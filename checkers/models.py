from __future__ import annotations

from typing import NewType, Generator
import numpy as np
from enum import Enum, IntEnum
from checkers.utils import logger

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
        visited_squares: list[int],
        captured_list: list[int] = [],
        captured_entities: list[Entity.value] = [],
    ) -> None:
        self.square_list = visited_squares
        self.captured_list = captured_list
        self.captured_entities = captured_entities

    def __repr__(self) -> str:
        return f"Move through squares: {[s + 1 for s in self.square_list ]}"

    def __eq__(self, other: object) -> bool:
        """Check if two moves are equal. move created from string will have only visited squares definied."""
        if not isinstance(other, Move):
            return False

        if (
            self.square_list[0] == other.square_list[0]
            and self.square_list[-1] == other.square_list[-1]
        ):
            longer = (
                self.square_list
                if len(self.square_list) >= len(other.square_list)
                else other.square_list
            )
            shorter = (
                self.square_list
                if len(self.square_list) < len(other.square_list)
                else other.square_list
            )

            return all(square in longer for square in shorter)

        return False

    def __add__(self, other: Move) -> Move:
        """Append moves"""
        if self.square_list[-1] != other.square_list[0]:
            raise ValueError(
                f"Cannot append moves {self} and {other}. Last square of first move should be equal to first square of second move."
            )
        return Move(
            self.square_list + other.square_list[1:],
            self.captured_list + other.captured_list,
            self.captured_entities + other.captured_entities,
        )

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
            raise ValueError(f"Invalid move {move}.")

        move = Move([int(step) - 1 for step in steps])
        for legal_move in legal_moves:
            if legal_move == move:
                return legal_move
        raise ValueError(
            f"{move} is correct, but not legal in given position.\n Legal moves are: {list(legal_moves)}"
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
