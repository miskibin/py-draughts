"""Profile legal_moves to find bottlenecks."""
import cProfile
import pstats
from io import StringIO
from draughts.boards.standard import Board

def run_benchmark():
    positions = [
        '[FEN "W:W28,33,34,38,39,43,44,48,49,50:B5,6,7,8,9,10,14,15,19,20"]',
        '[FEN "W:WK10:B14,15,24,25"]',  # King with multiple captures
        '[FEN "W:W31,32,33,34,35:B16,17,18,19,20"]',
    ]
    
    for _ in range(200):
        for fen in positions:
            board = Board.from_fen(fen)
            list(board.legal_moves)

if __name__ == "__main__":
    pr = cProfile.Profile()
    pr.enable()
    run_benchmark()
    pr.disable()
    
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(25)
    print(s.getvalue())
