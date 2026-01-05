#!/usr/bin/env python
"""Worker script for getting engine move. Run in isolated venv."""

import json
import sys
import time


def main():
    fen = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    from draughts import get_board
    from draughts.engines import AlphaBetaEngine
    
    board = get_board("standard", fen) if fen else get_board("standard")
    
    if board.game_over:
        result = {
            "move": None,
            "fen": board.fen,
            "game_over": True,
            "result": board.result,
            "nodes": 0,
            "time_ms": 0,
        }
    else:
        engine = AlphaBetaEngine(depth_limit=depth)
        start = time.perf_counter()
        move = engine.get_best_move(board)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        if move:
            board.push(move)
            result = {
                "move": str(move),
                "fen": board.fen,
                "game_over": board.game_over,
                "result": board.result if board.game_over else None,
                "nodes": engine.inspected_nodes,
                "time_ms": elapsed_ms,
            }
        else:
            result = {
                "move": None,
                "fen": board.fen,
                "game_over": True,
                "result": "no_move",
                "nodes": 0,
                "time_ms": 0,
            }
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()
