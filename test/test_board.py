import numpy as np
import pytest

import draughts.boards.american as checkers
from draughts.boards.base import BaseBoard, Color, Figure, Move
from draughts import get_board
from draughts.boards.american import Board


class TestBoard:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = get_board("american")
        yield
        del self.board

    def test_init(self):
        assert self.board.turn == Color.WHITE
        assert np.array_equal(self.board.position, Board.STARTING_POSITION)

    # def test_move(self):
    #     m = Move([checkers.A3, checkers.B4])
    #     self.board.push(m)
    #     assert self.board.turn == Color.BLACK
    #     assert self.board[checkers.A3] == Figure.EMPTY
    #     assert self.board[checkers.B4] == Figure.WHITE_MAN
    #     m = Move([checkers.F6, checkers.G5])
    #     self.board.push(m)
    #     assert self.board.turn == Color.WHITE
    #     assert self.board[checkers.F6] == Figure.EMPTY
    #     assert self.board[checkers.G5] == Figure.BLACK_MAN

    # def test_capture(self):
    #     m1 = Move([checkers.C3, checkers.B4])
    #     self.board.push(m1)

    #     m2 = Move([checkers.B6, checkers.A5])
    #     self.board.push(m2)

    #     m3 = Move([checkers.G3, checkers.H4])
    #     self.board.push(m3)

    #     m4 = Move([checkers.A5, checkers.C3], captured_list=[checkers.B4])
    #     self.board.push(m4)

    #     assert self.board[checkers.B4] == Figure.EMPTY
    #     assert self.board[checkers.C3] == Figure.BLACK_MAN

    #     m5 = Move([checkers.B2, checkers.D4], captured_list=[checkers.C3])
    #     self.board.push(m5)
    #     assert self.board[checkers.B2] == Figure.EMPTY
    #     assert self.board[checkers.C3] == Figure.EMPTY
    #     assert self.board[checkers.D4] == Figure.WHITE_MAN

    # def test_pop(self):
    #     m = Move([checkers.A3, checkers.B4])
    #     self.board.push(m)
    #     assert self.board.turn == Color.BLACK
    #     assert self.board[checkers.A3] == Figure.EMPTY
    #     assert self.board[checkers.B4] == Figure.WHITE_MAN
    #     m = Move([checkers.F6, checkers.G5])
    #     self.board.push(m)
    #     self.board.pop()
    #     assert self.board.turn == Color.BLACK
    #     assert self.board[checkers.F6] == Figure.BLACK_MAN
    #     assert self.board[checkers.G5] == Figure.EMPTY
    #     assert self.board[checkers.A3] == Figure.EMPTY
    #     assert self.board[checkers.B4] == Figure.WHITE_MAN
