from __future__ import annotations

"""
**Board for Standard (international) checkers.**
*Still in development.*
"""

from typing import Generator

import numpy as np
from collections import defaultdict
from checkers.base import BaseBoard
from checkers.models import Color, Entity
from checkers.move import Move
from checkers.utils import (
    logger,
    get_king_pseudo_legal_moves,
    get_man_pseudo_legal_moves,
)


# fmt: off
SQUARES=  [ B10, D10, F10, H10, J10,
            A9, C9, E9, G9, I9,
            B8, D8, F8, H8, J8, 
            A7, C7, E7, G7, I7,
            B6, D6, F6, H6, J6,
            A5, C5, E5, G5, I5,
            B4, D4, F4, H4, J4,
            A3, C3, E3, G3, I3,
            B2, D2, F2, H2, J2,
            A1, C1, E1, G1, I1] = range(50)
# fmt: on


class Board(BaseBoard):
    """
    **Board for Standard (international) checkers.**
     Game rules:

     - Board size: 10x10
     - Any piece can capture backwards and forwards
     - Capture is mandatory
     - King can move along the diagonal any number of squares
    """

    GAME_TYPE = 20
    STARTING_POSITION = np.array([1] * 15 + [0] * 20 + [-1] * 15, dtype=np.int8)
    row_idx = {val: val // 5 for val in range(len(STARTING_POSITION))}
    col_idx = {val: val % 10 for val in range(len(STARTING_POSITION))}
    PSEUDO_LEGAL_KING_MOVES = get_king_pseudo_legal_moves(len(STARTING_POSITION))
    PSEUDO_LEGAL_MAN_MOVES = get_man_pseudo_legal_moves(len(STARTING_POSITION))

    def __init__(self, starting_position=STARTING_POSITION) -> None:
        super().__init__(starting_position)

    @property
    def legal_moves(self) -> Generator[Move, None, None]:
        squares_list = np.transpose(np.nonzero(self._pos*self.turn.value > 0))
        for square in squares_list.flatten():
            moves = self._legal_moves_from(square)
            for move in moves:
                yield move

    def _legal_moves_from(
        self, square: int, is_after_capture=False
    ) -> Generator[Move, None, None]:
        ...


if __name__ == "__main__":
    board = Board()
    from pprint import pprint

    pprint(board)
    pprint(board.PSEUDO_LEGAL_KING_MOVES)
