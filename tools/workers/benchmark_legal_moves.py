#!/usr/bin/env python
"""Worker script for legal moves benchmark. Run in isolated venv."""

import json
import sys
import time
from pathlib import Path
from statistics import median


def main():
    positions_file = Path(sys.argv[1])
    warmup = int(sys.argv[2])
    rounds = int(sys.argv[3])
    
    positions = json.loads(positions_file.read_text())["positions"]
    
    from draughts import get_board
    
    times = []
    for _ in range(warmup + rounds):
        start = time.perf_counter()
        for fen in positions:
            # Clean up malformed FENs
            if fen.startswith("B:B:") or fen.startswith("W:W:"):
                fen = fen[2:]
            board = get_board("standard", fen)
            list(board.legal_moves)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    result = {
        "times": times[warmup:],
        "median_ms": median(times[warmup:]) * 1000,
        "positions_count": len(positions),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
