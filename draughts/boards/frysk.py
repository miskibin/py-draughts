"""
Frysk! Draughts - 10x10 board with Frisian rules but a tiny starting set.

Subclass of FrisianBoard. The only difference is the starting position:
each side has just 5 men, placed on their back rank. All movement,
capture and king rules are inherited from Frisian.
"""

from __future__ import annotations

import numpy as np

from draughts.boards.frisian import Board as FrisianBoard


class Board(FrisianBoard):
    """
    Frysk! Draughts.

    - 10×10 board, 50 squares (inherits geometry from Frisian)
    - Same Frisian movement, captures and king rules
    - Starting position: 5 men per side on the back rank (squares 0-4 for
      black, 45-49 for white)
    """

    GAME_TYPE = 40
    VARIANT_NAME = "Frysk!"
    STARTING_POSITION = np.array(
        [1] * 5 + [0] * 40 + [-1] * 5,
        dtype=np.int8,
    )

    def _init_default_position(self) -> None:
        self.black_men = (1 << 5) - 1
        self.black_kings = 0
        self.white_men = ((1 << 5) - 1) << 45
        self.white_kings = 0
