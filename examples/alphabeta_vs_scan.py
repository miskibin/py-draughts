"""
Example: AlphaBeta engine vs Scan engine (Hub protocol)

This script plays a game between the built-in AlphaBeta engine and
an external Scan engine using the Hub protocol.

Usage:
    python alphabeta_vs_scan.py [path_to_scan.exe]

Requirements:
    - Scan draughts engine (https://hjetten.home.xs4all.nl/scan/scan.html)
"""

import sys
from pathlib import Path
from loguru import logger
import sys

logger.add(sys.stderr, level="DEBUG")

from draughts import StandardBoard, Color
from draughts.engines import AlphaBetaEngine
from draughts.engines import HubEngine


def play_game(scan_path: str, max_moves: int = 100) -> None:
    """
    Play a game between AlphaBeta (White) and Scan (Black).
    
    Args:
        scan_path: Path to the Scan executable
        max_moves: Maximum number of moves before declaring a draw
    """
    board = StandardBoard()
    
    # AlphaBeta plays White
    alphabeta = AlphaBetaEngine(depth_limit=9)
    
    # Scan plays Black
    print(f"Starting Scan engine from: {scan_path}")
    
    with HubEngine(scan_path, time_limit=1.0) as scan:
        scan.new_game()
        
        print("\n=== Game Start ===")
        print(f"White: AlphaBeta (depth_limit=9)")
        print(f"Black: {scan.info.name} {scan.info.version}")
        print()
        
        move_count = 0
        
        while not board.game_over and move_count < max_moves:
            move_count += 1
            
            if board.turn == Color.WHITE:
                # AlphaBeta's turn
                move, score = alphabeta.get_best_move(board, with_evaluation=True)
                print(f"{move_count}. White (AlphaBeta): {move} (eval: {score:+.2f})")
            else:
                # Scan's turn
                move, score = scan.get_best_move(board, with_evaluation=True)
                print(f"   Black (Scan):     {move} (eval: {score:+.2f})")
            
            board.push(move)
        
        print("\n=== Game Over ===")
        print(f"Total moves: {move_count}")
        
        if board.is_draw:
            print("Result: Draw")
        elif not list(board.legal_moves):
            winner = "Black" if board.turn == Color.WHITE else "White"
            print(f"Result: {winner} wins!")
        else:
            print("Result: Draw (max moves reached)")
        
        print("\nFinal position:")
        print(board.fen)


def main():
    # Default path or from command line
    if len(sys.argv) > 1:
        scan_path = sys.argv[1]
        # add scan_path to sys.path
        sys.path.insert(0, str(Path(scan_path).parent))
    else:
        # Try common locations
        candidates = [
            "scan.exe",
            "./scan.exe",
            "../scan.exe",
            "C:/Games/Scan/scan.exe",
        ]
        scan_path = None
        for candidate in candidates:
            if Path(candidate).exists():
                scan_path = candidate
                break
        
        if scan_path is None:
            print("Usage: python alphabeta_vs_scan.py <path_to_scan.exe>")
            print("\nScan engine not found. Please provide the path to scan.exe")
            print("Download Scan from: https://hjetten.home.xs4all.nl/scan/scan.html")
            sys.exit(1)
    
    if not Path(scan_path).exists():
        print(f"Error: Scan engine not found at: {scan_path}")
        sys.exit(1)
    
    play_game(scan_path)


if __name__ == "__main__":
    main()
