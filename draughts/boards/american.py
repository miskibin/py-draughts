"""
American Checkers - 8x8 board, short kings, men capture forward only.
"""

from __future__ import annotations

import numpy as np

from draughts.boards._core import CORE_AMERICAN as _CORE
from draughts.boards.base import BaseBoard
from draughts.models import Color
from draughts.move import Move

# fmt: off
SQUARES = [B8, D8, F8, H8, A7, C7, E7, G7, B6, D6, F6, H6, A5, C5, E5, G5,
           B4, D4, F4, H4, A3, C3, E3, G3, B2, D2, F2, H2, A1, C1, E1, G1] = range(32)
# fmt: on

ROW = [((1 << 4) - 1) << (i * 4) for i in range(8)]


class Board(BaseBoard):
    """
    American Checkers.

    - 8×8 board, 32 squares
    - Short kings (move 1 square)
    - Men capture forward only
    - Captures optional
    """

    GAME_TYPE = 23
    VARIANT_NAME = "American checkers"
    STARTING_COLOR = Color.WHITE
    SQUARES_COUNT = 32
    PROMO_WHITE = ROW[0]
    PROMO_BLACK = ROW[7]
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    ROW_IDX = {v: v // 4 for v in range(32)}
    COL_IDX = {v: v % 8 for v in range(32)}

    # Algebraic notation for PDN parsing (used by playstrategy.org)
    # fmt: off
    SQUARE_NAMES = ['b8', 'd8', 'f8', 'h8', 'a7', 'c7', 'e7', 'g7',
                    'b6', 'd6', 'f6', 'h6', 'a5', 'c5', 'e5', 'g5',
                    'b4', 'd4', 'f4', 'h4', 'a3', 'c3', 'e3', 'g3',
                    'b2', 'd2', 'f2', 'h2', 'a1', 'c1', 'e1', 'g1']
    # fmt: on

    def _init_default_position(self) -> None:
        self.black_men = (1 << 12) - 1
        self.black_kings = 0
        self.white_men = ((1 << 12) - 1) << 20
        self.white_kings = 0

    @property
    def legal_moves(self) -> list[Move]:
        """All legal moves. Captures are NOT mandatory in American checkers, so
        simple moves and captures are both offered (no maximum-capture rule)."""
        return self._legal_moves_from_core(_CORE, max_capture=False, captures_optional=True)

    @property
    def is_draw(self) -> bool:
        """
        Check if the game is a draw.

        Draw conditions:
        - Threefold repetition
        - 40-move rule: 40 consecutive moves without a capture or promotion
        """
        if self.halfmove_clock >= 40:
            return True
        return self.is_threefold_repetition
