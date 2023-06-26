from __future__ import annotations
import numpy as np
from enum import Enum, auto, IntEnum
from utils import logger

# import cachedproperty
from functools import cached_property


class Square(Enum):
    A1 = (0, 0)
    A3 = (2, 0)
    A5 = (4, 0)
    A7 = (6, 0)
    B2 = (1, 0)
    B4 = (3, 0)
    B6 = (5, 0)
    B8 = (7, 0)
    C1 = (0, 1)
    C3 = (2, 1)
    C5 = (4, 1)
    C7 = (6, 1)
    D2 = (1, 1)
    D4 = (3, 1)
    D6 = (5, 1)
    D8 = (7, 1)
    E1 = (0, 2)
    E3 = (2, 2)
    E5 = (4, 2)
    E7 = (6, 2)
    F2 = (1, 2)
    F4 = (3, 2)
    F6 = (5, 2)
    F8 = (7, 2)
    G1 = (0, 3)
    G3 = (2, 3)
    G5 = (4, 3)
    G7 = (6, 3)
    H2 = (1, 3)
    H4 = (3, 3)
    H6 = (5, 3)
    H8 = (7, 3)

    @cached_property
    def as_np(self):
        return np.array(self.value)


class Entity(IntEnum):
    BLACK = -1
    WHITE = 1
    EMPTY = 0


class MOVE(Enum):
    CAPTURE_LEFT = (2, 1)
    CAPTURE_RIGHT = (2, -1)
    MOVE_LEFT = (1, 0)
    MOVE_RIGHT = (1, -1)

    @cached_property
    def as_np(self):
        return np.array(self.value)
