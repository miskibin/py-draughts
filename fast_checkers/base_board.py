from __future__ import annotations
import numpy as np
from fast_checkers.utils import logger
from fast_checkers.models import (
    Entity,
    Square,
    ENTITY_REPR,
    STARTING_POSITION,
    ENTITY_MAP,
    SQUARES,
    Color,
    Move,
    SquareT
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
    
    SQUARES_MAP = {idx:val for idx,val in enumerate(SQUARES[1:])}

    def __init__(self, position: np.ndarray = STARTING_POSITION) -> None:
        super().__init__()
        self.__pos = position.copy()
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

    #@abstractmethod
    def legal_moves(self) -> Generator[Move, None, None]:
        pass

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self.__pos

    def push(self, move: Move) -> None:
        """Pushes a move to the board."""
        src, tg = move.square_list[0], move.square_list[-1]
        self.__pos[src], self.__pos[tg] = self.__pos[tg], self.__pos[src]
        if move.captured_list:
            self.__pos[np.array(move.captured_list)] = Entity.EMPTY
        self._moves_stack.append(move)
        self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK

    def pop(self) -> None:
        """Pops a move from the board."""
        move = self._moves_stack.pop()
        src, tg = move.square_list[0], move.square_list[-1]
        self.__pos[src], self.__pos[tg] = self.__pos[tg], self.__pos[src]
        for sq, is_king in zip(move.captured_list, move.captured_entities): 
            self.__pos[sq] = ENTITY_MAP[(self.turn, is_king)]
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
        return self.position[self.SQUARES_MAP[key]]


if __name__ == "__main__":
    board = BaseBoard(STARTING_POSITION)
    print(board)
    m1 = Move(square_list=[Square(22).index, Square(17).index])
    m1 = Move(square_list=[SQUARES[22], SQUARES[17]])
    print(m1)
    board.push(m1)
    print(board)

