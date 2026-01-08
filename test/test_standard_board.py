import json
from pathlib import Path

import numpy as np
import pytest

from draughts.boards.base import BaseBoard, Color, Figure, Move
from draughts import get_board
from draughts.boards.standard import Board


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

    @pytest.mark.parametrize(
        "fen,valid_moves,invalid_moves",
        [
            # King multi-capture: can capture three pieces in sequence (44, 28, 31)
            ('[FEN "W:B:WK2,28,31,44:B20,K50"]', ["50x36"], []),
            # King cannot jump adjacent pieces (28 and 33 have no empty square between)
            ('[FEN "W:B:W7,28,31,33:B20,30,K50"]', [], ["50x50"]),
            # King cannot hop over same piece twice during capture sequence
            # Black king on 49 should capture 38, 28, 24 (path: 49->32->19->30/35)
            # It should NOT capture 41 because to reach it after capturing 38,
            # and then continue to 28, would require crossing 41's square twice
            ('[FEN "W:B:W6,24,28,38,41:B13,K49"]', ["49x30", "49x35"], []),
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

    def test_king_cannot_cross_captured_square(self):
        """
        Test that king cannot cross a square where a piece was already captured.
        
        FEN "W:B:W6,24,28,38,41:B13,K49" - Black king on 49
        Valid path: 49 -> capture 38 -> land on 32 -> capture 28 -> land on 19 -> capture 24 -> land on 30/35
        Invalid: capturing 41 then trying to capture 28 would cross the 41 square again
        """
        import numpy as np
        
        board = Board.from_fen('[FEN "W:B:W6,24,28,38,41:B13,K49"]')
        legal_moves = board.legal_moves
        
        # Should have exactly 2 moves (49x30 and 49x35)
        assert len(legal_moves) == 2, f"Expected 2 moves, got {len(legal_moves)}: {[str(m) for m in legal_moves]}"
        
        # Both moves should capture exactly 3 pieces: 38, 28, 24
        for move in legal_moves:
            captured_1idx = sorted([c + 1 for c in move.captured_list])
            assert captured_1idx == [24, 28, 38], f"Expected captures [24, 28, 38], got {captured_1idx}"
        
        # Piece on 41 should NOT be captured (it's on a different branch)
        test_board = Board.from_fen('[FEN "W:B:W6,24,28,38,41:B13,K49"]')
        test_board.push(legal_moves[0])
        
        # Square 41 (0-indexed: 40) should still have a white piece
        assert test_board.position[40] == -1, "White piece on square 41 was incorrectly captured"
        # Square 6 (0-indexed: 5) should still have a white piece
        assert test_board.position[5] == -1, "White piece on square 6 was incorrectly captured"
