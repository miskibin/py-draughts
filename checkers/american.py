from __future__ import annotations

from typing import Generator

import numpy as np

from checkers.base import BaseBoard
from checkers.models import Color
from checkers.move import Move
from checkers.utils import logger

"""
 board 8x8
 Short moves only 
 Cannot capture backwards
 Capture - choose any
"""

# fmt: off
SQUARES = [_, B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1] = range(33)
# fmt: on


class Board(BaseBoard):
    """
    **Board for American checkers.**
     Game rules:

     - Board size: 8x8
     - Short moves only
     - Only the king can capture backwards
     - Capture - choose any
    """

    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    size = int(np.sqrt(len(STARTING_POSITION) * 2))
    row_idx = {val: val // 4 for val in range(len(STARTING_POSITION))}
    col_idx = {val: val % 8 for val in range(len(STARTING_POSITION))}

    def __init__(self) -> None:
        super().__init__(Board.STARTING_POSITION)

    @property
    def legal_moves(self) -> Generator[Move, None, None]:
        if self.turn == Color.BLACK:
            squares_list = np.transpose(np.nonzero(self._pos > 0))
        else:
            squares_list = np.transpose(np.nonzero(self._pos < 0))

        for square in squares_list.flatten():
            moves = self._legal_moves_from(square)
            for move in moves:
                yield move

    def _legal_moves_from(self, square: int) -> Generator[Move, None, None]:
        row = self.row_idx[square]
        moves = []
        odd = (row % 2 != 0 and self.turn == Color.BLACK) or (
            row % 2 == 0 and self.turn == Color.WHITE
        )
        for move_offset, capture_offset in [(4 - odd, 7), (5 - odd, 9)]:
            move_square = square + move_offset * (self.turn.value)
            capture_square = square + capture_offset * (self.turn.value)

            if (
                0 <= move_square < len(self._pos)
                and row + 1 * (self.turn.value) == self.row_idx[move_square]
                and self[move_square] == 0
            ):
                moves.append(Move([square, move_square]))
            elif (
                0 <= capture_square < len(self._pos)
                and row + 2 * (self.turn.value) == self.row_idx[capture_square]
                and self[capture_square] == 0
                and self[move_square] * self.turn.value < 0
            ):
                move = Move(
                    [square, capture_square],
                    captured_list=[move_square],
                    captured_entities=[self[move_square]],
                )
                moves.append(move)
                self.push(move, False)
                moves += [move + m for m in self._legal_moves_from(capture_square)]
                self.pop(False)

        return moves


if __name__ == "__main__":
    board = Board()
    board.push_from_str("24-19")
    board.push_from_str("12-16")
    board.push_from_str("23-18")
    # from copy import deepcopy

    # logger.info(
    #     f"stack: {len(board._moves_stack)} turn: {board.turn}, num_moves: {len(list(board.legal_moves))}, num_of_white: {len(np.where(board._pos == -1)[0])}, num_of_black: {len(np.where(board._pos == 1)[0])}"
    # )
    # logger.info(
    #     f"stack: {len(board._moves_stack)} turn: {board.turn}, num_moves: {len(list(board.legal_moves))}, num_of_white: {len(np.where(board._pos == -1)[0])}, num_of_black: {len(np.where(board._pos == 1)[0])}"
    # )
    # print(b2.__dict__)
    # print(board.__dict__)
    board.push_from_str("16-23")
    print(board)
    # while True:
    #     moves = board.legal_moves
    #     move = np.random.choice(list(moves))
    #     board.push(move)
    #     print(move)
    #     print(board)
    #     from time import sleep

    #     sleep(2)
