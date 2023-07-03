from fast_checkers.base_board import (
    BaseBoard,
    Color,
    Move,
    STARTING_POSITION,
    Entity,
    MovesChain,
)
from fast_checkers.models import Square as Sq
from fast_checkers.models import MovesChain as Chain
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
        m = Chain([Move(Sq.A3, Sq.B4)])
        self.board.push(m)
        assert self.board.turn == Color.BLACK
        assert self.board[Sq.A3] == Entity.EMPTY
        assert self.board[Sq.B4] == Entity.WHITE_MAN
        m = Chain([Move(Sq.F6, Sq.G5)])
        self.board.push(m)
        assert self.board.turn == Color.WHITE
        assert self.board[Sq.F6] == Entity.EMPTY
        assert self.board[Sq.G5] == Entity.BLACK_MAN

    def test_capture(self):
        m1 = MovesChain([Move(Sq(22).index, Sq(17).index)])
        self.board.push(m1)
        m2 = MovesChain([Move(Sq(9).index, Sq(13).index)])
        self.board.push(m2)
        m2 = MovesChain([Move(Sq(24).index, Sq(20).index)])
        self.board.push(m2)
        m2 = MovesChain([Move(Sq(13).index, Sq(22).index, Sq(17).index)])
        self.board.push(m2)

        assert self.board[Sq(17)] == Entity.EMPTY
        assert self.board[Sq(22)] == Entity.BLACK_MAN

        m5 = Chain([Move(Sq(25), Sq(18), Sq(22))])
        self.board.push(m5)
        assert self.board[Sq(25)] == Entity.EMPTY
        assert self.board[Sq(22)] == Entity.EMPTY
        assert self.board[Sq(18)] == Entity.WHITE_MAN

    def test_pop(self):
        m = Chain([Move(Sq.A3, Sq.B4)])
        self.board.push(m)
        assert self.board.turn == Color.BLACK
        assert self.board[Sq.A3] == Entity.EMPTY
        assert self.board[Sq.B4] == Entity.WHITE_MAN
        m = Chain([Move(Sq.F6, Sq.G5)])
        self.board.push(m)
        self.board.pop()
        assert self.board.turn == Color.BLACK
        assert self.board[Sq.F6] == Entity.BLACK_MAN
        assert self.board[Sq.G5] == Entity.EMPTY
        assert self.board[Sq.A3] == Entity.EMPTY
        assert self.board[Sq.B4] == Entity.WHITE_MAN
