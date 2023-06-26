from __future__ import annotations
import numpy as np
from utils import logger
from typing import List
from models import Entity, Square, MoveOffsets
from typing import NewType, Generator

Move = NewType("Move", tuple[int, int])
Moves = NewType("Moves", List[tuple[Square, Square]])

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
    def legal_moves(self) -> Generator[Move, None, None]:
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
        offset = MoveOffsets(x, y)

        if offset.MOVE_LEFT and pos[offset.MOVE_LEFT] == Entity.EMPTY:
            target_sqs.append(offset.MOVE_LEFT)

        if offset.MOVE_RIGHT and pos[offset.MOVE_RIGHT] == Entity.EMPTY:
            target_sqs.append(offset.MOVE_RIGHT)

        if (
            offset.CAPTURE_LEFT
            and pos[offset.CAPTURE_LEFT] == Entity.EMPTY
            and pos[(x + 1, y)] == -self.turn
        ):
            target_sqs.append(offset.CAPTURE_LEFT)

        if (
            offset.CAPTURE_RIGHT
            and pos[offset.CAPTURE_RIGHT] == Entity.EMPTY
            and pos[(x + 1, y - 1)] == -self.turn
        ):
            target_sqs.append(offset.CAPTURE_RIGHT)
        return target_sqs

    def _is_sq_valid(self, sq: Square) -> bool:
        x, y = tuple(sq)
        return 0 <= x < self.__position.shape[0] and 0 <= y < self.__position.shape[1]

    def move(self, move: Move) -> None:
        """Moves a piece from one square to another."""
        source, target = tuple(move[0].value), tuple(move[1].value)
        self.__position[target] = self.__position[source]
        self.__position[source] = Entity.EMPTY
        if abs(target[0] - source[0]) == 2:
            self.__position[
                (source[0] + target[0]) // 2, (source[1] + target[1]) // 2
            ] = Entity.EMPTY
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

    def __getitem__(self, key: tuple[int, int] | Square | np.ndarray | int) -> Entity:
        if isinstance(key, np.ndarray):
            key = tuple(key)
        if isinstance(key, int):
            key = (key // 8, key % 4)
        if isinstance(key, Square):
            key = key.value
        # raise error if key is negative
        if key[0] < 0 or key[1] < 0:
            raise IndexError(f"Index {key} is out of bounds.")
        return self.__position[key[0], key[1]]


if __name__ == "__main__":
    board = Board()
    from pprint import pprint
    from time import sleep

    # play random game
    while True:
        print(list(board))
        sleep(1.5)
        moves = list(board.legal_moves)
        move = moves[np.random.randint(0, len(moves))]
        board.move(move)
