#!/usr/bin/env python
"""
Persistent worker for engine moves. Stays alive and reads commands from stdin.

Protocol:
- Input: JSON lines with {"cmd": "move", "fen": "...", "depth": N} or {"cmd": "quit"}
- Output: JSON lines with result

This avoids Python startup overhead (~500ms) per move.
"""

import json
import sys
import time

# Import once at startup
from draughts import get_board
from draughts.engines import AlphaBetaEngine


def handle_move(fen: str | None, depth: int) -> dict:
    """Process a single move request."""
    board = get_board("standard", fen) if fen else get_board("standard")
    
    if board.game_over:
        return {
            "move": None,
            "fen": board.fen,
            "game_over": True,
            "result": board.result,
            "nodes": 0,
            "time_ms": 0,
        }
    
    engine = AlphaBetaEngine(depth_limit=depth)
    start = time.perf_counter()
    move = engine.get_best_move(board)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    if move:
        board.push(move)
        return {
            "move": str(move),
            "fen": board.fen,
            "game_over": board.game_over,
            "result": board.result if board.game_over else None,
            "nodes": engine.inspected_nodes,
            "time_ms": elapsed_ms,
        }
    else:
        return {
            "move": None,
            "fen": board.fen,
            "game_over": True,
            "result": "no_move",
            "nodes": 0,
            "time_ms": 0,
        }


def main():
    # Signal ready
    print(json.dumps({"status": "ready"}), flush=True)
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"error": "invalid json"}), flush=True)
            continue
        
        if cmd.get("cmd") == "quit":
            break
        elif cmd.get("cmd") == "move":
            fen = cmd.get("fen") or None
            depth = cmd.get("depth", 3)
            result = handle_move(fen, depth)
            print(json.dumps(result), flush=True)
        else:
            print(json.dumps({"error": f"unknown command: {cmd.get('cmd')}"}), flush=True)


if __name__ == "__main__":
    main()
