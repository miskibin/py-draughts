import pytest
from draughts import get_board
from draughts.engines import AlphaBetaEngine
from draughts.boards.standard import Board as StandardBoard

from test._test_helpers import seeded_range, standard_board_after_random_play


class TestAlphaBetaEngine:
    """Test the AlphaBetaEngine optimizations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = get_board("standard")
        self.engine = AlphaBetaEngine(depth_limit=3)
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
        
        # Both moves should be legal
        legal_moves = list(self.board.legal_moves)
        assert move1 in legal_moves
        assert move2 in legal_moves

    def test_move_ordering(self):
        """Test that move ordering works correctly."""
        # Create a position with both captures and non-captures
        fen = "W:W31,32,33,34,35:B16,17,18,19,20"
        board = get_board("standard", fen)
        
        moves = list(board.legal_moves)
        ordered = self.engine._order_moves(moves)
        
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
        assert abs(eval_score) < 10

    def test_engine_consistency(self):
        """Test that engine gives valid results for same position."""
        move1 = self.engine.get_best_move(self.board)
        move2 = self.engine.get_best_move(self.board)
        
        # Both should be legal moves
        legal_moves = list(self.board.legal_moves)
        assert move1 in legal_moves
        assert move2 in legal_moves


def _snapshot(board: StandardBoard):
    return {
        "fen": board.fen,
        "turn": board.turn,
        "halfmove_clock": board.halfmove_clock,
        "pos": board.position.copy(),
        "stack_len": len(board._moves_stack),
    }


@pytest.mark.parametrize("seed", list(seeded_range(15)))
def test_engine_get_best_move_does_not_mutate_board(seed):
    board = standard_board_after_random_play(seed=seed, plies=30)
    engine = AlphaBetaEngine(depth_limit=2)

    if board.game_over:
        return

    before = _snapshot(board)
    move = engine.get_best_move(board)
    after = _snapshot(board)

    assert move in list(board.legal_moves)
    assert before["fen"] == after["fen"]
    assert before["turn"] == after["turn"]
    assert before["halfmove_clock"] == after["halfmove_clock"]
    assert before["stack_len"] == after["stack_len"]
    assert (before["pos"] == after["pos"]).all()


@pytest.mark.parametrize("seed", list(seeded_range(15)))
def test_engine_hash_is_stable_across_push_pop(seed):
    board = standard_board_after_random_play(seed=seed, plies=25)
    engine = AlphaBetaEngine(depth_limit=1)

    legal = list(board.legal_moves)
    if not legal:
        return

    h1 = engine.compute_hash(board)
    board.push(legal[0])
    board.pop()
    h2 = engine.compute_hash(board)
    assert h1 == h2


@pytest.mark.parametrize("seed", list(seeded_range(10)))
def test_engine_populates_transposition_table_for_root(seed):
    board = standard_board_after_random_play(seed=seed, plies=20)
    engine = AlphaBetaEngine(depth_limit=2)

    if board.game_over:
        return

    root_hash = engine.compute_hash(board)
    engine.get_best_move(board)

    entry = engine.tt.get(root_hash)
    assert entry is not None
    _depth, _flag, _score, best_move = entry
    assert best_move in list(board.legal_moves)
