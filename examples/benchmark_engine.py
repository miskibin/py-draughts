"""
Benchmark script to demonstrate engine performance improvements.

This script compares the engine's performance with the optimizations:
- Transposition table
- Move ordering
- Enhanced evaluation
"""

from draughts import get_board
from draughts.engine import AlphaBetaEngine
import time


def benchmark_engine():
    """Benchmark engine performance at different depths."""
    board = get_board('standard')
    
    print("=" * 60)
    print("Engine Performance Benchmark")
    print("=" * 60)
    
    depths = [3, 4, 5]
    
    for depth in depths:
        engine = AlphaBetaEngine(depth=depth)
        
        print(f"\nDepth {depth}:")
        print("-" * 40)
        
        start = time.time()
        move, score = engine.get_best_move(board, with_evaluation=True)
        elapsed = time.time() - start
        
        print(f"  Best move:        {move}")
        print(f"  Evaluation:       {score:.2f}")
        print(f"  Time:             {elapsed:.3f}s")
        print(f"  Nodes inspected:  {engine.inspected_nodes:,}")
        print(f"  Positions cached: {len(engine._transposition_table):,}")
    
    print("\n" + "=" * 60)
    print("Optimizations enabled:")
    print("  ✓ Alpha-beta pruning")
    print("  ✓ Move ordering (captures first)")
    print("  ✓ Transposition table")
    print("  ✓ Enhanced evaluation (material + position)")
    print("=" * 60)


def test_move_ordering():
    """Test move ordering effectiveness."""
    print("\n" + "=" * 60)
    print("Move Ordering Test")
    print("=" * 60)
    
    # Position with captures available
    fen = "W:W24,25,26,27,28:B14,15,16,17,18"
    board = get_board("standard", fen)
    engine = AlphaBetaEngine(depth=3)
    
    moves = list(board.legal_moves)
    ordered = engine._order_moves(moves, board)
    
    captures = [m for m in ordered if m.captured_list]
    non_captures = [m for m in ordered if not m.captured_list]
    
    print(f"\nTotal moves: {len(moves)}")
    print(f"Captures:    {len(captures)} (evaluated first)")
    print(f"Regular:     {len(non_captures)} (evaluated second)")
    
    if captures:
        print(f"\nFirst move evaluated: {ordered[0]} (capture)")
    else:
        print(f"\nFirst move evaluated: {ordered[0]} (regular)")
    
    print("=" * 60)


if __name__ == "__main__":
    benchmark_engine()
    test_move_ordering()
