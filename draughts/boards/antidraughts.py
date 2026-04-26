"""
Antidraughts (Losing Draughts) - 10x10 board with International rules but
inverted win condition.

Subclass of StandardBoard. The only difference is the result: the player
who runs out of pieces or has no legal moves WINS instead of losing.
All movement and capture rules (including mandatory max-capture) are
identical to Standard.
"""

from __future__ import annotations

from typing import Literal

from draughts.boards.standard import Board as StandardBoard
from draughts.models import Color


class Board(StandardBoard):
    """
    Antidraughts (also called Losing Draughts).

    - 10×10 board, 50 squares (inherits geometry from Standard)
    - Same movement, captures and max-capture rule as Standard
    - WIN condition: be the first to lose all pieces or have no legal moves
    """

    GAME_TYPE = 20
    VARIANT_NAME = "Antidraughts"

    @property
    def result(self) -> Literal["1/2-1/2", "1-0", "0-1", "-"]:
        if self.is_draw:
            return "1/2-1/2"
        if not self.legal_moves:
            return "1-0" if self.turn == Color.WHITE else "0-1"
        return "-"
