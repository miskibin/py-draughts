"""
Texel-style evaluation tuner for ``AlphaBetaEngine``.

The standard recipe (Hellsten 2014):

  E(w) = mean( ( sigmoid(eval(pos; w) / K) - result )^2 )

where ``result ∈ {0, 0.5, 1}`` is the *game* outcome from the side-to-move's
perspective. We minimise E with coordinate-descent because:

* the evaluation is fast but non-differentiable (PST lookups, popcounts);
* parameter count is tiny (currently 4) so coord-descent converges in
  minutes;
* the result is reproducible from a fixed dataset.

Three dataset sources are supported:

* ``--source pdn <path>``   — newline-separated PDN (whitespace-separated
                              games). One ``(fen, result)`` row is sampled
                              per quiet position in each game.
* ``--source self-play``    — generate a small dataset using the current
                              engine vs random.
* ``--source synthetic``    — random walks; result determined by final
                              material balance. Cheap default — used by
                              the smoke test.

Usage::

    python -m tools.tune_eval --source synthetic --positions 200 --iters 4
    python -m tools.tune_eval --source pdn data/games.pdn --positions 5000

The output JSON is written to ``tools/tuned_eval.json`` and can be passed to
``AlphaBetaEngine(eval_params=...)``.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import time
from pathlib import Path
from typing import Optional

from draughts import (
    AlphaBetaEngine,
    AmericanBoard,
    FrisianBoard,
    RussianBoard,
    StandardBoard,
)
from draughts.boards.base import BaseBoard
from draughts.models import Color


_BOARDS = {
    "standard": StandardBoard,
    "american": AmericanBoard,
    "russian": RussianBoard,
    "frisian": FrisianBoard,
}


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------


def _result_for_side_to_move(board: BaseBoard, final_result: str) -> float:
    """Map ``board.result`` ∈ {1-0, 0-1, 1/2-1/2} to {1, 0, 0.5} for the side
    that was on move at ``board``."""
    if final_result == "1/2-1/2":
        return 0.5
    if final_result == "1-0":  # white won
        return 1.0 if board.turn == Color.WHITE else 0.0
    if final_result == "0-1":  # black won
        return 1.0 if board.turn == Color.BLACK else 0.0
    raise ValueError(f"Unknown result {final_result!r}")


def _sample_positions_from_game(
    moves: list, BoardCls, samples: int, rng: random.Random
) -> list[BaseBoard]:
    """Replay a game and return ``samples`` random quiet positions."""
    board = BoardCls()
    snapshots: list[BaseBoard] = []
    for ply, move in enumerate(moves):
        try:
            board.push_uci(move)
        except Exception:
            break
        # Skip captures and the first 6 plies (still in book).
        if ply < 6 or move.find("x") >= 0:
            continue
        snapshots.append(board.copy())
    if not snapshots:
        return []
    if len(snapshots) <= samples:
        return snapshots
    return rng.sample(snapshots, samples)


def load_pdn_dataset(
    path: Path, BoardCls, max_positions: int, rng: random.Random
) -> list[tuple[BaseBoard, float]]:
    """Parse a PDN file and extract ``(board, result)`` rows."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    games = re.split(r"\n\s*\n", text)
    pairs: list[tuple[BaseBoard, float]] = []
    move_pat = re.compile(r"\b(\d+[-x]\d+(?:[-x]\d+)*)\b")
    res_pat = re.compile(r'\[Result\s*"([^"]+)"\]')
    for game_text in games:
        m = res_pat.search(game_text)
        if not m:
            continue
        result_str = m.group(1).strip()
        if result_str not in ("1-0", "0-1", "1/2-1/2"):
            continue
        moves = [
            x for x in move_pat.findall(game_text)
            if x not in {"1-0", "0-1"}
        ]
        if not moves:
            continue
        for board in _sample_positions_from_game(moves, BoardCls, samples=4, rng=rng):
            pairs.append((board, _result_for_side_to_move(board, result_str)))
            if len(pairs) >= max_positions:
                return pairs
    return pairs


def synthetic_dataset(
    BoardCls, n: int, rng: random.Random
) -> list[tuple[BaseBoard, float]]:
    """Random walks; outcome derived from final material balance."""
    pairs: list[tuple[BaseBoard, float]] = []
    while len(pairs) < n:
        b = BoardCls()
        depth = rng.randint(20, 50)
        for _ in range(depth):
            legal = list(b.legal_moves)
            if not legal:
                break
            b.push(rng.choice(legal))
            if b.game_over:
                break
        # Material-based outcome
        wm = b._popcount(b.white_men) + 2 * b._popcount(b.white_kings)
        bm = b._popcount(b.black_men) + 2 * b._popcount(b.black_kings)
        if wm > bm + 1:
            res = "1-0"
        elif bm > wm + 1:
            res = "0-1"
        else:
            res = "1/2-1/2"
        pairs.append((b, _result_for_side_to_move(b, res)))
    return pairs


def self_play_dataset(
    BoardCls, n_games: int, depth: int, rng: random.Random
) -> list[tuple[BaseBoard, float]]:
    """Engine-vs-random self-play to build a tiny labeled dataset."""
    pairs: list[tuple[BaseBoard, float]] = []
    eng = AlphaBetaEngine(depth_limit=depth)
    for _ in range(n_games):
        board = BoardCls()
        snapshots: list[BaseBoard] = []
        moves_played = 0
        while not board.game_over and moves_played < 80:
            legal = list(board.legal_moves)
            if not legal:
                break
            if moves_played >= 6:
                snapshots.append(board.copy())
            # Engine plays for one side, random for other (alternating each game)
            if (moves_played + len(pairs)) % 2 == 0:
                board.push(eng.get_best_move(board))
            else:
                board.push(rng.choice(legal))
            moves_played += 1
        result = board.result if board.result != "-" else "1/2-1/2"
        for snap in snapshots:
            pairs.append((snap, _result_for_side_to_move(snap, result)))
    return pairs


# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------


def _sigmoid(x: float, K: float) -> float:
    if x > 50 * K:
        return 1.0
    if x < -50 * K:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x / K))


def _loss(
    dataset: list[tuple[BaseBoard, float]],
    eval_fn,
    K: float,
) -> float:
    n = len(dataset)
    if n == 0:
        return 0.0
    total = 0.0
    for board, target in dataset:
        score = eval_fn(board)
        diff = _sigmoid(score, K) - target
        total += diff * diff
    return total / n


def fit_K(
    dataset: list[tuple[BaseBoard, float]],
    eval_fn,
    K_range=(0.1, 5.0),
    steps: int = 30,
) -> float:
    """Golden-section search for the sigmoid scale K."""
    lo, hi = K_range
    phi = (math.sqrt(5) - 1) / 2
    a = lo + (1 - phi) * (hi - lo)
    b = lo + phi * (hi - lo)
    fa = _loss(dataset, eval_fn, a)
    fb = _loss(dataset, eval_fn, b)
    for _ in range(steps):
        if fa < fb:
            hi = b
            b = a
            fb = fa
            a = lo + (1 - phi) * (hi - lo)
            fa = _loss(dataset, eval_fn, a)
        else:
            lo = a
            a = b
            fa = fb
            b = lo + phi * (hi - lo)
            fb = _loss(dataset, eval_fn, b)
        if hi - lo < 1e-3:
            break
    return (lo + hi) / 2


def coordinate_descent(
    params: dict,
    bounds: dict,
    dataset: list[tuple[BaseBoard, float]],
    iters: int = 5,
) -> dict:
    """Cheap coord-descent in 1D per parameter."""
    eng = AlphaBetaEngine(depth_limit=1, eval_params=params)
    # ``evaluate`` lazily binds Zobrist & PST tables to the variant.
    eval_fn = eng.evaluate

    best = dict(params)
    K = fit_K(dataset, eval_fn)
    cur_loss = _loss(dataset, eval_fn, K)
    print(f"  initial loss={cur_loss:.5f} K={K:.2f}")

    for it in range(iters):
        improved = False
        for name, (lo, hi, step) in bounds.items():
            for delta in (+step, -step):
                trial = dict(best)
                trial[name] = max(lo, min(hi, best[name] + delta))
                eng.eval_params = trial
                trial_loss = _loss(dataset, eval_fn, K)
                if trial_loss < cur_loss - 1e-6:
                    best = trial
                    cur_loss = trial_loss
                    improved = True
                    eng.eval_params = best
        K = fit_K(dataset, eval_fn)
        cur_loss = _loss(dataset, eval_fn, K)
        print(f"  iter {it+1}: loss={cur_loss:.5f} K={K:.2f} params={best}")
        if not improved:
            break
    return best


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Texel-style eval tuner")
    parser.add_argument(
        "--source",
        choices=["pdn", "self-play", "synthetic"],
        default="synthetic",
    )
    parser.add_argument("--pdn-path", type=Path, default=None)
    parser.add_argument("--variant", choices=list(_BOARDS), default="standard")
    parser.add_argument("--positions", type=int, default=200)
    parser.add_argument("--iters", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "tuned_eval.json",
    )
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    BoardCls = _BOARDS[args.variant]

    t0 = time.time()
    if args.source == "pdn":
        if args.pdn_path is None:
            parser.error("--pdn-path required when --source pdn")
        dataset = load_pdn_dataset(args.pdn_path, BoardCls, args.positions, rng)
    elif args.source == "self-play":
        dataset = self_play_dataset(BoardCls, n_games=args.positions // 8 + 1,
                                     depth=2, rng=rng)
    else:
        dataset = synthetic_dataset(BoardCls, args.positions, rng)

    print(f"Loaded {len(dataset)} positions in {time.time() - t0:.1f}s")
    if len(dataset) < 5:
        print("Dataset too small — aborting")
        return 1

    bounds = {
        "man_value": (1.0, 1.0, 0.0),  # anchor at 1.0 (everything else is in man-units)
        "king_value": (1.5, 5.0, 0.1),
        "tempo": (0.0, 0.3, 0.02),
        "back_rank_bonus": (0.0, 0.5, 0.02),
    }
    start = dict(AlphaBetaEngine.DEFAULT_EVAL_PARAMS)
    tuned = coordinate_descent(start, bounds, dataset, iters=args.iters)

    args.out.write_text(json.dumps(tuned, indent=2))
    print(f"Wrote tuned params to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
