import numpy as np
import pytest

import draughts.boards.american as SQUARES
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

    def test_move(self):
        m = Move([SQUARES.A3, SQUARES.B4])
        self.board.push(m)
        assert self.board.turn == Color.BLACK
        assert self.board[SQUARES.A3] == Figure.EMPTY
        assert self.board[SQUARES.B4] == Figure.WHITE_MAN
        m = Move([SQUARES.F6, SQUARES.G5])
        self.board.push(m)
        assert self.board.turn == Color.WHITE
        assert self.board[SQUARES.F6] == Figure.EMPTY
        assert self.board[SQUARES.G5] == Figure.BLACK_MAN

    def test_capture(self):
        m1 = Move([SQUARES.C3, SQUARES.B4])
        self.board.push(m1)

        m2 = Move([SQUARES.B6, SQUARES.A5])
        self.board.push(m2)

        m3 = Move([SQUARES.G3, SQUARES.H4])
        self.board.push(m3)

        m4 = Move([SQUARES.A5, SQUARES.C3], captured_list=[SQUARES.B4])
        self.board.push(m4)

        assert self.board[SQUARES.B4] == Figure.EMPTY
        assert self.board[SQUARES.C3] == Figure.BLACK_MAN

        m5 = Move([SQUARES.B2, SQUARES.D4], captured_list=[SQUARES.C3])
        self.board.push(m5)
        assert self.board[SQUARES.B2] == Figure.EMPTY
        assert self.board[SQUARES.C3] == Figure.EMPTY
        assert self.board[SQUARES.D4] == Figure.WHITE_MAN

    def test_pop(self):
        m = Move([SQUARES.A3, SQUARES.B4])
        self.board.push(m)
        assert self.board.turn == Color.BLACK
        assert self.board[SQUARES.A3] == Figure.EMPTY
        assert self.board[SQUARES.B4] == Figure.WHITE_MAN
        m = Move([SQUARES.F6, SQUARES.G5])
        self.board.push(m)
        self.board.pop()
        assert self.board.turn == Color.BLACK
        assert self.board[SQUARES.F6] == Figure.BLACK_MAN
        assert self.board[SQUARES.G5] == Figure.EMPTY
        assert self.board[SQUARES.A3] == Figure.EMPTY
        assert self.board[SQUARES.B4] == Figure.WHITE_MAN
