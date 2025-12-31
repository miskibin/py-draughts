from __future__ import annotations

from enum import Enum, IntEnum
from typing import NewType

import numpy as np

STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
SquareT = NewType("SquareT", int)


class Color(Enum):
    WHITE = -1
    BLACK = 1


class Figure(IntEnum):
    BLACK_KING = Color.BLACK.value * 2
    BLACK_MAN = Color.BLACK.value
    WHITE_KING = Color.WHITE.value * 2
    WHITE_MAN = Color.WHITE.value
    KING = 2
    MAN = 1
    EMPTY = 0


# Pre-cached values to avoid enum lookup overhead in hot paths
EMPTY = Figure.EMPTY.value  # 0
MAN = Figure.MAN.value      # 1
KING = Figure.KING.value    # 2


FIGURE_REPR = {
    Figure.BLACK_MAN: "b",
    Figure.WHITE_MAN: "w",
    Figure.EMPTY: ".",
    Figure.BLACK_KING: "B",
    Figure.WHITE_KING: "W",
}
