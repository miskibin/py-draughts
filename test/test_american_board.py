import numpy as np
import pytest

import draughts.boards.american as checkers
from draughts.boards.american import Board, Color, Move
from draughts.models import Figure


class TestAmericanBoard:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = Board()
        yield
        del self.board

    def test_move_from_str_method(self):
        legal_moves = self.board.legal_moves
        m1 = Move.from_uci("24-20", legal_moves)
        assert m1 == Move([checkers.G3, checkers.H4])

        with pytest.raises(ValueError):
            Move.from_uci("25-20", [])

    def test_push_from_string(self):
        m1 = Move.from_uci("24-20", self.board.legal_moves)
        self.board.push_uci("24-20")
        assert self.board.turn == Color.BLACK
        assert self.board.pop() == m1
        assert np.array_equal(self.board.position, Board.STARTING_POSITION)

    def test_capture(self):
        moves = ["24-20", "11-16", "20x11", "7x16"]
        for m in moves:
            self.board.push_uci(m)
        assert self.board[checkers.F6] == Figure.EMPTY.value
