#!/usr/bin/env python
"""Worker script for legal moves benchmark. Run in isolated venv."""

import gc
import json
import os
import sys
import time
from pathlib import Path
from statistics import median


def set_high_priority_and_affinity():
    """Set high process priority and pin to a single CPU core for stable benchmarks."""
    try:
        import psutil

        proc = psutil.Process()

        # Set high priority (below realtime, but above normal)
        if sys.platform == "win32":
            proc.nice(psutil.HIGH_PRIORITY_CLASS)
        else:
            # Unix: lower nice = higher priority, -10 is high but not root-only
            try:
                proc.nice(-10)
            except PermissionError:
                proc.nice(0)  # At least normal priority

        # Pin to a non-zero CPU core (core 0 often handles interrupts)
        cpu_count = psutil.cpu_count()
        if cpu_count and cpu_count > 1:
            # Use second-to-last core (usually less busy than core 0)
            target_core = max(1, cpu_count - 2)
            proc.cpu_affinity([target_core])

        return True
    except ImportError:
        # psutil not available, skip priority/affinity settings
        return False
    except Exception:
        return False


def stabilize_cpu_frequency(positions, get_board, duration_seconds=1.0):
    """Run workload for a fixed duration to stabilize CPU frequency."""
    end_time = time.perf_counter() + duration_seconds
    while time.perf_counter() < end_time:
        for fen in positions:
            board = get_board("standard", fen)
            list(board.legal_moves)


def main():
    positions_file = Path(sys.argv[1])
    warmup = int(sys.argv[2])
    rounds = int(sys.argv[3])
    iterations = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    # Set high priority and CPU affinity for stable measurements
    priority_set = set_high_priority_and_affinity()

    positions = json.loads(positions_file.read_text())["positions"]

    from draughts import get_board

    # Pre-clean FENs once
    clean_positions = []
    for fen in positions:
        if fen.startswith("B:B:") or fen.startswith("W:W:"):
            fen = fen[2:]
        clean_positions.append(fen)

    # Extended warmup: run for 1 second to stabilize CPU frequency
    stabilize_cpu_frequency(clean_positions, get_board, duration_seconds=1.0)

    # Additional warmup rounds
    for _ in range(warmup):
        for fen in clean_positions:
            board = get_board("standard", fen)
            list(board.legal_moves)

    # Run multiple iterations, each with multiple rounds
    # This keeps everything in one process for consistent measurements
    iteration_medians = []

    for _ in range(iterations):
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
        iteration_medians.append(median(times) * 1000)

    result = {
        "iteration_medians": iteration_medians,
        "median_ms": median(iteration_medians),
        "positions_count": len(clean_positions),
        "high_priority": priority_set,
        # Keep backward compatibility
        "times": [m / 1000 for m in iteration_medians],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
