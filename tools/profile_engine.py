"""Profile engine to find bottlenecks."""
import cProfile
import pstats
from io import StringIO
from draughts.boards.standard import Board
from draughts.engine import AlphaBetaEngine

def run_benchmark():
    # Test with starting position and depth=3
    board = Board()
    engine = AlphaBetaEngine(depth=3)
    
    # Just get one move at depth 3 from starting position
    move = engine.get_best_move(board)
    print(f"Best move: {move}, nodes inspected: {engine.inspected_nodes}")

if __name__ == "__main__":
    pr = cProfile.Profile()
    pr.enable()
    run_benchmark()
    pr.disable()
    
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(35)
    print(s.getvalue())
