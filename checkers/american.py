from __future__ import annotations
from typing import Generator
from checkers.base import BaseBoard
from checkers.models import  Move, Color
from checkers.utils import logger
import numpy as np

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
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    size = int(np.sqrt(len(STARTING_POSITION) * 2))
    row_idx = {val: val // 4 for val in range(len(STARTING_POSITION))}
    col_idx = {val: val % 8 for val in range(len(STARTING_POSITION))}

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
        move_right = square + (4 - odd) * (self.turn.value)
        capture_right = square + 7 * (self.turn.value)
        move_left = square + (5 - odd) * (self.turn.value)
        capture_left = square + 9 * (self.turn.value)
        if (
            0 <= move_right < len(self._pos)
            and row + 1 * (self.turn.value) == self.row_idx[move_right]
            and self[move_right] == 0
        ):
            moves.append(Move([square, move_right]))
        elif (
            0 <= capture_right < len(self._pos)
            and row + 2 * (self.turn.value) == self.row_idx[capture_right]
            and self[capture_right] == 0
            and self[move_right] == self.turn.value * -1
        ):
            move = Move(
                [square, capture_right],
                captured_list=[move_right],
                captured_entities=[False],
            )
            moves.append(move)
            self.push(move, False)
            moves += [move + m for m in self._legal_moves_from(capture_right)]
            self.pop(False)
        if (
            0 <= move_left < len(self._pos)
            and row + 1 * (self.turn.value) == self.row_idx[move_left]
            and self[move_left] == 0
        ):
            moves.append(Move([square, move_left]))
        elif (
            0 <= capture_left < len(self._pos)
            and row + 2 * (self.turn.value) == self.row_idx[capture_left]
            and self[capture_left] == 0
            and self[move_left] == self.turn.value * -1
        ):
            move = Move(
                [square, capture_left],
                captured_list=[move_left],
                captured_entities=[False],
            )
            moves.append(move)
            self.push(move, False)
            moves += [move + m for m in self._legal_moves_from(capture_left)]
            self.pop(False)
        return moves


if __name__ == "__main__":
    board = Board()
    print(list(board.legal_moves))
    board.move_from_str("24-19")
    print(board)
    # while True:
    #     moves = board.legal_moves
    #     move = np.random.choice(list(moves))
    #     board.push(move)
    #     print(move)
    #     print(board)
    #     from time import sleep

    #     sleep(2)
