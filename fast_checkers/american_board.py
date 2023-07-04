from __future__ import annotations
from typing import Generator
from fast_checkers.base_board import BaseBoard
from fast_checkers.models import SQUARES, Square, Move
import numpy as np
"""
 board 8x8
 Short moves only 
 Cannot capture backwards
 Capture - choose any
"""
class AmericanBoard(BaseBoard):
    
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    size =int(np.sqrt(len(STARTING_POSITION) * 2))
    row_idx = { val:val//4 for val in range(len(STARTING_POSITION))}
    col_idx = { val:val%8 for val in range(len(STARTING_POSITION))}
    B8
    SQUARES_MAP = {
        idx:val  for idx,val in enumerate((B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1) )} 

    def legal_moves(self) -> Generator[Move, None, None]:
        moves: list[Move] = []
        
        """
        Standard:
            1  (+4, +5) -> 5,6 
            4 [size//2] (+4)  -> 8
            8 (+4, +5) -> 11, 12
            CHECK IF:
            row(x+4) == row(x) + 1
            row(x+5) == row(x) + 1
        Captures:
            1: (+9) -> 10, !8
            2: (+7, +9) -> 9, 11
            CHECK IF 
            row(x+7) == row(x) + 2
            row(x+9) == row(x) + 2
        """


b= AmericanBoard()