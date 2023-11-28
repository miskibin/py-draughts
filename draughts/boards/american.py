from __future__ import annotations

from typing import Generator

import numpy as np

from draughts.boards.base import BaseBoard
from draughts.models import Color, Figure
from draughts.move import Move

# fmt: off
SQUARES = [B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1] = range(32)
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

    GAME_TYPE = 23
    STARTING_COLOR = Color.WHITE
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    VARIANT_NAME = "American checkers"
    ROW_IDX = {val: val // 4 for val in range(len(STARTING_POSITION))}
    COL_IDX = {val: val % 8 for val in range(len(STARTING_POSITION))}

    size = int(np.sqrt(len(STARTING_POSITION) * 2))

    @property
    def is_draw(self) -> bool:
        return self.is_threefold_repetition

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

    def _legal_moves_from(
        self, square: int, is_after_capture=False
    ) -> Generator[Move, None, None]:
        row = self.ROW_IDX[square]
        moves = []
        odd = bool(row % 2 != 0 and self.turn == Color.BLACK) or (
            row % 2 == 0 and self.turn == Color.WHITE
        )
        is_king = bool(self[square] == self.turn.value * Figure.KING)
        # is_king = False  # DEBUG
        for mv_offset, cap_offset, dir in [
            (4 - odd, 7, self.turn.value),
            (5 - odd, 9, self.turn.value),
        ] + is_king * [
            (4 - (not odd), 7, -self.turn.value),
            (5 - (not odd), 9, -self.turn.value),
        ]:
            move_sq = square + mv_offset * (dir)
            capture_sq = square + cap_offset * (dir)

            if (
                0 <= move_sq < len(self._pos)
                and row + 1 * (dir) == self.ROW_IDX[move_sq]
                and self[move_sq] == 0
                and not is_after_capture
            ):
                moves.append(Move([square, move_sq]))
            elif (
                0 <= capture_sq < len(self._pos)
                and row + 2 * (dir) == self.ROW_IDX[capture_sq]
                and self[capture_sq] == 0
                and self[move_sq] * self.turn.value < 0
            ):
                move = Move(
                    [square, capture_sq],
                    captured_list=[move_sq],
                    captured_entities=[self[move_sq]],
                )
                moves.append(move)
                self.push(move, False)
                moves += [move + m for m in self._legal_moves_from(capture_sq, True)]
                self.pop(False)

        return moves


if __name__ == "__main__":
    board = Board()
    for i in range(10):
        # random move
        move = np.random.choice(list(board.legal_moves))
        board.push(move)

    print(board.pdn)
