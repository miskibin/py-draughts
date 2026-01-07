# mypy: ignore-errors
from __future__ import annotations

import numpy as np
from loguru import logger

from draughts.boards.base import BaseBoard
from draughts.models import Color, Figure
from draughts.move import Move
from draughts.utils import (
    get_short_vertical_and_horizontal_moves,
    get_vertical_and_horizontal_moves,
)

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
    **Board for Frisian draughts.**

    Game rules:

    - Board size: 10x10

    - Besides capturing diagonally, one can also capture horizontally and vertically.
        Every piece can thus capture in eight directions

    - If a king and a man can play a capture sequence of equal value,
        it is always forced to play with the king.

    - If a player has one or more kings on the board but also has one or more men left,
        it is not allowed to play more than three non-capturing moves in a row with the same king.
        If no capture is available for a king after its third non-capturing move,
        one is forced to play with a different king or a man.
        After that one can play any move with that king again,
        but of course again only three times in a row if it doesn't capture.
        This rule does not apply for a player that has no more men left (only kings on the board).

    **Winning and drawing**

    - When one player has two kings and the other player has one king,
        the game is drawn after both players made 7 moves.
    - When both players have one king left, the game is drawn after both players made 2 moves.
        The official rules state that the game is drawn immediately when two kings are left
        unless either player can win by force (which means the other king can be captured immediately
        or will necessarily be captured next move). As we currently can't distinguish the positions
        that win by force on lidraughts, this rule is implemented by always allowing 2 more moves to win the game.
    """

    GAME_TYPE = 40
    STARTING_POSITION = np.array([1] * 20 + [0] * 10 + [-1] * 20, dtype=np.int8)
    STARTING_COLOR = Color.WHITE

    ROW_IDX = {val: val // 5 for val in range(len(STARTING_POSITION))}
    COL_IDX = {val: val % 10 for val in range(len(STARTING_POSITION))}

    @property
    def is_draw(self) -> bool:
        return (
            self.is_threefold_repetition
            or self.is_5_moves_rule
            or self.is_16_moves_rule
            or self.is_25_moves_rule
        )

    @property
    def is_25_moves_rule(self) -> bool:
        if self.halfmove_clock < 50:
            return False
        logger.debug("25 moves rule")
        return True
        # return self.halfmove_clock >= 50

    @property
    def is_16_moves_rule(self) -> bool:
        if self.halfmove_clock < 32:
            return False
        if len(self._pos[self._pos != Figure.EMPTY]) > 4:
            return False
        if np.abs(self._pos).sum() < Figure.KING.value * 2 + Figure.MAN.value * 2:
            return False
        logger.debug("16 moves rule")
        return True

    @property
    def is_5_moves_rule(self) -> bool:
        # if count of pieces is not 3 or 4
        if len(self._pos[self._pos != Figure.EMPTY]) > 3:
            return False
        if np.abs(self._pos).sum() < Figure.KING.value * 2 + Figure.MAN.value:
            return False
        if self.halfmove_clock < 10:
            return False
        logger.debug("5 moves rule")
        return True

    @property
    def legal_moves(self) -> list[Move]:
        all_moves = []
        is_capture_mandatory = False
        squares_list = np.transpose(np.nonzero(self._pos * self.turn.value > 0))
        for square in squares_list.flatten():
            moves = self._legal_moves_from(square, is_capture_mandatory)
            all_moves.extend(moves)

        return all_moves

    def _legal_moves_from(self, square: int | np.intp, is_capture_mandatory=False) -> list[Move]:
        entity = Figure(self._pos[square])
        if abs(entity) == Figure.MAN:
            moves = self._get_man_legal_moves_from(square, is_capture_mandatory)
        else:
            moves = self._get_king_legal_moves_from(square, is_capture_mandatory)
        if is_capture_mandatory:
            moves = [move for move in moves if len(move.captured_list) > 0]
        return moves

    def _get_man_legal_moves_from(
        self, square: int | np.intp, is_captrue_mandatory: bool
    ) -> list[Move]:
        # legal_moves  = self.DIAGONAL_SHORT_MOVES +

        raise NotImplementedError

    def _get_king_legal_moves_from(
        self, square: int | np.intp, is_captrue_mandatory: bool
    ) -> list[Move]:
        raise NotImplementedError


if __name__ == "__main__":
    pass  # Board is abstract - cannot instantiate directly
