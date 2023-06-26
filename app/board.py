from __future__ import annotations
import numpy as np
from utils import logger
from typing import List
from models import Entity, Square, Move
from typing import NewType, Generator

MoveType = NewType("MoveType", tuple[int, int])
Moves = NewType("Moves", List[tuple[Square, Square]])
# STARTING_POSITION = np.array(
#     [
#         [1, 0, 1, 0, 1, 0, 1, 0],
#         [0, 1, 0, 1, 0, 1, 0, 1],
#         [1, 0, 1, 0, 1, 0, 1, 0],
#         [0, 0, 0, 0, 0, 0, 0, 0],
#         [0, 0, 0, 0, 0, 0, 0, 0],
#         [0, -1, 0, -1, 0, -1, 0, -1],
#         [-1, 0, -1, 0, -1, 0, -1, 0],
#         [0, -1, 0, -1, 0, -1, 0, -1],
#     ],
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
)


class Board:
    """
    Checkers board. It is worth mentioning that board is really just a 8x4 array.
    On dark squares there are pieces, on light squares pieces can't be placed.
    Therefore just draw them, but not store them.
    """

    __slots__ = (
        "__position",
        "turn",
    )

    def __init__(self, position: np.ndarray = STARTING_POSITION) -> None:
        if position.shape != (8, 4) or position.dtype != np.int8:
            msg = f"Invalid board with shape {position.shape} provided. Please use a 8x4 np.int8 array."
            logger.error(msg)
            raise ValueError(msg)
        self.__position = position
        self.turn = Entity.WHITE

    # position getter

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self.__position

    @property
    def legal_moves(self) -> Generator[MoveType, None, None]:
        """Returns a generator of legal moves for the player."""

        if self.turn == Entity.BLACK:
            position = self.__position[::-1]
            squares_list = np.transpose(np.nonzero(position == Entity.BLACK))
        else:
            position = self.__position
            squares_list = np.transpose(np.nonzero(position == Entity.WHITE))

        for square in squares_list:
            target_sqs = self._legal_moves_from_square(square, position)
            for tg in target_sqs:
                if self.turn == Entity.BLACK:
                    yield Square(tuple(square)).reversed, Square(tg).reversed
                else:
                    yield Square(tuple(square)), Square(tg)

    def _legal_moves_from_square(self, sq: Square, pos: np.ndarray) -> Moves:
        target_sqs = []
        x, y = tuple(sq)
        MOVE = Move(x, y)

        if self._is_sq_valid(MOVE.MOVE_LEFT) and pos[MOVE.MOVE_LEFT] == Entity.EMPTY:
            target_sqs.append(MOVE.MOVE_LEFT)

        if self._is_sq_valid(MOVE.MOVE_RIGHT) and pos[MOVE.MOVE_RIGHT] == Entity.EMPTY:
            target_sqs.append(MOVE.MOVE_RIGHT)

        if (
            self._is_sq_valid(MOVE.CAPTURE_LEFT)
            and pos[MOVE.CAPTURE_LEFT] == Entity.EMPTY
            and pos[(x + 1, y)] == -self.turn
        ):
            target_sqs.append(MOVE.CAPTURE_LEFT)

        if (
            self._is_sq_valid(MOVE.CAPTURE_RIGHT)
            and pos[MOVE.CAPTURE_RIGHT] == Entity.EMPTY
            and pos[(x + 1, y - 1)] == -self.turn
        ):
            target_sqs.append(MOVE.CAPTURE_RIGHT)
        return target_sqs

    def _is_sq_valid(self, sq: Square) -> bool:
        x, y = tuple(sq)
        return 0 <= x < self.__position.shape[0] and 0 <= y < self.__position.shape[1]

    def move(self, move: tuple[Square, Square]) -> None:
        """Moves a piece from one square to another."""
        source, target = move
        self[target] = self[source]
        self[source] = Entity.EMPTY
        self.turn = Entity.WHITE if self.turn == Entity.BLACK else Entity.BLACK

    @property
    def friendly_form(self) -> np.ndarray:
        pos = list(self.__position.copy())
        for row_idx in range(8):
            pos[row_idx] = [
                pos[row_idx][i // 2] if (i + row_idx) % 2 == 0 else 0 for i in range(8)
            ]
        return np.array(pos)

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

    def __getitem__(self, key: tuple[int, int] | Square | np.ndarray) -> Entity:
        if isinstance(key, np.ndarray):
            key = tuple(key)
        if isinstance(key, Square):
            key = key.value
        # raise error if key is negative
        if key[0] < 0 or key[1] < 0:
            raise IndexError(f"Index {key} is out of bounds.")
        return self.__position[key[0], key[1]]

    def __copy__(self) -> Board:
        return Board(self.__position.copy())


if __name__ == "__main__":
    board = Board()
    from pprint import pprint

    pprint(list(board.legal_moves))
    # print(board._position)

    # a = np.array([[1, 2, 3], [None, 5, 6]])
    # print(np.argwhere(a == 5))
