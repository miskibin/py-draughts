"""Paired, reproducible matches against a frozen TurboEngine checkout.

Both engines use the current board implementation as referee. Each unique,
seeded opening is played twice, with colours reversed and fresh engines.
Errors abort the run, never silently become wins. The Elo interval resamples
whole opening pairs, not correlated individual games. This is relative Elo
at the specified time/depth, not an absolute FMJD rating.

    python tools/compare_turbo.py --baseline ../baseline --pairs 100 \
        --time 0.1 --workers 6 --out results.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draughts import Board, Color
from draughts.engines.turbo import TurboEngine

_BASELINES: dict = {}


def load_baseline(root):
    path = str(Path(root).resolve() / "draughts/engines/turbo.py")
    if path not in _BASELINES:
        spec = importlib.util.spec_from_file_location("turbo_baseline", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _BASELINES[path] = module
    return _BASELINES[path]


def openings(count, seed):
    rng = random.Random(seed)
    out = []
    seen = set()
    while len(out) < count:
        board = Board()
        for _ in range(rng.randint(4, 12)):
            legal = board.legal_moves
            if not legal:
                break
            board.push(rng.choice(legal))
        if board.white_men.bit_count() != 20 or board.black_men.bit_count() != 20:
            continue
        if board.fen in seen or board.legal_moves[0].captured_list:
            continue
        seen.add(board.fen)
        out.append(board.fen)
    return out


def elo(score):
    if score <= 0:
        return -math.inf
    if score >= 1:
        return math.inf
    return 400 * math.log10(score / (1 - score))


def paired_summary(pairs, seed=0):
    if len(pairs) < 2:
        raise ValueError("At least two opening pairs are required")
    pair_scores = [sum(g["score"] for g in pair["games"]) / 2 for pair in pairs]
    mean = statistics.mean(pair_scores)
    rng = random.Random(seed)
    samples = sorted(
        sum(rng.choices(pair_scores, k=len(pair_scores))) / len(pair_scores) for _ in range(20000)
    )
    low, high = samples[499], samples[19499]
    if low == high:
        # A degenerate empirical bootstrap is not evidence of zero uncertainty.
        # Hoeffding applies to bounded independent opening-pair scores.
        radius = math.sqrt(math.log(40) / (2 * len(pair_scores)))
        low, high = max(0, mean - radius), min(1, mean + radius)
    games = [g for pair in pairs for g in pair["games"]]
    return {
        "pairs": len(pairs),
        "games": len(games),
        "wins": sum(g["score"] == 1 for g in games),
        "draws": sum(g["score"] == 0.5 for g in games),
        "losses": sum(g["score"] == 0 for g in games),
        "score": mean,
        "relative_elo": elo(mean),
        "elo_95_ci": [elo(low), elo(high)],
        "interval": "20,000 opening-pair bootstrap resamples; Hoeffding fallback if degenerate",
        "positive_gain_at_95_percent": low > 0.5,
        "terminations": {
            k: sum(g["termination"] == k for g in games)
            for k in sorted({g["termination"] for g in games})
        },
        "seconds": [sum(g["seconds"][i] for g in games) for i in (0, 1)],
        "nodes": [sum(g["nodes"][i] for g in games) for i in (0, 1)],
    }


def play_pair(task):
    index, fen, root, depth, budget, max_plies = task
    baseline = load_baseline(root).TurboEngine
    games = []
    for candidate_white in (True, False):
        board = Board.from_fen(fen)
        engines = (
            TurboEngine(depth_limit=depth, time_limit=budget),
            baseline(depth_limit=depth, time_limit=budget),
        )
        times, nodes = [0.0, 0.0], [0, 0]
        moves = []
        result = board.result
        while result == "-" and len(moves) < max_plies:
            side = 0 if (board.turn == Color.WHITE) == candidate_white else 1
            start = time.perf_counter()
            move = engines[side].get_best_move(board)
            times[side] += time.perf_counter() - start
            nodes[side] += engines[side].nodes
            # Compare exact paths/captures, not the permissive Move.__eq__.
            if not any(
                move.square_list == m.square_list and move.captured_list == m.captured_list
                for m in board.legal_moves
            ):
                raise RuntimeError(f"Illegal move in pair {index}: {move}, {board.fen}")
            moves.append(str(move))
            board.push(move)
            result = board.result
        score = 0.5
        if result in ("1-0", "0-1"):
            score = float((result == "1-0") == candidate_white)
        games.append(
            {
                "candidate_white": candidate_white,
                "score": score,
                "termination": "max_plies" if result == "-" else result,
                "seconds": times,
                "nodes": nodes,
                "moves": moves,
                "final_fen": board.fen,
            }
        )
    return {"pair": index, "fen": fen, "games": games}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--pairs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261008)
    limits = parser.add_mutually_exclusive_group(required=True)
    limits.add_argument("--depth", type=int)
    limits.add_argument("--time", type=float)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-plies", type=int, default=300)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.pairs < 2 or args.workers < 1 or args.max_plies < 1:
        parser.error("pairs >= 2, workers >= 1 and max-plies >= 1 required")
    fens = openings(args.pairs, args.seed)
    tasks = [
        (i, fen, args.baseline, args.depth, args.time, args.max_plies) for i, fen in enumerate(fens)
    ]
    start = time.perf_counter()
    results = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(play_pair, task) for task in tasks]
        for future in as_completed(futures):
            pair = future.result()
            results.append(pair)
            scores = [g["score"] for g in pair["games"]]
            print(f"pair {len(results)}/{args.pairs}: {scores}", flush=True)
    results.sort(key=lambda pair: pair["pair"])
    roots = [Path(__file__).resolve().parents[1], Path(args.baseline).resolve()]
    data = {
        "meta": {
            "seed": args.seed,
            "depth": args.depth,
            "time_limit": args.time,
            "workers": args.workers,
            "max_plies": args.max_plies,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "elapsed_s": time.perf_counter() - start,
            "engine_sha256": [
                hashlib.sha256((root / "draughts/engines/turbo.py").read_bytes()).hexdigest()
                for root in roots
            ],
            "weights_sha256": [
                hashlib.sha256(
                    (root / "draughts/engines/turbo_weights.bin").read_bytes()
                ).hexdigest()
                for root in roots
            ],
            "rating": "relative to frozen baseline; NOT absolute or FMJD Elo",
        },
        "summary": paired_summary(results, args.seed),
        "pairs": results,
    }
    args.out.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data["summary"], indent=2))


if __name__ == "__main__":
    main()
