"""
Brazilian Draughts - 8x8 board with International (FMJD) rules.

Same geometry as Russian, but:
- Mandatory MAX capture (must take the longest sequence available).
- No mid-capture promotion: a man passing through the king's row during a
  capture chain stays a man until the move finishes; promotion is then applied
  by ``BaseBoard.push``.
"""

from __future__ import annotations

from draughts.boards._core import CORE_BRAZILIAN as _CORE
from draughts.boards.russian import Board as RussianBoard
from draughts.models import Color
from draughts.move import Move


class Board(RussianBoard):
    """
    Brazilian Draughts.

    - 8×8 board, 32 squares (inherits geometry from Russian)
    - Flying kings, men capture in all 4 diagonal directions
    - Captures mandatory and must take the maximum number of pieces
    - Promotion only at the end of a move (no mid-capture promotion)

    GameType 26 per pydraughts/lidraughts convention.
    """

    GAME_TYPE = 26
    VARIANT_NAME = "Brazilian draughts"

    @property
    def legal_moves(self) -> list[Move]:
        to_ghost = _CORE.to_ghost
        wm = to_ghost(self.white_men)
        wk = to_ghost(self.white_kings)
        bm = to_ghost(self.black_men)
        bk = to_ghost(self.black_kings)
        white = self.turn == Color.WHITE

        raw = _CORE.gen_captures(wm, wk, bm, bk, white)
        if raw:
            # Mandatory maximum capture: keep only the longest chains.
            best = 0
            for _, caps, _promo in raw:
                if len(caps) > best:
                    best = len(caps)
            get = self._get
            moves = [
                Move(list(path), list(caps), [get(c) for c in caps])
                for path, caps, _promo in raw
                if len(caps) == best
            ]
            return self._dedupe_captures(moves)
        return [Move([frm, to]) for frm, to in _CORE.gen_quiets(wm, wk, bm, bk, white)]
