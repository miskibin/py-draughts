"""
Breakthrough Draughts - 10x10 board with International rules but the first
side to make a king wins.

Subclass of StandardBoard. Movement and captures are identical to Standard,
but the game ends as soon as either player promotes a man.
"""

from __future__ import annotations

from typing import Literal

from draughts.boards.standard import Board as StandardBoard


class Board(StandardBoard):
    """
    Breakthrough Draughts.

    - 10×10 board, 50 squares (inherits geometry from Standard)
    - Same movement, captures and max-capture rule as Standard
    - WIN condition: first player to promote a man (create a king) wins
    """

    GAME_TYPE = 20
    VARIANT_NAME = "Breakthrough"

    @property
    def game_over(self) -> bool:
        if self.white_kings or self.black_kings:
            return True
        return self.is_draw or not self.legal_moves

    @property
    def result(self) -> Literal["1/2-1/2", "1-0", "0-1", "-"]:
        if self.white_kings:
            return "1-0"
        if self.black_kings:
            return "0-1"
        return super().result
