from __future__ import annotations

import numpy as np

from draughts.base import BaseBoard
from draughts.models import Figure
from draughts.move import Move
from draughts.utils import (get_king_pseudo_legal_moves,
                            get_man_pseudo_legal_moves)

# fmt: off
SQUARES=  [ B10, D10, F10, H10, J10,
            A9, C9, E9, G9, I9,
            B8, D8, F8, H8, J8, 
            A7, C7, E7, G7, I7,
            B6, D6, F6, H6, J6,
            A5, C5, E5, G5, I5,
            B4, D4, F4, H4, J4,
            A3, C3, E3, G3, I3,
            B2, D2, F2, H2, J2,
            A1, C1, E1, G1, I1] = range(50)
# fmt: on


class Board(BaseBoard):
    """
    **Board for Standard (international) checkers.**
     Game rules:

     - Board size: 10x10
     - Any piece can capture backwards and forwards
     - Capture is mandatory
     - King can move along the diagonal any number of squares
    """

    GAME_TYPE = 20
    STARTING_POSITION = np.array([1] * 15 + [0] * 20 + [-1] * 15, dtype=np.int8)
    PSEUDO_LEGAL_KING_MOVES = get_king_pseudo_legal_moves(len(STARTING_POSITION))
    PSEUDO_LEGAL_MAN_MOVES = get_man_pseudo_legal_moves(len(STARTING_POSITION))

    def __init__(self, starting_position=STARTING_POSITION) -> None:
        super().__init__(starting_position)

    @property
    def legal_moves(self) -> list[Move]:
        all_moves = []
        is_capture_mandatory = False
        squares_list = np.transpose(np.nonzero(self._pos * self.turn.value > 0))
        for square in squares_list.flatten():
            moves = self._legal_moves_from(square, is_capture_mandatory)
            # if not is_capture_mandatory and any( # TODO this should optimize the search
            #     [len(move.square_list) > 0 for move in moves]
            # ):
            #     is_capture_mandatory = True
            all_moves.extend(moves)
        if any([len(move.captured_list) > 0 for move in all_moves]):
            all_moves = [move for move in all_moves if len(move.captured_list) > 0]
        return all_moves

    def _get_man_legal_moves_from(
        self, square: int, is_capture_mandatory: bool
    ) -> list:
        moves = []
        # white can move only on even directions
        for idx, direction in enumerate(self.PSEUDO_LEGAL_MAN_MOVES[square]):
            if (
                len(direction) > 0
                and (self.turn.value + idx)
                in [-1, 0, 3, 4]  # TERRIBLE HACK get only directions for given piece
                and self._pos[direction[0]] == Figure.EMPTY
                and not is_capture_mandatory
            ):
                moves.append(Move([square, direction[0]]))
            elif (
                len(direction) > 1
                and self._pos[direction[0]] * self.turn.value < 0
                and self._pos[direction[1]] == Figure.EMPTY
            ):
                move = Move(
                    [square, direction[1]], [direction[0]], [self._pos[direction[0]]]
                )
                moves.append(move)
                self.push(move, False)
                moves += [move + m for m in self._legal_moves_from(direction[1], True)]
                self.pop(False)
        return moves

    def _get_king_legal_moves_from(
        self, square: int, is_capture_mandatory: bool
    ) -> list[Move]:
        moves = []
        for direction in self.PSEUDO_LEGAL_KING_MOVES[square]:
            for idx, target in enumerate(direction):
                if (
                    len(direction) > idx + 1
                    and self._pos[target] * self.turn.value < 0
                    and self._pos[direction[idx + 1]] == Figure.EMPTY
                ):
                    i = idx + 1
                    while (
                        i < len(direction) and self._pos[direction[i]] == Figure.EMPTY
                    ):
                        move = Move(
                            [square, direction[i]], [target], [self._pos[target]]
                        )
                        moves.append(move)
                        self.push(move, False)
                        moves += [
                            move + m for m in self._legal_moves_from(direction[i], True)
                        ]
                        # if one move is longer then others return only this one
                        self.pop(False)
                        max_len = max([len(m) for m in moves])
                        moves = [m for m in moves if len(m) == max_len]
                        i += 1
                    break
                if (
                    self._pos[target] == Figure.EMPTY.value and not is_capture_mandatory
                ):  # casual move
                    moves.append(Move([square, target]))
                else:
                    break
        return moves

    def _legal_moves_from(self, square: int, is_capture_mandatory=False) -> list[Move]:
        entity = Figure(self._pos[square])
        if abs(entity) == Figure.MAN:
            moves = self._get_man_legal_moves_from(square, is_capture_mandatory)
        else:
            moves = self._get_king_legal_moves_from(square, is_capture_mandatory)
        if is_capture_mandatory:
            moves = [move for move in moves if len(move.captured_list) > 0]
        return moves


if __name__ == "__main__":
    board = Board()

    b = Board.from_fen("B:B:WG8,18,24,28,34,37,42,44,49:B2,10,12,15,25,26")
    print(b)
    Board.from_fen("W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32")
