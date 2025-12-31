import numpy as np
import pytest

from draughts.boards.base import BaseBoard, Color, Figure, Move
from draughts import get_board
from draughts.boards.standard import Board
from pathlib import Path
import json
from draughts.utils import logger


class TestBoard:
    flies_dir = Path(__file__).parent / "games" / "standard"
    legal_mvs_file = flies_dir / "legal_moves_len.json"
    random_pos_file = flies_dir / "random_positions.json"
    random_pdns = flies_dir / "random_pdns.json"

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

    @pytest.mark.parametrize(
        "fen,valid_moves,invalid_moves",
        [
            # King multi-capture: can capture three pieces in sequence (44, 28, 31)
            ('[FEN "W:B:WK2,28,31,44:B20,K50"]', ["50x36"], []),
            # King cannot jump adjacent pieces (28 and 33 have no empty square between)
            ('[FEN "W:B:W7,28,31,33:B20,30,K50"]', [], ["50x50"]),
        ],
    )
    def test_king_capture_edge_cases(self, fen, valid_moves, invalid_moves):
        """Test various edge cases for king captures."""
        board = Board.from_fen(fen)
        legal_moves = board.legal_moves
        move_strs = [str(m) for m in legal_moves]

        for move in valid_moves:
            assert move in move_strs, f"Expected {move} in legal moves, got: {move_strs}"

        for move in invalid_moves:
            assert move not in move_strs, f"Invalid move {move} found in: {move_strs}"

    def test_games_from_pdns(self):
        import re
        with open(self.random_pdns, "r") as f:
            pdns = json.load(f)["pdn_positions"]

        # Regex to extract moves (e.g., "33-28", "22x31") - excludes game results like "1-0", "0-1", "2-0", "0-2"
        re_moves = re.compile(r"\b(\d{2,}[-x]\d+(?:[-x]\d+)*)\b")

        for pdn in pdns:
            board = Board.from_pdn(pdn)
            output_pdn = board.pdn

            # Extract moves from input and output PDNs (only moves with 2+ digit squares)
            input_moves = re_moves.findall(pdn)
            output_moves = re_moves.findall(output_pdn)

            assert input_moves == output_moves, f"Moves mismatch:\nInput:  {input_moves}\nOutput: {output_moves}" 