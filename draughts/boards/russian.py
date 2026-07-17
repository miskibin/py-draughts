"""
Russian Draughts - 8x8 board, flying kings, men capture backward, free capture choice.

Key differences from other variants:
- 8×8 board (32 squares, like American)
- Men move diagonally forward only
- Men capture both forward AND backward (unlike American)
- Flying kings (move any distance diagonally, like International)
- Free capture choice - NOT required to take maximum captures (unlike International)
- Mid-capture promotion: if a man reaches promotion rank during a capture, it
  immediately becomes a king and continues capturing as a king
- Mandatory captures (must capture if able, but can choose which sequence)
"""

from __future__ import annotations

import numpy as np

from draughts.boards._core import CORE_RUSSIAN as _CORE
from draughts.boards.base import BaseBoard
from draughts.models import Color
from draughts.move import Move

# fmt: off
SQUARES = [B8, D8, F8, H8, A7, C7, E7, G7, B6, D6, F6, H6, A5, C5, E5, G5,
           B4, D4, F4, H4, A3, C3, E3, G3, B2, D2, F2, H2, A1, C1, E1, G1] = range(32)
# fmt: on

# Diagonal ray geometry (board-square indices), shared with Brazilian and used
# by the test suite to verify capture flight paths.
KING_RAYS = _CORE.KING_RAYS


class Board(BaseBoard):
    """
    Russian Draughts.

    - 8×8 board, 32 squares
    - Flying kings (move any distance diagonally)
    - Men capture forward AND backward
    - Captures mandatory, but free choice (NOT max capture rule)
    - Mid-capture promotion (man becomes king during capture sequence)

    GameType 25 per PDN specification.
    """

    GAME_TYPE = 25
    VARIANT_NAME = "Russian draughts"
    STARTING_COLOR = Color.WHITE
    SQUARES_COUNT = 32
    PROMO_WHITE = (1 << 4) - 1
    PROMO_BLACK = ((1 << 4) - 1) << 28
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    ROW_IDX = {v: v // 4 for v in range(32)}
    COL_IDX = {v: v % 8 for v in range(32)}

    # Algebraic notation for PDN parsing
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
        """
        All legal moves for current player.
        In Russian draughts, captures are mandatory but the player may choose ANY
        capture sequence (no maximum-capture rule). A man that reaches the crown
        row mid-chain is flagged as a promotion and continues as a king.
        """
        to_ghost = _CORE.to_ghost
        wm = to_ghost(self.white_men)
        wk = to_ghost(self.white_kings)
        bm = to_ghost(self.black_men)
        bk = to_ghost(self.black_kings)
        white = self.turn == Color.WHITE

        raw = _CORE.gen_captures(wm, wk, bm, bk, white)
        if raw:
            get = self._get
            return [
                Move(list(path), list(caps), [get(c) for c in caps], promo)
                for path, caps, promo in raw
            ]
        return [Move([frm, to]) for frm, to in _CORE.gen_quiets(wm, wk, bm, bk, white)]

    @property
    def is_draw(self) -> bool:
        """
        Check if position is drawn per Russian draughts rules.
        - Threefold repetition
        - 3+ kings vs 1 king: 15 moves (30 half-moves) to win
        - 15 king-only moves without captures (30 half-moves)
        """
        return self.is_threefold_repetition or self.is_15_moves_rule or self.is_3_kings_vs_1_rule

    @property
    def is_15_moves_rule(self) -> bool:
        """
        Draw after 15 king moves without any captures or man moves.
        (30 half-moves of king-only non-capture moves)
        """
        return self.halfmove_clock >= 30

    @property
    def is_3_kings_vs_1_rule(self) -> bool:
        """
        Draw if a player has 3+ kings vs 1 king and fails to win within 15 moves.
        This checks if we're in a 3+ kings vs 1 king endgame.
        """
        white_kings = self._popcount(self.white_kings)
        black_kings = self._popcount(self.black_kings)
        white_men = self._popcount(self.white_men)
        black_men = self._popcount(self.black_men)

        # Only applies when there are no men left
        if white_men > 0 or black_men > 0:
            return False

        # Check for 3+ vs 1 king situation
        if (white_kings >= 3 and black_kings == 1) or (black_kings >= 3 and white_kings == 1):
            return self.halfmove_clock >= 30  # 15 moves = 30 half-moves

        return False
