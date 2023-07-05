from __future__ import annotations
import numpy as np
from checkers.utils import logger
from checkers.models import (
    Entity,
    ENTITY_REPR,
    STARTING_POSITION,
    ENTITY_MAP,
    Color,
    Move,
    SquareT,
)
import checkers
from typing import Generator, Literal
from abc import ABC, abstractmethod
import warnings


class BaseBoard(ABC):
    """
    The class is designed to support checkers boards of any size.
    The shape attribute, represented as a tuple (rows, columns),
    enables dynamic configuration of the board's dimensions.
    """

    SQUARES_MAP: checkers.T10X10 | checkers.T8X8 = checkers.T8X8

    def __init__(self, position: np.ndarray = STARTING_POSITION) -> None:
        super().__init__()
        self._pos = position.copy()
        size = int(np.sqrt(len(self.position) * 2))
        if size**2 != len(self.position) * 2:
            msg = f"Invalid board with shape {position.shape} provided.\
                Please use an array with lenght = (n * n/2). \
                Where n is an size of the board."
            logger.error(msg)
            raise ValueError(msg)
        self.shape = (size, size)
        self.turn = Color.WHITE
        self._moves_stack: list[Move] = []
        logger.info(f"Board initialized with shape {self.shape}.")

    # @abstractmethod
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
        if move.captured_list:
            self._pos[
                np.array([self.SQUARES_MAP[sq] for sq in move.captured_list])
            ] = Entity.EMPTY
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
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        for sq, is_king in zip(move.captured_list, move.captured_entities):
            self._pos[sq] = ENTITY_MAP[(self.turn, is_king)]
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK
        return move

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

    m1 = Move([checkers.C3, checkers.B4])
    board.push(m1)

    m2 = Move([checkers.B6, checkers.A5])
    board.push(m2)

    m3 = Move([checkers.G3, checkers.H4])
    board.push(m3)
    print(board)

    m4 = Move([checkers.A5, checkers.C3], captured_list=[checkers.B4])
    board.push(m4)
    print(board)
    checkers.SQUARES = range(51)
    print(checkers.SQUARES)
