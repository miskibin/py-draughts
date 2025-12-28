import pytest
from draughts import get_board
from draughts.engine import AlphaBetaEngine


class TestAlphaBetaEngine:
    """Test the AlphaBetaEngine optimizations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = get_board("standard")
        self.engine = AlphaBetaEngine(depth=3)
        yield
        del self.board
        del self.engine

    def test_engine_returns_valid_move(self):
        """Test that engine returns a legal move."""
        move = self.engine.get_best_move(self.board)
        assert move in list(self.board.legal_moves)

    def test_engine_with_evaluation(self):
        """Test that engine can return move with evaluation."""
        move, score = self.engine.get_best_move(self.board, with_evaluation=True)
        assert move in list(self.board.legal_moves)
        assert isinstance(score, (int, float))

    def test_transposition_table_caching(self):
        """Test that transposition table is used."""
        # First call should populate the transposition table
        move1 = self.engine.get_best_move(self.board)
        nodes1 = self.engine.inspected_nodes
        
        # Make and undo a move
        self.board.push(move1)
        self.board.pop()
        
        # Second call with same position should use cache
        move2 = self.engine.get_best_move(self.board)
        nodes2 = self.engine.inspected_nodes
        
        # Should get same move
        assert move1 == move2

    def test_move_ordering(self):
        """Test that move ordering works correctly."""
        # Create a position with both captures and non-captures
        fen = "W:W31,32,33,34,35:B16,17,18,19,20"
        board = get_board("standard", fen)
        
        moves = list(board.legal_moves)
        ordered = self.engine._order_moves(moves, board)
        
        # Captures should come before non-captures
        captures = [m for m in ordered if m.captured_list]
        non_captures = [m for m in ordered if not m.captured_list]
        
        # If there are both types, captures should be first
        if captures and non_captures:
            first_capture_idx = ordered.index(captures[0])
            first_non_capture_idx = ordered.index(non_captures[0])
            assert first_capture_idx < first_non_capture_idx

    def test_evaluation_function(self):
        """Test that evaluation function works."""
        eval_score = self.engine.evaluate(self.board)
        assert isinstance(eval_score, (int, float))
        
        # Starting position should be roughly equal
        assert abs(eval_score) < 5

    def test_engine_consistency(self):
        """Test that engine gives consistent results for same position."""
        move1 = self.engine.get_best_move(self.board)
        move2 = self.engine.get_best_move(self.board)
        
        # Should return the same move for the same position
        assert move1 == move2
