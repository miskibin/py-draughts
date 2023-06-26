from __future__ import annotations
import numpy as np
from utils import logger
from typing import List
from models import Entity, Square, MOVE

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

    __slots__ = ("_position", "turn")

    def __init__(self, position: np.ndarray = STARTING_POSITION) -> None:
        if position.shape != (8, 4) or position.dtype != np.int8:
            msg = f"Invalid board with shape {position.shape} provided. Please use a 8x4 np.int8 array."
            logger.error(msg)
            raise ValueError(msg)
        self._position = position
        self.turn = Entity.WHITE

    @property
    def legal_moves(self) -> List[tuple[Square, Square]]:
        """Returns a list of legal moves for the player."""
        moves = []
        for square in Square:
            moves += self._legal_moves_from_square(square)
        return moves

    def _legal_moves_from_square(self, sq: Square) -> List[tuple[Square, Square]]:
        logger.info(f"Checking moves from {sq.value}")
        target_sqs = []
        try:
            if self[target := sq.as_np + MOVE.MOVE_LEFT.as_np] == Entity.EMPTY:
                target_sqs.append(target)
            if self[target := sq.as_np + MOVE.MOVE_RIGHT.as_np] == Entity.EMPTY:
                target_sqs.append(target)

            # if (
            #     self[square.as_np + MOVE_TYPE.CAPTURE_LEFT.as_np] == Entity.EMPTY
            #     and self[square.as_np + (1, 0)] == -self.turn
            # ):
            #     moves.append(square.as_np, square.as_np + MOVE_TYPE.CAPTURE_LEFT.as_np)

            # if (
            #     self[square.as_np + MOVE_TYPE.CAPTURE_RIGHT.as_np] == Entity.EMPTY
            #     and self[square.as_np + (1, 1)] == -self.turn
            # ):
            #     moves.append(square.as_np, square.as_np + MOVE_TYPE.CAPTURE_RIGHT.as_np)

            # map all moves to Square
        except (IndexError, ValueError) as e:
            logger.debug(f"Error while checking moves from {sq.value}: {e}")
            pass  # TODO We should not try to move outside the board

        return [(sq, Square(tuple(tg))) for tg in target_sqs]

    def move(self, move: tuple[Square, Square]) -> None:
        """Moves a piece from one square to another."""
        source, target = move
        self[target] = self[source]
        self[source] = Entity.EMPTY
        self.turn = Entity.WHITE if self.turn == Entity.BLACK else Entity.BLACK

    @property
    def friendly_form(self) -> np.ndarray:
        pos = list(self._position.copy())
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
        return self._position[key[0], key[1]]

    def __setitem__(self, key: tuple[int, int] | Square, value: Entity) -> None:
        if isinstance(key, Square):
            key = key.value
            self._position[key // 8, key % 8] = value
        else:
            self._position[key] = value

    def __copy__(self) -> Board:
        return Board(self._position.copy())


if __name__ == "__main__":
    board = Board()
    from pprint import pprint

    pprint(board.legal_moves)
    # print(board._position)

    # a = np.array([[1, 2, 3], [None, 5, 6]])
    # print(np.argwhere(a == 5))
