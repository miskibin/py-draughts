"""
Standard (International) Draughts - 10x10 board, flying kings, mandatory max captures.
"""

from __future__ import annotations

import numpy as np

from draughts.boards._core import CORE_STANDARD as _CORE
from draughts.boards._draw import endgame_limits
from draughts.boards.base import BaseBoard
from draughts.models import Color
from draughts.move import Move

# fmt: off
SQUARES = [B10, D10, F10, H10, J10,
A9, C9, E9, G9, I9, B8, D8, F8, H8, J8,
           A7, C7, E7, G7, I7, B6, D6, F6, H6, J6, A5, C5, E5, G5, I5,
           B4, D4, F4, H4, J4, A3, C3, E3, G3, I3, B2, D2, F2, H2, J2,
           A1, C1, E1, G1, I1] = range(50)
# fmt: on

ROW = [((1 << 5) - 1) << (i * 5) for i in range(10)]


class Board(BaseBoard):
    """
    Standard (International) Draughts.

    - 10×10 board, 50 squares
    - Flying kings (move any distance)
    - All pieces capture forwards and backwards
    - Captures mandatory, must take maximum
    """

    GAME_TYPE = 20
    PDN_INTERNATIONAL_RESULT = True
    VARIANT_NAME = "Standard (international) checkers"
    STARTING_COLOR = Color.WHITE
    SQUARES_COUNT = 50
    PROMO_WHITE = ROW[0]
    PROMO_BLACK = ROW[9]
    STARTING_POSITION = np.array([1] * 20 + [0] * 10 + [-1] * 20, dtype=np.int8)
    ROW_IDX = {v: v // 5 for v in range(50)}
    COL_IDX = {v: v % 10 for v in range(50)}

    def _init_default_position(self) -> None:
        self.black_men = (1 << 20) - 1
        self.black_kings = 0
        self.white_men = ((1 << 20) - 1) << 30
        self.white_kings = 0

    @property
    def legal_moves(self) -> list[Move]:
        return self._legal_moves_from_core(_CORE, max_capture=True)

    @property
    def is_draw(self) -> bool:
        drawn = (
            self.is_25_moves_rule
            or self.is_threefold_repetition
            or self.is_5_moves_rule
            or self.is_16_moves_rule
        )
        return drawn and bool(self.legal_moves)

    @property
    def is_25_moves_rule(self) -> bool:
        """Draw after 25 king moves (50 half-moves) without capture."""
        return self.halfmove_clock >= 50

    @property
    def is_16_moves_rule(self) -> bool:
        """FMJD 6.3: three pieces including a king against a lone king."""
        return self._endgame_remaining[0] == 0

    @property
    def is_5_moves_rule(self) -> bool:
        """FMJD 6.4: one/two pieces including a king against a lone king."""
        return self._endgame_remaining[1] == 0

    @property
    def _endgame_remaining(self) -> tuple[int, int]:
        """Reconstruct up to 32 plies of material history without push overhead."""
        if self._all().bit_count() > 4:
            return -1, -1
        counts = [
            self.white_men.bit_count(),
            self.white_kings.bit_count(),
            self.black_men.bit_count(),
            self.black_kings.bit_count(),
        ]
        a, b = endgame_limits(*counts)
        turn = self.turn
        stack = self._moves_stack
        for i in range(1, min(32, len(stack)) + 1):
            move = stack[-i]
            turn = Color.BLACK if turn == Color.WHITE else Color.WHITE
            if move.is_promotion:
                side = 0 if turn == Color.WHITE else 2
                counts[side] += 1
                counts[side + 1] -= 1
            for piece in move.captured_entities:
                counts[(0 if piece < 0 else 2) + (abs(piece) == 2)] += 1
            if sum(counts) > 4:
                break
            old_a, old_b = endgame_limits(*counts)
            if old_a >= 0:
                a = max(0, old_a - i)
            if old_b >= 0:
                b = max(0, old_b - i)
        if self._endgame_start is not None:
            old_a, old_b = self._endgame_start
            if old_a >= 0:
                a = max(0, old_a - len(stack))
            if old_b >= 0:
                b = max(0, old_b - len(stack))
        return a, b
