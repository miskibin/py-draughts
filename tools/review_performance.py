"""Repeatable microbenchmarks and cProfile for a chosen source checkout.

Run the SAME script against each checkout, sequentially on an idle machine:
    python tools/review_performance.py --root ../baseline --out before.json
    python tools/review_performance.py --root . --out after.json

Times exclude imports, FEN setup, and profiling overhead. All raw repeats,
source hashes and environment metadata are retained. Search nodes may change
with search fixes, so both elapsed time and nodes/second are reported.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import platform
import pstats
import statistics
import sys
import time
from pathlib import Path

FENS = [
    "W:W31-50:B1-20",
    "W:W28,33,34,38,39,43,44,48,49,50:B5,6,7,8,9,10,14,15,19,20",
    "W:W31,32,33,34,35:B16,17,18,19,20",
    "W:WK10:B14,15,24,25",
    "W:WK4:B13,32,37,20",
    "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24",
    "W:WK10,K20:BK30,K40",
    "B:WK15,K25:BK35,K45",
    "W:W21,22,26,27,31,32:B14,15,19,20,24,25",
    "W:W30,31,35,36,40,41,45,46:B8,9,13,14,18,19,23,24",
    "W:W18,22,23,27,28,32,33:B6,7,11,12,16,17",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--loops", type=int, default=2000)
    parser.add_argument("--depth", type=int, default=6)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    from draughts import Board, Color
    from draughts.engines import turbo

    assert Path(turbo.__file__).resolve().is_relative_to(root)
    boards = [Board.from_fen(fen) for fen in FENS]
    moves = [b.legal_moves[0] for b in boards]
    positions = [(*turbo.TurboEngine._convert(b), b.turn == Color.WHITE) for b in boards]

    def fen():
        for value in FENS:
            Board.from_fen(value)

    def legal_moves():
        for board in boards:
            board.legal_moves

    def push_pop():
        for board, move in zip(boards, moves):
            board.push(move)
            board.pop()

    def features():
        for board in boards:
            board.features()

    def evaluate():
        for position in positions:
            turbo._evaluate(*position)

    def captures():
        for position in positions:
            turbo._gen_captures(*position)

    def search():
        rows = []
        for board in boards:
            engine = turbo.TurboEngine(depth_limit=args.depth)
            start = time.perf_counter()
            move = engine.get_best_move(board)
            elapsed = time.perf_counter() - start
            rows.append(
                {"fen": board.fen, "move": str(move), "nodes": engine.nodes, "seconds": elapsed}
            )
        return rows

    operations = {
        "fen": fen,
        "legal_moves": legal_moves,
        "push_pop": push_pop,
        "features": features,
        "evaluate": evaluate,
        "captures": captures,
    }
    data = {
        "meta": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "repeats": args.repeats,
            "loops": args.loops,
            "positions": len(boards),
            "depth": args.depth,
            "root": str(root),
            "source_sha256": {
                str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((root / "draughts").rglob("*.py"))
            },
        },
        "fens": FENS,
        "operations": {},
    }
    for name, function in operations.items():
        function()  # warm code/data caches, without retaining search state
        times = []
        for _ in range(args.repeats):
            start = time.perf_counter()
            for _ in range(args.loops):
                function()
            times.append((time.perf_counter() - start) / (args.loops * len(boards)))
        data["operations"][name] = {
            "median_us": statistics.median(times) * 1e6,
            "raw_seconds_per_operation": times,
        }
        print(name, data["operations"][name]["median_us"], flush=True)
    search()
    runs = [search() for _ in range(args.repeats)]
    seconds = [sum(row["seconds"] for row in run) for run in runs]
    nodes = [sum(row["nodes"] for row in run) for run in runs]
    data["search"] = {
        "median_seconds": statistics.median(seconds),
        "median_nodes": statistics.median(nodes),
        "median_nps": statistics.median(n / t for n, t in zip(nodes, seconds)),
        "runs": runs,
    }
    print("search", data["search"]["median_seconds"], data["search"]["median_nps"], flush=True)
    profiler = cProfile.Profile()
    profiler.runcall(search)
    stats = pstats.Stats(profiler)
    data["profile"] = [
        {
            "file": str(Path(key[0]).relative_to(root))
            if Path(key[0]).is_relative_to(root)
            else key[0],
            "line": key[1],
            "function": key[2],
            "calls": val[1],
            "self_s": val[2],
            "cumulative_s": val[3],
        }
        for key, val in sorted(stats.stats.items(), key=lambda item: item[1][2], reverse=True)[:30]
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
