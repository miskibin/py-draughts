from __future__ import annotations
from typing import Any
import numpy as np
from enum import Enum, IntEnum
from utils import logger

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

    @cached_property
    def reversed(self):
        # (0, 0) -> (7, 3)
        return Square((7 - self.value[0], 3 - self.value[1]))


class Entity(IntEnum):
    BLACK = -1
    WHITE = 1
    EMPTY = 0


class MoveOffsets:
    def __init__(self, x, y) -> None:
        self.CAPTURE_LEFT = self._get_valid_offset(x + 2, y + 1)
        self.CAPTURE_RIGHT = self._get_valid_offset(x + 2, y - 1)
        self.MOVE_LEFT = self._get_valid_offset(x + 1, y + 0)
        self.MOVE_RIGHT = self._get_valid_offset(x + 1, y - 1)

    def _get_valid_offset(self, x, y):
        return (x, y) if self._is_offset_valid(x, y) else None

    def _is_offset_valid(self, x, y) -> bool:
        return 0 <= x < 8 and 0 <= y < 4
