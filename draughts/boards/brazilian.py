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
        return self._legal_moves_from_core(_CORE, max_capture=True)
