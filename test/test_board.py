from checkers.base_board import (
    BaseBoard,
    Color,
    Move,
    STARTING_POSITION,
    Entity,
)
from checkers.models import Square as Sq
from checkers.models import MovesChain as Chain
import pytest
import numpy as np


class TestBoard:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = BaseBoard()
        yield
        del self.board

    def test_init(self):
        assert self.board.turn == Color.WHITE
        assert np.array_equal(self.board.position, STARTING_POSITION)

    def test_move(self):
        m = Move(square_list=[Sq.A3.index, Sq.B4.index])
        self.board.push(m)
        assert self.board.turn == Color.BLACK
        assert self.board[Sq.A3] == Entity.EMPTY
        assert self.board[Sq.B4] == Entity.WHITE_MAN
        m = Move(square_list=[Sq.F6.index, Sq.G5.index])
        self.board.push(m)
        assert self.board.turn == Color.WHITE
        assert self.board[Sq.F6] == Entity.EMPTY
        assert self.board[Sq.G5] == Entity.BLACK_MAN

    def test_capture(self):
        m1 = Move(square_list=[Sq(22).index, Sq(17).index])
        self.board.push(m1)

        m2 = Move(square_list=[Sq(9).index, Sq(13).index])
        self.board.push(m2)

        m3 = Move(square_list=[Sq(24).index, Sq(20).index])
        self.board.push(m3)

        m4 = Move(square_list=[Sq(13).index, Sq(22).index], captured_list=[Sq(17).index])
        self.board.push(m4)

        assert self.board[Sq(17)] == Entity.EMPTY
        assert self.board[Sq(22)] == Entity.BLACK_MAN

        m5 = Move(square_list=[Sq(25).index, Sq(18).index], captured_list=[Sq(22).index])
        self.board.push(m5)
        assert self.board[Sq(25)] == Entity.EMPTY
        assert self.board[Sq(22)] == Entity.EMPTY
        assert self.board[Sq(18)] == Entity.WHITE_MAN

    def test_pop(self):
        m = Move(square_list=[Sq.A3.index, Sq.B4.index])
        self.board.push(m)
        assert self.board.turn == Color.BLACK
        assert self.board[Sq.A3] == Entity.EMPTY
        assert self.board[Sq.B4] == Entity.WHITE_MAN
        m = Move(square_list=[Sq.F6.index, Sq.G5.index])
        self.board.push(m)
        self.board.pop()
        assert self.board.turn == Color.BLACK
        assert self.board[Sq.F6] == Entity.BLACK_MAN
        assert self.board[Sq.G5] == Entity.EMPTY
        assert self.board[Sq.A3] == Entity.EMPTY
        assert self.board[Sq.B4] == Entity.WHITE_MAN
