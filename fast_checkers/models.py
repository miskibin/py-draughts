from __future__ import annotations

from typing import NewType, Generator
import numpy as np
from enum import Enum, IntEnum
from fast_checkers.utils import logger
from dataclasses import dataclass, field

import warnings

# import cached_property
from functools import cached_property

STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
SquareT = NewType("SquareT", int)


@dataclass
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

    square_list: list[int]
    captured_list: list[int] = field(default_factory=list)
    captured_entities: list[bool] =  field(default_factory=list)# wether or not captured piece was king or not

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

SQUARES = [
    _, B10, D10, F10, H10, J10,
    A9, C9, E9, G9, I9,
    B8, D8, F8, H8, J8,
    A7, C7, E7, G7, I7,
    B6, D6, F6, H6, J6,
    A5, C5, E5, G5, I5,
    B4, D4, F4, H4, J4,
    A3, C3, E3, G3, I3,
    B2, D2, F2, H2, J2,
    A1, C1, E1, G1, I1
] = range(51)

T8X8 = {
        val:idx  for idx,val in enumerate((B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1) )} 

T10X10 = {val:idx for idx,val in enumerate(SQUARES)}
class Square(IntEnum):
    """
    For me it will be easier to use notation from chess. (A-H for columns, 1-8 for rows)
    Source: https://webdocs.cs.ualberta.ca/~chinook/play/notation.html
    USE INDEX VAR TO GET INDEX OF THE SQUARE ON BORAD. VALUES ARE SHIFTED BY 1.
    """

    B8 = 1
    D8 = 2
    F8 = 3
    H8 = 4
    A7 = 5
    C7 = 6
    E7 = 7
    G7 = 8
    B6 = 9
    D6 = 10
    F6 = 11
    H6 = 12
    A5 = 13
    C5 = 14
    E5 = 15
    G5 = 16
    B4 = 17
    D4 = 18
    F4 = 19
    H4 = 20
    A3 = 21
    C3 = 22
    E3 = 23
    G3 = 24
    B2 = 25
    D2 = 26
    F2 = 27
    H2 = 28
    A1 = 29
    C1 = 30
    E1 = 31
    G1 = 32

    # overwrite value attribute
    @cached_property
    def index(self) -> int:
        return self.value - 1


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
        (Color.BLACK, True): Entity.BLACK_KING
    }

if __name__ == "__main__":
    print(SQUARES[1])
