#!/usr/bin/env python
"""
Persistent worker for engine moves. Stays alive and reads commands from stdin.

Protocol:
- Input: JSON lines with commands:
  - {"cmd": "new_game", "fen": "..."} - Start new game from position (resets board state)
  - {"cmd": "move", "depth": N} - Get best move for current position
  - {"cmd": "apply_move", "move": "32-28"} - Apply opponent's move to our board
  - {"cmd": "quit"} - Exit worker
- Output: JSON lines with result

This avoids Python startup overhead (~500ms) per move and preserves board state
for proper draw detection (halfmove clock, threefold repetition).
"""

import json
import sys
import time

# Import once at startup
from draughts import get_board
from draughts.engines import AlphaBetaEngine
from draughts.move import Move

# Persistent board state across moves in same game
current_board = None


def handle_new_game(fen: str | None) -> dict:
    """Start a new game from given position."""
    global current_board
    current_board = get_board("standard", fen) if fen else get_board("standard")
    return {
        "status": "ok",
        "fen": current_board.fen,
        "game_over": current_board.game_over,
        "result": current_board.result if current_board.game_over else None,
    }


def handle_apply_move(move_str: str) -> dict:
    """Apply opponent's move to our board."""
    global current_board
    
    if current_board is None:
        return {"error": "No game started. Call new_game first."}
    
    try:
        move = Move.from_uci(move_str, current_board.legal_moves)
        current_board.push(move)
        return {
            "status": "ok",
            "fen": current_board.fen,
            "game_over": current_board.game_over,
            "result": current_board.result if current_board.game_over else None,
        }
    except ValueError as e:
        return {"error": f"Invalid move: {e}"}


def handle_move(depth: int) -> dict:
    """Process a single move request using persistent board."""
    global current_board
    
    if current_board is None:
        return {"error": "No game started. Call new_game first."}
    
    if current_board.game_over:
        return {
            "move": None,
            "fen": current_board.fen,
            "game_over": True,
            "result": current_board.result,
            "nodes": 0,
            "time_ms": 0,
        }
    
    engine = AlphaBetaEngine(depth_limit=depth)
    start = time.perf_counter()
    move = engine.get_best_move(current_board)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    if move:
        move_str = str(move)
        current_board.push(move)
        return {
            "move": move_str,
            "fen": current_board.fen,
            "game_over": current_board.game_over,
            "result": current_board.result if current_board.game_over else None,
            "nodes": engine.inspected_nodes,
            "time_ms": elapsed_ms,
        }
    else:
        return {
            "move": None,
            "fen": current_board.fen,
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
        elif cmd.get("cmd") == "new_game":
            fen = cmd.get("fen") or None
            try:
                result = handle_new_game(fen)
                print(json.dumps(result), flush=True)
            except Exception as e:
                print(json.dumps({"error": f"new_game exception: {e}"}), flush=True)
        elif cmd.get("cmd") == "apply_move":
            move_str = cmd.get("move", "")
            try:
                result = handle_apply_move(move_str)
                print(json.dumps(result), flush=True)
            except Exception as e:
                print(json.dumps({"error": f"apply_move exception: {e}"}), flush=True)
        elif cmd.get("cmd") == "move":
            depth = cmd.get("depth", 3)
            try:
                result = handle_move(depth)
                print(json.dumps(result), flush=True)
            except Exception as e:
                print(json.dumps({"error": f"handle_move exception: {e}"}), flush=True)
        else:
            print(json.dumps({"error": f"unknown command: {cmd.get('cmd')}"}), flush=True)


if __name__ == "__main__":
    main()
