from __future__ import annotations
from checkers.utils import logger
from checkers.models import (
    Entity,
    ENTITY_REPR,
    STARTING_POSITION,
    Color,
    Move,
    SquareT,
)
import checkers
from typing import Generator
from abc import ABC
import numpy as np

# SQUARES = [
#     _, B10, D10, F10, H10, J10,
#     A9, C9, E9, G9, I9,
#     B8, D8, F8, H8, J8,
#     A7, C7, E7, G7, I7,
#     B6, D6, F6, H6, J6,
#     A5, C5, E5, G5, I5,
#     B4, D4, F4, H4, J4,
#     A3, C3, E3, G3, I3,
#     B2, D2, F2, H2, J2,
#     A1, C1, E1, G1, I1
#     ] = range(51)
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


class BaseBoard(ABC):
    """
    The class is designed to support checkers boards of any size.
    The shape attribute, represented as a tuple (rows, columns),
    enables dynamic configuration of the board's dimensions.
    """

    def __init__(self, starting_position: np.ndarray = STARTING_POSITION) -> None:
        super().__init__()
        self._pos = starting_position.copy()
        size = int(np.sqrt(len(self.position) * 2))
        if size**2 != len(self.position) * 2:
            msg = f"Invalid board with shape {starting_position.shape} provided.\
                Please use an array with lenght = (n * n/2). \
                Where n is an size of the board."
            logger.error(msg)
            raise ValueError(msg)
        self.shape = (size, size)
        self.turn = Color.WHITE
        self._moves_stack: list[Move] = []
        logger.info(f"Board initialized with shape {self.shape}.")

    # @abstractmethod
    @property
    def legal_moves(self) -> Generator[Move, None, None]:
        pass

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self._pos

    def push(self, move: Move, is_finished: bool = True) -> None:
        """Pushes a move to the board."""
        src, tg = (
            move.square_list[0],
            move.square_list[-1],
        )
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        logger.debug(
            f"({is_finished}) PUSH METHOD: Moved entity: {Entity(self._pos[tg])} to {tg}"
        )
        if move.captured_list:
            self._pos[np.array([sq for sq in move.captured_list])] = Entity.EMPTY
        self._moves_stack.append(move)
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK

    def pop(self, is_finished=True) -> None:
        """Pops a move from the board."""
        move = self._moves_stack.pop()
        src, tg = (
            move.square_list[0],
            move.square_list[-1],
        )
        logger.debug(f"({is_finished}): Reversing: {Entity(self._pos[tg])} to {tg}")
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        for sq, entity in zip(move.captured_list, move.captured_entities):
            self._pos[sq] = entity  # Dangerous line
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK
        return move

    def push_from_str(self, str_move: str) -> None:
        try:
            move = Move.from_string(str_move, self.legal_moves)
        except ValueError as e:
            logger.error(f"{e} \n {str(self)}")
            raise e
        self.push(move)

    @property
    def friendly_form(self) -> np.ndarray:
        """
        Really tricky method. It is used to print board in a friendly way.
        Designed so it can be used with any board size.
        """
        new_pos = [0]
        for idx, sq in enumerate(self.position):
            new_pos.extend([0] * (idx % (self.shape[0] // 2) != 0))
            new_pos.extend([0, 0] * (idx % self.shape[0] == 0 and idx != 0))
            new_pos.append(sq)
        new_pos.append(0)
        return np.array(new_pos)

    def __repr__(self) -> str:
        board = ""
        position = self.friendly_form
        for i in range(self.shape[0]):
            board += f"{'-' * (self.shape[0]*4 + 1) }\n|"
            for j in range(self.shape[0]):
                board += f" {ENTITY_REPR[position[i*self.shape[0] + j]]} |"
            board += "\n"
        return board

    def __iter__(self) -> Generator[Entity, None, None]:
        for sq in self.position:
            yield sq

    def __getitem__(self, key: SquareT) -> Entity:
        return self.position[key]


if __name__ == "__main__":
    board = BaseBoard(STARTING_POSITION)

    m1 = Move([C3, B4])
    board.push(m1)

    m2 = Move([B6, A5])
    board.push(m2)

    m3 = Move([G3, H4])
    board.push(m3)
    print(board)

    m4 = Move([A5, C3], captured_list=[B4])
    board.push(m4)
    print(board)
    SQUARES = range(51)
    print(SQUARES)
