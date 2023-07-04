from __future__ import annotations

from typing import NewType, Generator
import numpy as np
from enum import Enum, IntEnum
from checkers.utils import logger
from dataclasses import dataclass, field

import warnings

# import cached_property
from functools import cached_property

STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
SquareT = NewType("SquareT", int)


class Move:
    """Move representation.
    Since
    ```
    Multiple jumps, such as a double or triple jump,
    require you to pay attention, as the convention is
    to just show the start and end squares and not the
    in-between or intermediate squares. So the notation
    1-3 would mean a King does a double jump from 1 to 10 to 3.
    The intermediate square is only shown if there are two ways
    to jump and it would not be clear otherwise.
    ```
    Note that:
    n - number of visited squares (include source square)
    n - 2 - number of captured pieces
    """

    def __init__(
        self,
        visited_squares: tuple[int],
        captured_list: tuple[int] = (),
        captured_entities: tuple[bool] = (),
    ) -> None:
        self.square_list = visited_squares
        self.captured_list = captured_list
        self.captured_entities = captured_entities

    def __str__(self) -> str:
        return f"Move from {self.square_list[0]} to {self.square_list[-1]}"

    @classmethod
    def from_string(cls, move: str, legal_moves: Generator) -> Move:
        """Converts string representation of move to MovesChain
        Accepted types:
        with `-` separator: eg 1-5
        with `x` separator: eg 1x5
        multiple jumps: eg 1-5-9
        """
        move = move.lower()
        if "-" in move:
            steps = move.split("-")
        elif "x" in move:
            steps = move.split("x")
        else:
            raise ValueError(
                f"Invalid move {move}. Accepted moves <1-32>-<1-32> or <1-32>x<1-32>."
            )
        steps = [int(step) for step in steps]
        for legal_move in legal_moves:
            raise NotImplementedError
        raise ValueError(
            f"Move {move} is correct, but not legal in given position.\n Legal moves are: {list(legal_moves)}"
        )


class Color(Enum):
    WHITE = -1
    BLACK = 1


class Entity(IntEnum):
    BLACK_KING = 10
    BLACK_MAN = 1
    WHITE_KING = -10
    WHITE_MAN = -1
    EMPTY = 0


ENTITY_REPR = {
    Entity.BLACK_MAN: "x",
    Entity.WHITE_MAN: "o",
    Entity.EMPTY: " ",
    Entity.BLACK_KING: "X",
    Entity.WHITE_KING: "O",
}

ENTITY_MAP = {
    (Color.WHITE, False): Entity.WHITE_MAN,
    (Color.WHITE, True): Entity.WHITE_KING,
    (Color.BLACK, False): Entity.BLACK_MAN,
    (Color.BLACK, True): Entity.BLACK_KING,
}

if __name__ == "__main__":
    pass
