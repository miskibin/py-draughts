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
        
        # Pin to first CPU core to avoid migration overhead
        proc.cpu_affinity([0])
        
        return True
    except ImportError:
        # psutil not available, try platform-specific fallbacks
        if sys.platform == "win32":
            try:
                import ctypes
                # Set high priority
                ctypes.windll.kernel32.SetPriorityClass(
                    ctypes.windll.kernel32.GetCurrentProcess(), 
                    0x00000080  # HIGH_PRIORITY_CLASS
                )
                # Set affinity to first core
                ctypes.windll.kernel32.SetProcessAffinityMask(
                    ctypes.windll.kernel32.GetCurrentProcess(),
                    1  # First CPU core
                )
                return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def main():
    positions_file = Path(sys.argv[1])
    warmup = int(sys.argv[2])
    rounds = int(sys.argv[3])
    
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
        "high_priority": priority_set,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
