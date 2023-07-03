from __future__ import annotations
import numpy as np
from fast_checkers.utils import logger
from models2 import (
    Entity,
    Square,
    MovesChain,
    ENTITY_REPR,
    STARTING_POSITION,
    Color,
)
from typing import Generator
from abc import ABC, abstractmethod


class BaseBoard(ABC):
    """
    The class is designed to support checkers boards of any size.
    The shape attribute, represented as a tuple (rows, columns),
    enables dynamic configuration of the board's dimensions.


    """

    def __init__(self, position: np.ndarray) -> None:
        super().__init__()
        self.__position = position
        size = int(np.sqrt(len(self.position) * 2))
        if size**2 != len(self.position) * 2:
            msg = f"Invalid board with shape {position.shape} provided.\
                Please use an array with lenght = (n * n/2). Where n is an size of the board."
            logger.error(msg)
            raise ValueError(msg)
        self.shape = (size, size)
        self.turn = Color.WHITE
        logger.info(f"Board initialized with shape {self.shape}.")

    @abstractmethod
    def legal_moves(self) -> Generator[MovesChain, None, None]:
        pass

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self.__position

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
        return self.position[key.value]


if __name__ == "__main__":
    board = BaseBoard(STARTING_POSITION)
    print(board)
