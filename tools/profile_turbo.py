"""
Profile TurboEngine performance: nodes per second over test positions.

Usage:
  python tools/profile_turbo.py --module tools.checkpoints.turbo_v3 --depth 7

Outputs per-position and TOTAL nodes, time, and nps.
"""

import argparse
import importlib
import sys
import time
from typing import Optional

from draughts import Board


# Test positions: opening, midgame, endgame-with-kings, complex
TEST_POSITIONS = [
    # Opening (starting position)
    ('[FEN "W:W28,33,34,38,39,43,44,48,49,50:B5,6,7,8,9,10,14,15,19,20"]', "Opening"),

    # Midgame
    ('[FEN "W:W31,32,33,34,35:B16,17,18,19,20"]', "Midgame-A"),
    ('[FEN "B:W24,28,29,30,33,34,38,39,44,45,49,50:B1,2,6,7,8,12,13,17,18,22,23,27"]', "Midgame-B"),

    # King captures / tactical
    ('[FEN "W:WK10:B14,15,24,25"]', "King Captures"),

    # Complex positions
    ('[FEN "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24"]', "Complex"),

    # Endgame with kings
    ('[FEN "W:WK10,K20:BK30,K40"]', "Endgame-Kings-A"),
    ('[FEN "B:WK15,K25:BK35,K45"]', "Endgame-Kings-B"),

    # More midgame positions for stability
    ('[FEN "W:W21,22,26,27,31,32:B14,15,19,20,24,25"]', "Midgame-C"),
    ('[FEN "W:W30,31,35,36,40,41,45,46:B8,9,13,14,18,19,23,24"]', "Midgame-D"),

    # Position with threats
    ('[FEN "W:W18,22,23,27,28,32,33:B6,7,11,12,16,17"]', "Midgame-Threats"),
]


def load_engine_class(module_path: str):
    """Dynamically import and return TurboEngine class from module path."""
    try:
        module = importlib.import_module(module_path)
        return module.TurboEngine
    except (ImportError, AttributeError) as e:
        print(f"Error loading module {module_path}: {e}", file=sys.stderr)
        sys.exit(1)


def profile_position(engine, board: Board, position_name: str) -> tuple[int, float, Optional[float]]:
    """
    Profile a single position.

    Returns: (nodes, secs, nps)
    nps is None if engine doesn't expose node counter.
    """
    # Ensure engine starts clean
    engine.nodes = 0

    start = time.perf_counter()
    move = engine.get_best_move(board)
    elapsed = time.perf_counter() - start

    nodes = getattr(engine, 'nodes', None)
    nps = nodes / elapsed if nodes is not None and elapsed > 0 else None

    return nodes, elapsed, nps


def main():
    parser = argparse.ArgumentParser(
        description="Profile TurboEngine: report nodes, time, and nps per position"
    )
    parser.add_argument(
        "--module",
        required=True,
        help="Module path (e.g., draughts.engines.turbo or tools.checkpoints.turbo_v3)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=7,
        help="Search depth (default: 7)"
    )
    args = parser.parse_args()

    # Load engine class
    TurboEngine = load_engine_class(args.module)

    # Initialize engine
    engine = TurboEngine(depth_limit=args.depth)

    print(f"# Profiling {args.module} at depth {args.depth}")
    print(f"# {len(TEST_POSITIONS)} positions")
    print()

    total_nodes = 0
    total_secs = 0.0
    has_nodes = True

    for fen, name in TEST_POSITIONS:
        board = Board.from_fen(fen)
        nodes, secs, nps = profile_position(engine, board, name)

        if nodes is None:
            has_nodes = False
            if nps is not None:
                print(f"{name:20} secs={secs:8.4f} nps={nps:10.0f}")
            else:
                print(f"{name:20} secs={secs:8.4f} nps=None")
        else:
            total_nodes += nodes
            total_secs += secs
            if nps is not None:
                print(f"{name:20} nodes={nodes:10} secs={secs:8.4f} nps={nps:10.0f}")
            else:
                print(f"{name:20} nodes={nodes:10} secs={secs:8.4f} nps=None")

    print()
    if has_nodes:
        total_nps = total_nodes / total_secs if total_secs > 0 else 0.0
        print(f"TOTAL               nodes={total_nodes:10} secs={total_secs:8.4f} nps={total_nps:10.0f}")
    else:
        print(f"TOTAL               secs={total_secs:8.4f} nps=None")


if __name__ == "__main__":
    main()
