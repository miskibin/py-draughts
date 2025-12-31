#!/usr/bin/env python
"""Worker script for legal moves benchmark. Run in isolated venv."""

import gc
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
    
    # Pre-clean FENs once
    clean_positions = []
    for fen in positions:
        if fen.startswith("B:B:") or fen.startswith("W:W:"):
            fen = fen[2:]
        clean_positions.append(fen)
    
    # Warm up - let CPU frequency stabilize
    for _ in range(warmup):
        for fen in clean_positions:
            board = get_board("standard", fen)
            list(board.legal_moves)
    
    # Disable GC during measurement
    gc.collect()
    gc.disable()
    
    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        for fen in clean_positions:
            board = get_board("standard", fen)
            list(board.legal_moves)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    gc.enable()
    
    result = {
        "times": times,
        "median_ms": median(times) * 1000,
        "positions_count": len(clean_positions),
    }
    print(json.dumps(result))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
