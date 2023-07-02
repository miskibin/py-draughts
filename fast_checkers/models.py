from __future__ import annotations
from typing import Any
import numpy as np
from enum import Enum, IntEnum
from fast_checkers.utils import logger

from functools import cached_property


class Square(Enum):
    A1 = (0, 0)
    A3 = (0, 2)
    A5 = (0, 4)
    A7 = (0, 6)
    B2 = (0, 1)
    B4 = (0, 3)
    B6 = (0, 5)
    B8 = (0, 7)
    C1 = (1, 0)
    C3 = (1, 2)
    C5 = (1, 4)
    C7 = (1, 6)
    D2 = (1, 1)
    D4 = (1, 3)
    D6 = (1, 5)
    D8 = (1, 7)
    E1 = (2, 0)
    E3 = (2, 2)
    E5 = (2, 4)
    E7 = (2, 6)
    F2 = (2, 1)
    F4 = (2, 3)
    F6 = (2, 5)
    F8 = (2, 7)
    G1 = (3, 0)
    G3 = (3, 2)
    G5 = (3, 4)
    G7 = (3, 6)
    H2 = (3, 1)
    H4 = (3, 3)
    H6 = (3, 5)
    H8 = (3, 7)

    @cached_property
    def as_np(self):
        return np.array(self.value)

    @cached_property
    def reversed(self):
        # (0, 0) -> (3, 7)
        return Square((3 - self.value[0], 7 - self.value[1]))


class Entity(IntEnum):
    BLACK = -1
    WHITE = 1
    EMPTY = 0


class MoveOffsets:
    def __init__(self, x, y) -> None:
        temp_x = x + y % 2
        self.CAPTURE_LEFT = self._get_valid_offset(x + 1, y + 2)
        self.CAPTURE_RIGHT = self._get_valid_offset(x - 1, y + 2)
        self.MOVE_LEFT = self._get_valid_offset(temp_x, y + 1)
        self.MOVE_RIGHT = self._get_valid_offset(temp_x - 1, y + 1)

    def _get_valid_offset(self, x, y):
        return (x, y) if self._is_offset_valid(x, y) else None

    def _is_offset_valid(self, x, y) -> bool:
        return 0 <= x < 4 and 0 <= y < 8

    def __str__(self) -> str:
        string = ""
        for k, v in self.__dict__.items():
            string += f"{k}: {v}\n"
        return string
