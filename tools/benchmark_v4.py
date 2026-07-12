"""
Ship-gate benchmark: live v4 TurboEngine vs frozen v3 TurboEngine.

Plays engine1 = live ``draughts.TurboEngine`` (v4, reads
``draughts/engines/turbo_weights.bin``) against engine2 =
``tools.checkpoints.turbo_v3.TurboEngine`` (frozen v3, reads its own weights).
A POSITIVE ``elo_diff`` therefore means v4 is stronger.

Two configs run sequentially (the ship gate):
  * fast: time_limit=0.1s, games=200  -- GATED: must have elo >= 2*SE_elo
  * slow: time_limit=0.3s, games=100  -- must have elo > 0

Ship verdict = both configs elo > 0 AND the fast config elo >= 2*SE_elo.

Elo standard error is derived from the per-game score of engine1 (v4), where
each game contributes s in {1.0 win, 0.5 draw, 0.0 loss}:
    p       = mean(s)                              (== stats.e1_win_rate)
    var     = sample variance of the observed s
    SE_p    = sqrt(var / n)
    SE_elo  = (400 / ln 10) * SE_p / max(p*(1-p), 0.05)

Usage:
  python tools/benchmark_v4.py                      # full gate (both configs)
  python tools/benchmark_v4.py --config fast        # only the fast config
  python tools/benchmark_v4.py --smoke              # quick end-to-end check
  python tools/benchmark_v4.py --games 40 --time 0.2 --workers 4
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

# Add project root to path (mirrors tools/profile_turbo.py) so both
# `tools.checkpoints.turbo_v3` and the repo's `draughts` package resolve --
# including inside ProcessPoolExecutor workers, which restore the parent's
# sys.path when spawning.
sys.path.insert(0, str(Path(__file__).parent.parent))

from draughts import Benchmark, TurboEngine  # noqa: E402  (live v4)
from draughts.benchmark import BenchmarkStats  # noqa: E402
from tools.checkpoints.turbo_v3 import TurboEngine as TurboV3  # noqa: E402  (frozen v3)

# Config presets. `gated` marks the config whose Elo must clear the 2*SE bar
# (the fast/0.1s config) for the ship gate.
CONFIGS: dict[str, dict] = {
    "fast": {"time_limit": 0.1, "games": 200, "gated": True},
    "slow": {"time_limit": 0.3, "games": 100, "gated": False},
}

# Distinct, untracked results path. Deliberately NOT "benchmark_results.csv":
# that filename is a tracked file owned by tools/compare_versions.py with a
# different schema, and BenchmarkStats.to_csv only writes a header when the file
# is absent -- appending here would corrupt that file. Overridable via --csv.
DEFAULT_CSV_PATH = "benchmark_v4_results.csv"


def _v4_scores(stats: BenchmarkStats) -> list[float]:
    """Per-game score for engine1 (v4): 1.0 win, 0.5 draw, 0.0 loss."""
    scores: list[float] = []
    for r in stats.results:
        if r.winner is None:
            scores.append(0.5)
        elif r.winner == r.e1_color:
            scores.append(1.0)
        else:
            scores.append(0.0)
    return scores


def _se_elo(scores: list[float]) -> tuple[float, float]:
    """
    Return (SE_elo, p) for the given per-game scores.

    SE_elo = (400 / ln 10) * sqrt(var/n) / max(p*(1-p), 0.05)
    where var is the sample variance of the observed scores.
    """
    n = len(scores)
    if n == 0:
        return 0.0, 0.5
    arr = np.asarray(scores, dtype=float)
    p = float(arr.mean())
    var = float(arr.var())  # variance of observed {0, 0.5, 1} scores
    se_p = math.sqrt(var / n)
    denom = max(p * (1.0 - p), 0.05)
    se_elo = (400.0 / math.log(10.0)) * se_p / denom
    return se_elo, p


def run_config(
    label: str,
    time_limit: float,
    games: int,
    workers: int,
    gated: bool,
    csv_path: str,
) -> dict:
    """Run one config, append to CSV, print a per-config report, return summary."""
    print("=" * 60)
    print(f"  CONFIG '{label}': time={time_limit}s  games={games}  workers={workers}")
    print("=" * 60)

    # depth_limit=None -> search is governed purely by the time deadline, so the
    # match is time-controlled and identical for both engines.
    v4 = TurboEngine(depth_limit=None, time_limit=time_limit, name="TurboV4")
    v3 = TurboV3(depth_limit=None, time_limit=time_limit, name="TurboV3")

    bench = Benchmark(
        v4,
        v3,
        games=games,
        openings=None,          # default STANDARD_OPENINGS for 10x10
        swap_colors=True,
        max_moves=200,
        workers=workers,
    )
    stats = bench.run()
    stats.to_csv(csv_path)

    scores = _v4_scores(stats)
    se_elo, _p = _se_elo(scores)
    two_se = 2.0 * se_elo
    elo = stats.elo_diff

    passed = elo > 0.0 and (elo >= two_se if gated else True)

    print()
    print(f"  W-L-D (v4-v3-draw): {stats.e1_wins}-{stats.e2_wins}-{stats.draws}")
    print(f"  v4 win rate:        {stats.e1_win_rate:.1%}")
    print(f"  Elo (v4 - v3):      {elo:+.1f}")
    print(f"  2*SE_elo:           {two_se:.1f}")
    print(f"  Elo +/- 2SE:        {elo:+.1f} +/- {two_se:.1f}")
    gate_note = " (elo>0 AND elo>=2SE)" if gated else " (elo>0)"
    print(f"  Result:             {'PASS' if passed else 'FAIL'}{gate_note}")
    print()

    return {
        "label": label,
        "time_limit": time_limit,
        "games": stats.games,
        "wins": stats.e1_wins,
        "losses": stats.e2_wins,
        "draws": stats.draws,
        "win_rate": stats.e1_win_rate,
        "elo": elo,
        "two_se": two_se,
        "gated": gated,
        "passed": passed,
    }


def print_markdown_summary(results: list[dict], full_gate: bool) -> bool:
    """Print a markdown table + overall ship verdict. Return ship bool."""
    print("## Benchmark summary (v4 vs frozen v3)")
    print()
    print("| Config | Time | Games | W-L-D | Win% | Elo | +/-2SE | Result |")
    print("|--------|------|-------|-------|------|-----|--------|--------|")
    for r in results:
        wld = f"{r['wins']}-{r['losses']}-{r['draws']}"
        print(
            f"| {r['label']} | {r['time_limit']}s | {r['games']} | {wld} | "
            f"{r['win_rate']:.1%} | {r['elo']:+.1f} | {r['two_se']:.1f} | "
            f"{'PASS' if r['passed'] else 'FAIL'} |"
        )
    print()

    all_positive = all(r["elo"] > 0.0 for r in results)
    fast = next((r for r in results if r["gated"]), None)
    fast_ok = fast is not None and fast["elo"] >= fast["two_se"]
    ship = all_positive and fast_ok

    verdict = "SHIP" if ship else "NO-SHIP"
    if not full_gate:
        verdict += " (partial/smoke run -- informational only, not a real gate)"
    print(f"**Verdict: {verdict}**")
    print(
        "  gate = both configs Elo > 0 AND fast(0.1s) config Elo >= 2*SE_elo"
    )
    return ship


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ship-gate benchmark: live v4 TurboEngine vs frozen v3."
    )
    parser.add_argument(
        "--config",
        choices=["both", "fast", "slow"],
        default="both",
        help="Which config(s) to run (default: both).",
    )
    parser.add_argument(
        "--games", type=int, default=None, help="Override games for selected configs."
    )
    parser.add_argument(
        "--time", type=float, default=None, help="Override time_limit (s) for selected configs."
    )
    parser.add_argument(
        "--workers", type=int, default=6, help="Parallel worker processes (default: 6)."
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_PATH,
        help=(
            "Results CSV path (default: %(default)s). NEVER point this at the "
            "tracked benchmark_results.csv (different schema, owned by "
            "tools/compare_versions.py) -- appending would corrupt it."
        ),
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Quick end-to-end check: 1 config, games=4, time=0.05, workers=2.",
    )
    args = parser.parse_args()

    if args.smoke:
        # Single (fast/gated) config, tiny sample -- proves the script runs
        # end-to-end, computes SE, writes CSV, and prints the verdict.
        selected = ["fast"]
        games_override = 4
        time_override = 0.05
        workers = 2
        full_gate = False
        print("[SMOKE] games=4 time=0.05 workers=2 config=fast\n")
    else:
        if args.config == "both":
            selected = ["fast", "slow"]
        else:
            selected = [args.config]
        games_override = args.games
        time_override = args.time
        workers = args.workers
        full_gate = args.config == "both" and args.games is None and args.time is None

    results: list[dict] = []
    for label in selected:
        cfg = CONFIGS[label]
        time_limit = time_override if time_override is not None else cfg["time_limit"]
        games = games_override if games_override is not None else cfg["games"]
        results.append(
            run_config(
                label=label,
                time_limit=time_limit,
                games=games,
                workers=workers,
                gated=cfg["gated"],
                csv_path=args.csv,
            )
        )

    ship = print_markdown_summary(results, full_gate=full_gate)
    print(f"\nCSV appended to: {Path(args.csv).resolve()}")

    # Exit code reflects the gate on a full run so CI / callers can branch on it.
    if full_gate:
        sys.exit(0 if ship else 1)


if __name__ == "__main__":
    main()
