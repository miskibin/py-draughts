from __future__ import annotations
import numpy as np
from fast_checkers.utils import logger
from typing import List
from fast_checkers.models import Entity, Square, MoveOffsets
from typing import NewType, Generator

Move = NewType("Move", tuple[Square, Square])
Moves = NewType("Moves", List[tuple[Square, Square]])

# shape is (4, 8) because we want to have the same coordinates as in the book
STARTING_POSITION = np.array(
    [
        [1, 1, 1, 1],
        [1, 1, 1, 1],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [-1, -1, -1, -1],
        [-1, -1, -1, -1],
        [-1, -1, -1, -1],
    ],
    dtype=np.int8,
).T  # we transpose it because we want to have the same coordinates as in the book


class Board:
    """
    Checkers board. It is worth mentioning that board is really just a 8x4 array.
    On dark squares there are pieces, on light squares pieces can't be placed.
    Therefore just draw them, but not store them.
    """

    __slots__ = (
        "__position",
        "__relative_position",
        "turn",
    )

    def __init__(self, position: np.ndarray = STARTING_POSITION) -> None:
        if position.shape != (4, 8) or position.dtype != np.int8:
            msg = f"Invalid board with shape {position.shape} provided. Please use a 8x4 np.int8 array."
            logger.error(msg)
            raise ValueError(msg)
        self.__relative_position = position.copy()
        self.turn = Entity.WHITE

    # position getter

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        if self.turn == Entity.BLACK:
            return np.flip(self.__relative_position, axis=1)[::-1]
        return self.__relative_position

    @property
    def legal_moves(self) -> Generator[Move, None, None]:
        """Returns a generator of legal moves for the player."""

        if self.turn == Entity.BLACK:
            squares_list = np.transpose(
                np.nonzero(self.__relative_position == Entity.BLACK)
            )

        else:
            squares_list = np.transpose(
                np.nonzero(self.__relative_position == Entity.WHITE)
            )

        for square in squares_list:
            target_sqs = self._legal_moves_from_square(square)
            for tg in target_sqs:
                if self.turn == Entity.BLACK:
                    yield Square(tuple(square)).reversed, Square(tg).reversed
                else:
                    yield Square(tuple(square)), Square(tg)

    def _legal_moves_from_square(self, sq: tuple) -> Moves:
        target_sqs = []
        x, y = tuple(sq)
        offset = MoveOffsets(x, y)
        if (
            offset.MOVE_LEFT
            and self.__relative_position[offset.MOVE_LEFT] == Entity.EMPTY
        ):
            target_sqs.append(offset.MOVE_LEFT)

        if (
            offset.MOVE_RIGHT
            and self.__relative_position[offset.MOVE_RIGHT] == Entity.EMPTY
        ):
            target_sqs.append(offset.MOVE_RIGHT)

        if (
            offset.CAPTURE_LEFT
            and self.__relative_position[offset.CAPTURE_LEFT] == Entity.EMPTY
            and self.__relative_position[offset.MOVE_LEFT] == -self.turn
        ):
            target_sqs.append(offset.CAPTURE_LEFT)

        if (
            offset.CAPTURE_RIGHT
            and self.__relative_position[offset.CAPTURE_RIGHT] == Entity.EMPTY
            and self.__relative_position[offset.MOVE_RIGHT] == -self.turn
        ):
            target_sqs.append(offset.CAPTURE_RIGHT)
        return target_sqs

    def move(self, move: Move) -> None:
        """Moves a piece from one square to another."""
        if self.turn == Entity.BLACK:
            source, target = move[0].reversed.value, move[1].reversed.value
        else:
            source, target = tuple(move[0].value), tuple(move[1].value)

        self.__relative_position[target] = self.__relative_position[source]
        self.__relative_position[source] = Entity.EMPTY
        if target[1] - source[1] > 1:
            offset = MoveOffsets(*source)
            if target == offset.CAPTURE_LEFT:
                self.__relative_position[offset.MOVE_LEFT] = Entity.EMPTY
            elif target == offset.CAPTURE_RIGHT:
                self.__relative_position[offset.MOVE_RIGHT] = Entity.EMPTY
            else:
                raise ValueError(f"Invalid capture move from {source} to {target}")
        self.turn = -self.turn
        self.__relative_position = np.flip(self.__relative_position, axis=1)[::-1]

    @property
    def friendly_form(self) -> np.ndarray:
        pos = self.position.copy()
        new_pos = np.zeros((8, 8), dtype=np.int8)
        for col_idx in range(8):
            for row_idx in range(8):
                if (col_idx + row_idx) % 2 == 0:
                    new_pos[col_idx, row_idx] = pos[col_idx // 2][row_idx]
        return new_pos.T

    def __repr__(self) -> str:
        items_repr = {
            Entity.BLACK: "X",
            Entity.WHITE: "O",
            Entity.EMPTY: " ",
        }
        representation = ""
        pos = self.friendly_form
        for row in pos[::-1]:
            representation += f"| "
            for col in row:
                representation += f"{items_repr[col]} | "
            representation += f"\n {'-' * 34}\n"
        return representation

    def __getitem__(self, key: tuple[int, int] | Square | np.ndarray | int) -> Entity:
        if isinstance(key, np.ndarray):
            key = tuple(key)
        if isinstance(key, int):
            key = (key // 4, key % 8)
        if isinstance(key, Square):
            key = key.value
        # raise error if key is negative
        if key[0] < 0 or key[1] < 0:
            raise IndexError(f"Index {key} is out of bounds.")
        return self.position[key[0], key[1]]


if __name__ == "__main__":
    board = Board()
    from pprint import pprint
    from time import sleep

    # play random game
    while True:
        print(board)
        sleep(1.5)
        moves = list(board.legal_moves)
        # move = moves[np.random.randint(0, len(moves))]
        move = (Square.A3, Square.B4)
        board.move(move)
