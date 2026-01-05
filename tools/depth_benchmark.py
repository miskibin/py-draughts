#!/usr/bin/env python
"""
Benchmark engine performance at different depths (1-12).
Shows average time per move for each depth.
"""

import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from draughts.boards.standard import Board
from draughts.engines import AlphaBetaEngine


# Test positions - mix of opening, midgame, and endgame
TEST_POSITIONS = [
    None,  # Starting position
    '[FEN "W:W31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20"]',
    '[FEN "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24"]',
    '[FEN "B:W24,28,29,30,33,34,38,39,44,45,49,50:B1,2,6,7,8,12,13,17,18,22,23,27"]',
    '[FEN "W:WK10,K20:BK30,K40"]',  # King endgame
    '[FEN "W:W45,50:B5,10"]',  # Simple endgame
]

MOVES_PER_POSITION = 3  # Number of moves to make per position


def benchmark_depth(depth: int) -> dict:
    """Benchmark engine at given depth, return stats."""
    engine = AlphaBetaEngine(depth_limit=depth)
    
    total_time = 0.0
    total_moves = 0
    total_nodes = 0
    
    for fen in TEST_POSITIONS:
        if fen:
            board = Board.from_fen(fen)
        else:
            board = Board()
        
        for _ in range(MOVES_PER_POSITION):
            if not list(board.legal_moves):
                break
            
            engine.nodes = 0
            start = time.perf_counter()
            move = engine.get_best_move(board)
            elapsed = time.perf_counter() - start
            
            total_time += elapsed
            total_moves += 1
            total_nodes += engine.nodes
            
            board.push(move)
    
    return {
        "depth": depth,
        "total_moves": total_moves,
        "avg_time_ms": (total_time / total_moves * 1000) if total_moves > 0 else 0,
        "avg_nodes": total_nodes // total_moves if total_moves > 0 else 0,
        "total_time": total_time,
    }


def main():
    print("=" * 70)
    print("Engine Depth Benchmark")
    print("=" * 70)
    print(f"Testing {len(TEST_POSITIONS)} positions, {MOVES_PER_POSITION} moves each")
    print()
    print(f"{'Depth':>6} | {'Avg Time':>12} | {'Avg Nodes':>12} | {'Total Time':>12}")
    print("-" * 70)
    sys.stdout.flush()
    
    results = []
    
    for depth in range(1, 13):
        result = benchmark_depth(depth)
        results.append(result)
        
        avg_time = result["avg_time_ms"]
        if avg_time < 1000:
            time_str = f"{avg_time:.2f} ms"
        else:
            time_str = f"{avg_time/1000:.2f} s"
        
        total_time = result["total_time"]
        if total_time < 60:
            total_str = f"{total_time:.2f} s"
        else:
            total_str = f"{total_time/60:.1f} min"
        
        print(f"{depth:>6} | {time_str:>12} | {result['avg_nodes']:>12,} | {total_str:>12}")
        sys.stdout.flush()
        
        # Stop if taking too long (> 30s per move on average)
        if avg_time > 30000:
            print(f"\nStopping - depth {depth} takes > 30s per move")
            break
    
    print("=" * 70)


if __name__ == "__main__":
    main()
