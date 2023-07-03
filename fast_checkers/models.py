from __future__ import annotations

from typing import Any, TypeAlias, NewType, Generator
import numpy as np
from enum import Enum, IntEnum
from fast_checkers.utils import logger
from dataclasses import dataclass


STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
SquareT = TypeAlias("SquareT", int)


@dataclass
class MovesChain:
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
    """

    steps: list[(SquareT, SquareT, SquareT)]

    @classmethod
    def from_string(cls, move: str, legal_moves: Generator) -> MovesChain:
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
            if (
                legal_move[0] == steps[0]
                and legal_move[-1] == steps[-1]
                and steps[1:-1] in legal_move[1:-1]
            ):
                return cls(legal_move)
        raise ValueError(
            f"Move {move} is correct, but not legal in given position.\n Legal moves are: {list(legal_moves)}"
        )


class Color(Enum):
    WHITE = -1
    BLACK = 1


class Square(IntEnum):
    """
    For me it will be easier to use notation from chess. (A-H for columns, 1-8 for rows)
    Source: https://webdocs.cs.ualberta.ca/~chinook/play/notation.html
    """

    A2 = 32
    A4 = 31
    A6 = 30
    A8 = 29
    B1 = 28
    B3 = 27
    B5 = 26
    B7 = 25
    C2 = 24
    C4 = 23
    C6 = 22
    C8 = 21
    D1 = 20
    D3 = 19
    D5 = 18
    D7 = 17
    E2 = 16
    E4 = 15
    E6 = 14
    E8 = 13
    F1 = 12
    F3 = 11
    F5 = 10
    F7 = 9
    G2 = 8
    G4 = 7
    G6 = 6
    G8 = 5
    H1 = 4
    H3 = 3
    H5 = 2
    H7 = 1


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
