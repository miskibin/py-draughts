import numpy as np
import pytest

from draughts.boards.base import BaseBoard, Color, Figure, Move
from draughts import get_board
from draughts.boards.standard import Board
from pathlib import Path
import json


class TestBoard:
    flies_dir = Path(__file__).parent / "games" / "standard"
    legal_mvs_file = flies_dir / "legal_moves_len.json"
    random_pos_file = flies_dir / "random_positions.json"

    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = get_board("standard")
        yield
        del self.board

    def test_init(self):
        assert self.board.turn == Color.WHITE
        assert np.array_equal(self.board.position, Board.STARTING_POSITION)

    def test_fen(self):
        with open(self.random_pos_file, "r") as f:
            random_positions = json.load(f)["positions"]
        for fen in random_positions:
            board1 = Board.from_fen(fen)
            board2 = Board.from_fen(board1.fen)
            assert np.array_equal(board1.position, board2.position)
            assert board1.turn == board2.turn

    def test_legal_moves(self):
        with open(self.legal_mvs_file, "r") as f:
            legal_moves_len = json.load(f)

        for fen, moves_len in legal_moves_len.items():
            board = Board.from_fen(fen)
            assert len(list(board.legal_moves)) == moves_len
