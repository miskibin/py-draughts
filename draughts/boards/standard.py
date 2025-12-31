from __future__ import annotations
import types
from typing import Any
import numpy as np
from draughts.boards.base import BaseBoard
from draughts.models import Color, Figure
from draughts.move import Move
from draughts.utils import (
    get_diagonal_moves,
    get_short_diagonal_moves,
    logger,
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
    **Board for Standard (international) checkers.**

    Game rules:

    - Board size: 10x10
    - Any piece can capture backwards and forwards
    - Capture is mandatory
    - King can move along the diagonal any number of squares

    **Winning and drawing**

    - A player wins the game when the opponent no longer has any valid moves.
      This can be either because all of the player's pieces have been captured,
      or because they are all blocked and thus have no more squares available.
    - If the same position appears on the board for the third time,
      with the same side to move, the game is considered drawn by threefold repetition.
    - The game is drawn when both players make 25 consecutive king moves without capturing.
      When one player has only a king left, and the other player three pieces including at least
      one king (three kings, two kings and a man, or one king and two men),
      the game is drawn after both players made 16 moves.
    - When one player has only a king left, and the other player two pieces
      or less including at least one king (one king, two kings, or one king and a man),
      the game is drawn after both players made 5 moves.

    """

    GAME_TYPE = 20
    STARTING_POSITION = np.array([1] * 20 + [0] * 10 + [-1] * 20, dtype=np.int8)
    STARTING_COLOR = Color.WHITE
    VARIANT_NAME = "Standard (international) checkers"

    ROW_IDX = {val: val // 5 for val in range(len(STARTING_POSITION))}
    COL_IDX = {val: val % 10 for val in range(len(STARTING_POSITION))}

    # def __init__(
    #     self, starting_position=STARTING_POSITION, turn=STARTING_COLOR, *args, **kwargs
    # ) -> None:
    #     super().__init__(starting_position, turn, *args, **kwargs)

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
            # if not is_capture_mandatory and any( # TODO this should optimize the search
            #     [len(move.square_list) > 0 for move in moves]
            # ):
            #     is_capture_mandatory = True
            all_moves.extend(moves)
        return [mv for mv in all_moves if len(mv) == max(len(m) for m in all_moves)]

    def _get_man_legal_moves_from(
        self, square: int, is_capture_mandatory: bool
    ) -> list:
        moves = []
        # white can move only on even directions
        for idx, direction in enumerate(self.DIAGONAL_LONG_MOVES[square]):
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
                # moves.append(move)
                self.push(move, False)
                new_moves = [
                    move + m for m in self._get_man_legal_moves_from(direction[1], True)
                ]
                moves += [move] if len(new_moves) == 0 else new_moves
                self.pop(False)
        return moves

    def _get_king_legal_moves_from(
        self, square: int, is_capture_mandatory: bool
    ) -> list[Move]:
        moves = []
        for direction in self.DIAGONAL_SHORT_MOVES[square]:
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
                            move + m
                            for m in self._get_king_legal_moves_from(direction[i], True)
                        ]
                        # if one move is longer then others return only this one
                        self.pop(False)
                        max_len = max([len(m) for m in moves])
                        moves = [m for m in moves if len(m) == max_len]
                        i += 1
                    break
                if self._pos[target] == Figure.EMPTY.value:
                    if not is_capture_mandatory:
                        # casual move - only when not in capture chain
                        moves.append(Move([square, target]))
                    # Continue searching for capturable pieces further along diagonal
                else:
                    # Any piece (own or enemy without landing space) blocks the path
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
    # board = Board()
    # for i in range(10):
    #     # random move
    #     move = np.random.choice(list(board.legal_moves))
    #     board.push(move)
#     pdn = """
# [GameType \"20\"]\n1. 33-28 18-23 2. 39-33 13-18 3. 44-39 18-22 4. 31-27 22x31 5. 36x27 8-13 6. 50-44 2-8 7. 41-36 20-24 8. 34-29 23x34 9. 40x20 14x25 10. 46-41 10-14 11. 44-40 5-10 12. 39-34 17-21 13. 43-39 21-26 14. 49-43 12-17 15. 27-21 16x27 16. 32x12 7x18 17. 37-32 11-16 18. 41-37 1-7 19. 37-31 26x37 20. 42x31 7-11 21. 31-27 14-20 22. 47-42 10-14 23. 42-37 20-24 24. 27-21 16x27 25. 32x21 8-12 26. 21-16 3-8 27. 16x7 12x1 28. 37-32 8-12 29. 28-23 19x37 30. 34-30 25x34 31. 39x17 14-19 32. 43-39 1-7 33. 38-32 37x28 34. 33x24 9-13 35. 40-34 4-9 36. 34-30 9-14 37. 30-25 13-18 38. 17-12 18-22 39. 12x1 22-27 40. 48-42 6-11 41. 1-23 11-17 42. 23x5 17-21 43. 5-37 21-26 44. 39-34 15-20 45. 24x15 26-31 46. 37x26 27-32 47. 42-37 32x41 48. 36x47 2-0
#     """
#     board = Board.from_pdn(pdn)

#     print(board.pdn)
    board = Board.from_fen('[FEN "W:B:WK2,28,31,44:B20,K50"])')
    print(board)
    print(board.legal_moves)