"""
Standard (International) Draughts - 10x10 board, flying kings, mandatory max captures.
"""

from __future__ import annotations

import numpy as np

from draughts.boards._core import CORE_STANDARD as _CORE
from draughts.boards.base import BaseBoard
from draughts.models import Color
from draughts.move import Move

# Bind the generators as module globals so the hot path avoids per-call
# attribute lookups on the core instance.
_to_ghost = _CORE.to_ghost
_gen_captures = _CORE.gen_captures
_gen_quiets = _CORE.gen_quiets

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
        wm = _to_ghost(self.white_men)
        wk = _to_ghost(self.white_kings)
        bm = _to_ghost(self.black_men)
        bk = _to_ghost(self.black_kings)
        white = self.turn == Color.WHITE

        raw = _gen_captures(wm, wk, bm, bk, white)
        if raw:
            # Mandatory maximum capture: keep only the longest chains.
            best = 0
            for _, caps, _promo in raw:
                if len(caps) > best:
                    best = len(caps)
            get = self._get
            moves = [
                Move(list(path), list(caps), [get(c) for c in caps], promo)
                for path, caps, promo in raw
                if len(caps) == best
            ]
            return self._dedupe_captures(moves)

        return [Move([frm, to]) for frm, to in _gen_quiets(wm, wk, bm, bk, white)]

    @property
    def is_draw(self) -> bool:
        return (
            self.is_25_moves_rule
            or self.is_threefold_repetition
            or self.is_5_moves_rule
            or self.is_16_moves_rule
        )

    @property
    def is_25_moves_rule(self) -> bool:
        """Draw after 25 king moves (50 half-moves) without capture."""
        return self.halfmove_clock >= 50

    @property
    def is_16_moves_rule(self) -> bool:
        """Draw after 16 moves in specific endgames (≤4 pieces, ≥3 kings)."""
        if self.halfmove_clock < 32 or self._popcount(self._all()) > 4:
            return False
        return (
            self._popcount(self.white_kings | self.black_kings) * 2
            + self._popcount(self.white_men | self.black_men)
            >= 6
        )

    @property
    def is_5_moves_rule(self) -> bool:
        """Draw after 5 moves in specific endgames (≤3 pieces, ≥2 kings)."""
        if self._popcount(self._all()) > 3:
            return False
        return (
            self._popcount(self.white_kings | self.black_kings) * 2
            + self._popcount(self.white_men | self.black_men)
            >= 5
            and self.halfmove_clock >= 10
        )
