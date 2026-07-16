#!/usr/bin/env python
"""
Measure TurboEngine strength and dump a JSON the chart generator consumes.

Three complementary experiments, all reported as an Elo with a standard error
(``elo +/- 2*SE``).  Fixed search depth is the default because wall-clock time
on a shared/cloud CPU is noisy and non-reproducible; depth-limited games give
the same result on any machine.

1. DEPTH LADDER  (``--ladder``)
   Self-play head-to-head ``Turbo(depth=k)`` vs ``Turbo(depth=k-1)`` for a range
   of k.  Each rung is the strength gained by one more ply of search; the
   cumulative sum is an internal Elo curve anchored at the shallowest depth.
   Same engine on both sides, so the trained eval is identical -- this isolates
   the value of *search depth*.

2. FLAGSHIP vs BASELINE  (``--flagship``)
   ``TurboEngine`` vs the general-purpose ``SimpleEngine`` at equal search depth
   (reproducible) and, as a secondary point, at equal wall-clock time.

3. TRAINING ABLATION  (``--ablation``)
   ``TurboEngine`` with the shipped trained pattern weights vs the *same* engine
   with the pattern term switched off (v2 hand eval).  This is the Elo the
   offline Texel/Scan training actually bought.  The two variants are loaded as
   independent module copies so their evaluations do not share global state.

The internal scale is relative (anchored at ``Turbo(depth=D0)``), not an
absolute FMJD/rating-list number: with no externally-calibrated opponent
(e.g. the Scan engine) available, an absolute rating cannot be claimed.

Usage::

    python tools/measure_turbo_elo.py --all --workers 3 --out docs/source/_static/turbo_elo.json
    python tools/measure_turbo_elo.py --smoke      # tiny, for a quick sanity run
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from draughts import Benchmark, SimpleEngine, TurboEngine  # noqa: E402
from draughts.benchmark import _play_game  # noqa: E402
from draughts.boards.standard import Board as StandardBoard  # noqa: E402
from draughts.models import Color  # noqa: E402

_TURBO_PATH = str(Path(__file__).parent.parent / "draughts" / "engines" / "turbo.py")


# ---------------------------------------------------------------------------
# Elo estimation from per-game scores (win=1, draw=0.5, loss=0 for engine 1)
# ---------------------------------------------------------------------------


def elo_and_se(scores: list[float]) -> tuple[float, float]:
    """(elo, se_elo) for engine 1 from its per-game scores.

    Elo(p) = -400 log10(1/p - 1);  dElo/dp = (400/ln10) / (p(1-p)).
    """
    n = len(scores)
    if n == 0:
        return 0.0, 0.0
    p = sum(scores) / n
    var = sum((s - p) ** 2 for s in scores) / n
    se_p = math.sqrt(var / n)
    pc = min(max(p, 1e-6), 1 - 1e-6)
    elo = -400.0 * math.log10(1.0 / pc - 1.0)
    se_elo = (400.0 / math.log(10)) * se_p / max(p * (1.0 - p), 0.02)
    return elo, se_elo


def _scores_from_results(results) -> list[float]:
    out = []
    for r in results:
        if r.winner is None:
            out.append(0.5)
        elif r.winner == r.e1_color:
            out.append(1.0)
        else:
            out.append(0.0)
    return out


def random_openings(n: int, seed: int, min_ply: int = 4, max_ply: int = 7) -> list[str]:
    """``n`` distinct, near-balanced opening FENs, each reached by a few random
    legal plies from the start.  Using a *distinct* opening per game makes the
    games statistically independent — cycling a small fixed book with a
    deterministic fixed-depth engine produces correlated (near-duplicate) games
    and understates the Elo standard error.
    """
    import random

    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[str] = []
    guard = 0
    while len(out) < n and guard < n * 80:
        guard += 1
        board = StandardBoard()
        for _ in range(rng.randint(min_ply, max_ply)):
            lm = board.legal_moves
            if not lm or board.game_over:
                break
            board.push(rng.choice(lm))
        if board.game_over:
            continue
        # keep only material-balanced openings (no capture played: 20 men each)
        w = int(board.white_men | board.white_kings).bit_count()
        b = int(board.black_men | board.black_kings).bit_count()
        if w != 20 or b != 20:
            continue
        fen = board.fen.split('"')[1]  # inner FEN, unwrapped
        if fen in seen:
            continue
        seen.add(fen)
        out.append(fen)
    return out


def _summary(name: str, results, extra: dict | None = None) -> dict:
    scores = _scores_from_results(results)
    wins = sum(1 for s in scores if s == 1.0)
    losses = sum(1 for s in scores if s == 0.0)
    draws = sum(1 for s in scores if s == 0.5)
    elo, se = elo_and_se(scores)
    row = {
        "name": name,
        "games": len(scores),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "elo": round(elo, 1),
        "se": round(se, 1),
        "elo_2se": round(2 * se, 1),
    }
    if extra:
        row.update(extra)
    print(
        f"  {name:36s}  {wins}-{losses}-{draws}  "
        f"score={row['score']:.3f}  Elo={elo:+.1f} +/- {2 * se:.1f}"
    )
    return row


# ---------------------------------------------------------------------------
# Benchmark-backed matchups (picklable engines -> real process pool)
# ---------------------------------------------------------------------------


def run_match(e1, e2, name, games, workers, openings, max_moves=250, swap=True) -> dict:
    stats = Benchmark(
        e1, e2, games=games, openings=openings, swap_colors=swap,
        max_moves=max_moves, workers=workers,
    ).run()
    return _summary(
        name,
        stats.results,
        extra={
            "e1": stats.e1_name,
            "e2": stats.e2_name,
            "avg_moves": round(stats.avg_moves, 1),
            "avg_ms_e1": round(stats.avg_time_e1 * 1000, 1),
            "avg_ms_e2": round(stats.avg_time_e2 * 1000, 1),
            "avg_nodes_e1": round(stats.avg_nodes_e1),
            "avg_nodes_e2": round(stats.avg_nodes_e2),
        },
    )


# ---------------------------------------------------------------------------
# Training ablation: trained vs untrained (own-process module copies)
# ---------------------------------------------------------------------------


def _load_untrained_turbo(depth_limit):
    """A TurboEngine whose pattern weights are forced to zero (v2 hand eval),
    loaded as an independent module object so its eval globals are separate
    from the shipped, trained module."""
    spec = importlib.util.spec_from_file_location("turbo_untrained", _TURBO_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PAT_W = tuple((0,) * m.PAT_ENTRIES for _ in range(m.N_PATTERNS))
    m.PAT_ACTIVE = False
    return m.TurboEngine(depth_limit=depth_limit)


def _ablation_worker(args):
    """Play a slice of trained-vs-untrained games inside one worker process.

    Engines are built here (not pickled in) so the two module copies keep
    independent evaluation state.  ``configs`` is a list of
    (game_number, trained_is_white, opening)."""
    depth, max_moves, configs = args
    trained = TurboEngine(depth_limit=depth)
    untrained = _load_untrained_turbo(depth_limit=depth)
    out = []
    for n, white, opening in configs:
        r = _play_game(trained, untrained, StandardBoard, n, white, opening, max_moves)
        out.append((r.winner, r.e1_color))
    return out


class _R:
    """Minimal result shim so _summary can consume ablation tuples."""

    def __init__(self, winner, e1_color):
        self.winner = winner
        self.e1_color = e1_color


def run_ablation(depth, games, workers, openings, max_moves=250) -> dict:
    # one distinct opening per game -> independent games (see random_openings)
    configs = [
        (i + 1, i % 2 == 0, (f"open{i}", openings[i % len(openings)])) for i in range(games)
    ]
    # Split into `workers` contiguous slices.
    per = math.ceil(games / max(1, workers))
    slices = [configs[i : i + per] for i in range(0, games, per)]
    tasks = [(depth, max_moves, s) for s in slices]

    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_ablation_worker, t) for t in tasks]
        for f in as_completed(futs):
            results.extend(_R(w, c) for w, c in f.result())
    return _summary(f"Turbo(d={depth}) trained vs untrained", results, extra={"depth": depth})


# ---------------------------------------------------------------------------


def cumulative_ladder(ladder: list[dict], anchor_depth: int) -> list[dict]:
    """Turn per-rung Elo gains into a cumulative internal Elo curve."""
    by_high = {r["high"]: r for r in ladder}
    depths = sorted({anchor_depth} | {r["high"] for r in ladder} | {r["low"] for r in ladder})
    curve = []
    cum = 0.0
    cum_var = 0.0
    for d in depths:
        if d == anchor_depth:
            curve.append({"depth": d, "elo": 0.0, "se": 0.0})
            continue
        rung = by_high.get(d)
        if rung is None:
            continue
        cum += rung["elo"]
        cum_var += (rung["se"]) ** 2
        curve.append({"depth": d, "elo": round(cum, 1), "se": round(math.sqrt(cum_var), 1)})
    return curve


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--all", action="store_true", help="run every experiment")
    ap.add_argument("--ladder", action="store_true")
    ap.add_argument("--flagship", action="store_true")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="tiny counts for a sanity check")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--ladder-games", type=int, default=100)
    ap.add_argument("--flagship-games", type=int, default=60)
    ap.add_argument("--ablation-games", type=int, default=200)
    ap.add_argument("--ablation-depth", type=int, default=6)
    ap.add_argument("--time-control", type=float, default=0.1)
    ap.add_argument("--open-seed", type=int, default=20260716,
                    help="seed for the distinct random opening positions")
    ap.add_argument("--open-min", type=int, default=4, help="min random opening plies")
    ap.add_argument("--open-max", type=int, default=7, help="max random opening plies")
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "docs" / "source" / "_static" / "turbo_elo.json"))
    args = ap.parse_args()

    if args.smoke:
        args.all = True
        args.ladder_games = args.flagship_games = args.ablation_games = 6
        args.workers = min(args.workers, 3)
    if args.all:
        args.ladder = args.flagship = args.ablation = True
    if not (args.ladder or args.flagship or args.ablation):
        ap.error("choose --all / --ladder / --flagship / --ablation (or --smoke)")

    # Each matchup gets its own set of DISTINCT random openings (one per game),
    # so games are independent and the reported standard errors are honest.
    seed = [args.open_seed]

    def openings(n):
        seed[0] += 1
        return random_openings(n, seed[0], args.open_min, args.open_max)

    t0 = time.perf_counter()
    data: dict = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "processor": platform.processor() or platform.machine(),
            "cpu_count": os.cpu_count(),
            "workers": args.workers,
            "openings": "distinct random per game (independent games)",
            "open_plies": [args.open_min, args.open_max],
            "note": (
                "Fixed-depth Elo is machine-independent; the internal ladder is "
                "anchored at the shallowest depth (relative scale, not absolute FMJD)."
            ),
        }
    }

    if args.ladder:
        print("\n== DEPTH LADDER (Turbo d=k vs d=k-1) ==")
        rungs = [(5, 4), (6, 5), (7, 6)] if not args.smoke else [(4, 3), (5, 4)]
        ladder = []
        for high, low in rungs:
            row = run_match(
                TurboEngine(depth_limit=high),
                TurboEngine(depth_limit=low),
                f"Turbo d={high} vs d={low}",
                args.ladder_games,
                args.workers,
                openings(args.ladder_games),
            )
            row["high"], row["low"] = high, low
            ladder.append(row)
        anchor = min(low for _, low in rungs)
        data["ladder"] = ladder
        data["ladder_cumulative"] = cumulative_ladder(ladder, anchor)
        data["ladder_anchor_depth"] = anchor

    if args.flagship:
        print("\n== FLAGSHIP vs BASELINE (Turbo vs Simple) ==")
        fd = 6 if not args.smoke else 4
        flagship_depth = run_match(
            TurboEngine(depth_limit=fd),
            SimpleEngine(depth_limit=fd),
            f"Turbo d={fd} vs Simple d={fd}",
            args.flagship_games,
            args.workers,
            openings(args.flagship_games),
        )
        flagship_depth["mode"] = "fixed-depth"
        flagship_depth["depth"] = fd
        flagship_depth["reproducible"] = True
        flagship_time = run_match(
            TurboEngine(time_limit=args.time_control),
            SimpleEngine(time_limit=args.time_control),
            f"Turbo t={args.time_control}s vs Simple t={args.time_control}s",
            args.flagship_games,
            args.workers,
            openings(args.flagship_games),
        )
        flagship_time["mode"] = "equal-time"
        flagship_time["time_control"] = args.time_control
        flagship_time["reproducible"] = False
        data["flagship"] = [flagship_depth, flagship_time]

    if args.ablation:
        print("\n== TRAINING ABLATION (trained vs untrained pattern eval) ==")
        data["ablation"] = run_ablation(
            args.ablation_depth if not args.smoke else 4,
            args.ablation_games,
            args.workers,
            openings(args.ablation_games),
        )

    data["meta"]["elapsed_s"] = round(time.perf_counter() - t0, 1)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(f"\nwrote {out}  ({data['meta']['elapsed_s']}s)")


if __name__ == "__main__":
    main()
