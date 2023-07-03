from __future__ import annotations
import numpy as np
from fast_checkers.utils import logger
from fast_checkers.models import (
    Entity,
    Square,
    MovesChain,
    ENTITY_REPR,
    STARTING_POSITION,
    Color,
    Move,
)
from typing import Generator
from abc import ABC, abstractmethod
import warnings


class BaseBoard(ABC):
    """
    The class is designed to support checkers boards of any size.
    The shape attribute, represented as a tuple (rows, columns),
    enables dynamic configuration of the board's dimensions.


    """

    def __init__(self, position: np.ndarray = STARTING_POSITION) -> None:
        super().__init__()
        self.__position = position.copy()
        size = int(np.sqrt(len(self.position) * 2))
        if size**2 != len(self.position) * 2:
            msg = f"Invalid board with shape {position.shape} provided.\
                Please use an array with lenght = (n * n/2). Where n is an size of the board."
            logger.error(msg)
            raise ValueError(msg)
        self.shape = (size, size)
        self.turn = Color.WHITE
        self._moves_stack: list[MovesChain] = []
        logger.info(f"Board initialized with shape {self.shape}.")

    def legal_moves(self) -> Generator[MovesChain, None, None]:
        pass

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self.__position

    def push(self, move: MovesChain) -> None:
        """Pushes a move to the board."""
        for step in move.steps:
            self.__position[step.from_], self.__position[step.to] = (
                Entity.EMPTY,
                self.__position[step.from_],
            )
            if step.captured:
                self.__position[step.captured] = Entity.EMPTY
        self._moves_stack.append(move)
        self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK

    def pop(self) -> None:
        """Pops a move from the board."""
        move = self._moves_stack.pop()
        for step in reversed(move.steps):
            self.__position[step.from_] = self.__position[step.to]
            self.__position[step.to] = Entity.EMPTY
            if step.captured:
                self.__position[step.captured] = step.captured_entity
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
        return new_pos

    def __repr__(self) -> str:
        board = ""
        position = self.friendly_form
        self.shape[0]
        for i in range(self.shape[0]):
            board += f"{'-' * (self.shape[0]*4 + 1) }\n|"
            for j in range(self.shape[0]):
                board += f" {ENTITY_REPR[position[i*self.shape[0] + j]]} |"
            board += "\n"
        return board

    def __iter__(self) -> Generator[Entity, None, None]:
        for sq in self.position:
            yield sq

    def __getitem__(self, key: Square) -> Entity:
        return self.position[key.index]


if __name__ == "__main__":
    board = BaseBoard(STARTING_POSITION)
    print(board)
    m1 = MovesChain([Move(Square(22).index, Square(17).index)])
    board.push(m1)
    m2 = MovesChain([Move(Square(9).index, Square(13).index)])
    board.push(m2)
    m2 = MovesChain([Move(Square(24).index, Square(20).index)])
    board.push(m2)
    m2 = MovesChain([Move(Square(13).index, Square(22).index, Square(17).index)])
    board.push(m2)
    print(board)
