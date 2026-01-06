from __future__ import annotations

from typing import Generator

import numpy as np

from draughts.boards.base import BaseBoard
from draughts.models import Color, Figure, EMPTY, MAN, KING
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
        # Use flatnonzero for faster piece lookup
        turn_val = self.turn.value
        squares_list = np.flatnonzero(self._pos * turn_val > 0)
        for square in squares_list:
            moves = self._legal_moves_from(square)
            for move in moves:
                yield move

    def _legal_moves_from(
        self, square: int, is_after_capture=False
    ) -> list[Move]:
        """
        Generate legal moves using pre-computed attack tables.
        American checkers: men can only capture forward, kings can capture in all directions.
        """
        moves = []
        pos = self._pos
        turn_val = self.turn.value
        piece_val = abs(pos[square])
        is_king = piece_val == KING
        
        # Use pre-computed attack tables
        attack_table = self.WHITE_MAN_ATTACKS if turn_val < 0 else self.BLACK_MAN_ATTACKS
        
        if is_king:
            # Kings can move and capture in all directions using KING_DIAGONALS
            for direction in self.KING_DIAGONALS[square]:
                if len(direction) >= 1:
                    target = direction[0]
                    # Regular move (not after capture)
                    if pos[target] == EMPTY and not is_after_capture:
                        moves.append(Move([square, target]))
                    # Capture
                    if len(direction) >= 2:
                        jump_over = direction[0]
                        land_on = direction[1]
                        if pos[jump_over] * turn_val < 0 and pos[land_on] == EMPTY:
                            move = Move(
                                [square, land_on],
                                captured_list=[jump_over],
                                captured_entities=[pos[jump_over]],
                            )
                            moves.append(move)
                            self.push(move, False)
                            moves += [move + m for m in self._legal_moves_from(land_on, True)]
                            self.pop(False)
        else:
            # Men use attack table (forward moves only, but can capture forward)
            for entry in attack_table[square]:
                target = entry.target
                jump_over = entry.jump_over
                land_on = entry.land_on
                
                # Regular move (only forward, not after capture)
                if target >= 0 and not is_after_capture:
                    if pos[target] == EMPTY:
                        moves.append(Move([square, target]))
                
                # Capture move (men can only capture forward in American checkers)
                if jump_over >= 0 and land_on >= 0:
                    if pos[jump_over] * turn_val < 0 and pos[land_on] == EMPTY:
                        move = Move(
                            [square, land_on],
                            captured_list=[jump_over],
                            captured_entities=[pos[jump_over]],
                        )
                        moves.append(move)
                        self.push(move, False)
                        moves += [move + m for m in self._legal_moves_from(land_on, True)]
                        self.pop(False)
        
        return moves


if __name__ == "__main__":
    board = Board()
    for i in range(10):
        # random move
        move = np.random.choice(list(board.legal_moves))
        board.push(move)

    print(board.pdn)
