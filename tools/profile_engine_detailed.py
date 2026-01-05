"""Detailed profile of engine to find bottlenecks."""
import cProfile
import pstats
from io import StringIO
from draughts.boards.standard import Board
from draughts.engines import AlphaBetaEngine

def run_benchmark(depth=4):
    """Run benchmark with configurable depth."""
    # Test with starting position
    board = Board()
    engine = AlphaBetaEngine(depth_limit=depth)
    
    # Get one move at specified depth
    move = engine.get_best_move(board)
    print(f"Depth: {depth}")
    print(f"Best move: {move}, nodes inspected: {engine.inspected_nodes}")

def run_mid_game_benchmark(depth=4):
    """Run benchmark from a mid-game position with more complexity."""
    # A mid-game position with captures possible
    fen = '[FEN "W:W27,28,29,30,31,32,33,34,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20"]'
    board = Board()
    
    # Make a few moves to get to a more interesting position
    for _ in range(6):
        moves = list(board.legal_moves)
        if moves:
            board.push(moves[0])
    
    engine = AlphaBetaEngine(depth_limit=depth)
    print(f"\nMid-game position (after 6 moves):")
    print(board)
    
    move = engine.get_best_move(board)
    print(f"Depth: {depth}")
    print(f"Best move: {move}, nodes inspected: {engine.inspected_nodes}")

def profile_legal_moves():
    """Profile just legal moves generation."""
    board = Board()
    # Make some moves to get interesting position
    for _ in range(8):
        moves = list(board.legal_moves)
        if moves:
            board.push(moves[0])
    
    print("\nProfiling 1000 legal_moves calls:")
    for _ in range(1000):
        _ = list(board.legal_moves)

if __name__ == "__main__":
    import sys
    
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    
    print("=" * 60)
    print("PROFILING ENGINE AT DEPTH", depth)
    print("=" * 60)
    
    pr = cProfile.Profile()
    pr.enable()
    
    # Run the benchmark
    run_benchmark(depth)
    run_mid_game_benchmark(depth)
    
    pr.disable()
    
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(40)
    print("\n" + "=" * 60)
    print("CUMULATIVE TIME PROFILE")
    print("=" * 60)
    print(s.getvalue())
    
    # Also sort by total time
    s2 = StringIO()
    ps2 = pstats.Stats(pr, stream=s2).sort_stats('tottime')
    ps2.print_stats(30)
    print("\n" + "=" * 60)
    print("TOTAL TIME (self-time) PROFILE")
    print("=" * 60)
    print(s2.getvalue())
    
    # Print callers for key functions
    print("\n" + "=" * 60)
    print("WHO CALLS legal_moves THE MOST")
    print("=" * 60)
    s3 = StringIO()
    ps3 = pstats.Stats(pr, stream=s3)
    ps3.print_callers('legal_moves')
    print(s3.getvalue())
