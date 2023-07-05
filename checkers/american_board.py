from __future__ import annotations
from typing import Generator
from checkers.base_board import BaseBoard
from checkers.models import STARTING_POSITION, Move, Color, Entity
from checkers.utils import logger
import checkers
import numpy as np

"""
 board 8x8
 Short moves only 
 Cannot capture backwards
 Capture - choose any
"""


class AmericanBoard(BaseBoard):
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
    board = AmericanBoard()
    while True:
        moves = board.legal_moves
        move = np.random.choice(list(moves))
        board.push(move)
        print(move)
        print(board)
        from time import sleep

        sleep(2)