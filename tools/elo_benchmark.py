"""Head-to-head engine benchmark with Elo *and* a standard error.

The built-in :class:`draughts.Benchmark` reports a point Elo estimate. For
deciding whether one engine is really stronger than another you need the
uncertainty too: at a few hundred games the Elo noise is easily ±30-50, so a
"+20 Elo" point estimate is often indistinguishable from zero. This tool wraps
``Benchmark`` and adds the standard error, a 2-sigma interval, and a
significance verdict.

Each engine is given as a spec string ``kind[:key=val...]``:

    turbo                      TurboEngine, default settings
    turbo:time=0.2             TurboEngine, 0.2s / move
    turbo:depth=8:name=deep    TurboEngine, fixed depth 8, labelled "deep"
    simple:depth=6          SimpleEngine, depth 6

Examples::

    # Is TurboEngine at 0.1s stronger than at 0.3s? 300 games, 6 workers.
    python tools/elo_benchmark.py --e1 turbo:time=0.1 --e2 turbo:time=0.3 \
        --games 300 --workers 6

    # TurboEngine vs the simple engine.
    python tools/elo_benchmark.py --e1 turbo:time=0.2 --e2 simple:depth=6 \
        --games 100

A positive Elo means ``--e1`` is stronger. ``significant`` is true when the
estimate is at least two standard errors from zero.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from draughts import Benchmark, SimpleEngine, TurboEngine  # noqa: E402
from draughts.models import Color  # noqa: E402

_KINDS = {"turbo": TurboEngine, "simple": SimpleEngine}


def build_engine(spec: str):
    """Parse ``kind[:key=val...]`` into an engine instance."""
    parts = spec.split(":")
    kind = parts[0].strip().lower()
    if kind not in _KINDS:
        raise SystemExit(f"unknown engine kind {kind!r}; choose from {list(_KINDS)}")
    kwargs = {}
    for p in parts[1:]:
        if not p:
            continue
        k, _, v = p.partition("=")
        k = k.strip()
        if k == "time":
            kwargs["time_limit"] = float(v)
        elif k == "depth":
            kwargs["depth_limit"] = int(v)
        elif k == "name":
            kwargs["name"] = v
        else:
            raise SystemExit(f"unknown engine param {k!r} in spec {spec!r}")
    return _KINDS[kind](**kwargs)


def e1_scores(stats) -> list[float]:
    """Per-game score for engine 1: win 1.0, draw 0.5, loss 0.0."""
    out = []
    for r in stats.results:
        if r.winner is None:
            out.append(0.5)
        elif r.winner == r.e1_color:
            out.append(1.0)
        else:
            out.append(0.0)
    return out


def elo_and_se(scores: list[float]) -> tuple[float, float]:
    """Return (elo, se_elo) for engine 1 from its per-game scores."""
    n = len(scores)
    if n == 0:
        return 0.0, 0.0
    p = sum(scores) / n
    mean = p
    var = sum((s - mean) ** 2 for s in scores) / n  # population variance of scores
    se_p = math.sqrt(var / n) if n else 0.0
    # Elo(p) = -400 log10(1/p - 1); dElo/dp = (400/ln10) / (p(1-p))
    pc = min(max(p, 1e-6), 1 - 1e-6)
    elo = -400.0 * math.log10(1.0 / pc - 1.0)
    se_elo = (400.0 / math.log(10)) * se_p / max(p * (1.0 - p), 0.05)
    return elo, se_elo


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--e1", required=True, help="engine 1 spec (kind[:key=val...])")
    ap.add_argument("--e2", required=True, help="engine 2 spec (kind[:key=val...])")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-moves", type=int, default=200)
    ap.add_argument(
        "--no-swap", action="store_true", help="do not swap colours between games (default: swap)"
    )
    ap.add_argument("--csv", default=None, help="append summary to this CSV path")
    args = ap.parse_args()

    e1, e2 = build_engine(args.e1), build_engine(args.e2)
    stats = Benchmark(
        e1,
        e2,
        games=args.games,
        swap_colors=not args.no_swap,
        max_moves=args.max_moves,
        workers=args.workers,
    ).run()

    scores = e1_scores(stats)
    elo, se = elo_and_se(scores)
    two_se = 2.0 * se
    significant = abs(elo) >= two_se and two_se > 0

    print()
    print(f"  {stats.e1_name}  vs  {stats.e2_name}")
    print(f"  games:       {stats.games}")
    print(f"  W-L-D (e1):  {stats.e1_wins}-{stats.e2_wins}-{stats.draws}")
    print(f"  e1 score:    {stats.e1_win_rate:.1%}")
    print(f"  Elo (e1-e2): {elo:+.1f}  +/- {two_se:.1f} (2 SE)")
    print(
        f"  significant: {significant}  (|Elo| >= 2 SE, e1 {'stronger' if elo > 0 else 'weaker'})"
    )

    if args.csv:
        stats.to_csv(args.csv)
        print(f"  csv:         appended to {args.csv}")


if __name__ == "__main__":
    main()
