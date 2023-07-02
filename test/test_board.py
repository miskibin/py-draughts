from fast_checkers.board import Board, Square, Entity, Move, STARTING_POSITION
import pytest
import numpy as np


class TestBoard:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = Board()
        yield
        del self.board

    def test_init(self):
        assert self.board.turn == Entity.WHITE
        assert np.array_equal(self.board.position, STARTING_POSITION)

    def test_move(self):
        self.board.move((Square.A3, Square.B4))
        assert self.board.turn == Entity.BLACK
        assert self.board[Square.A3] == Entity.EMPTY
        assert self.board[Square.B4] == Entity.WHITE
        self.board.move((Square.F6, Square.G5))
        assert self.board.turn == Entity.WHITE
        assert self.board[Square.F6] == Entity.EMPTY
        assert self.board[Square.G5] == Entity.BLACK

    def test_capture(self):
        print(self.board)
        self.board.move((Square.A3, Square.B4))
        self.board.move((Square.D6, Square.C5))
        self.board.move((Square.B4, Square.D6))
        self.board.move((Square.B4, Square.D6))
        assert self.board[Square.A3] == Entity.EMPTY
        assert self.board[Square.B4] == Entity.EMPTY
        assert self.board[Square.D6] == Entity.WHITE
        assert self.board[Square.C5] == Entity.EMPTY
        self.board.move((Square.C7, Square.E5))
        assert self.board[Square.C7] == Entity.EMPTY
        assert self.board[Square.D6] == Entity.EMPTY
        assert self.board[Square.E5] == Entity.BLACK
