from __future__ import annotations
import numpy as np
from fast_checkers.utils import logger
from typing import List
from fast_checkers.models import Entity, Square, MoveOffsets
from typing import NewType, Generator
from fast_checkers.board import Board, STARTING_POSITION, Move
from colorama import Fore, Style
from time import sleep


class Game:
    def __init__(self, position=STARTING_POSITION) -> None:
        self.board = Board(position)
        self.moves_stack = []

    def play_random(self):
        while True:
            moves = list(self.board.legal_moves)
            move = moves[np.random.randint(0, len(moves))]
            self.move(move)
            self._show_board()
            sleep(9.5)

    def move(self, move: Move) -> None:
        self.board.move(move)
        self.moves_stack.append(move)

    def _show_board(self):
        source = self.moves_stack[-1][0] if self.moves_stack else None  # color green
        target = self.moves_stack[-1][1] if self.moves_stack else None  # color red
        print(f"last move: {self.moves_stack[-1]}")
        items_repr = {
            Entity.BLACK: "| X ",
            Entity.WHITE: "| O ",
            Entity.EMPTY: "|   ",
        }
        pos = self.board.friendly_form
        for row in range(8):
            print(f"\n{'-' * 34}")
            for col in range(8):
                if (row, (col - (row % 2)) // 2) == target.value:
                    print(Fore.RED + items_repr[pos[row][col]] + Fore.RESET, end="")
                elif (row, (col - (row % 2)) // 2) == source.value:
                    print(Fore.GREEN + items_repr[pos[row][col]] + Fore.RESET, end="")
                else:
                    print(items_repr[pos[row][col]], end="")
            print(f"|", end="")
        print("\n")


game = Game()
game.play_random()
