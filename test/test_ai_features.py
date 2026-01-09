"""Tests for AI/ML support features."""
import copy

import numpy as np
import pytest

from draughts import (
    Agent,
    AgentEngine,
    AmericanBoard,
    BaseAgent,
    Board,
    BoardFeatures,
    Color,
    Engine,
    Move,
)


class TestCopy:
    """Tests for board.copy() method."""

    def test_copy_preserves_position(self):
        board = Board()
        board.push_uci("31-27")
        clone = board.copy()
        assert np.array_equal(board.position, clone.position)

    def test_copy_preserves_turn(self):
        board = Board()
        board.push_uci("31-27")
        clone = board.copy()
        assert board.turn == clone.turn

    def test_copy_is_independent(self):
        board = Board()
        board.push_uci("31-27")
        clone = board.copy()
        clone.push_uci("18-22")
        # Original should be unchanged
        assert board.turn == Color.BLACK
        assert clone.turn == Color.WHITE

    def test_copy_has_empty_move_stack(self):
        board = Board()
        board.push_uci("31-27")
        board.push_uci("18-22")
        clone = board.copy()
        assert len(clone._moves_stack) == 0
        assert len(board._moves_stack) == 2

    def test_deepcopy_preserves_move_stack(self):
        board = Board()
        board.push_uci("31-27")
        board.push_uci("18-22")
        clone = copy.deepcopy(board)
        assert len(clone._moves_stack) == 2


class TestFeatures:
    """Tests for board.features() method."""

    def test_features_returns_dataclass(self):
        board = Board()
        f = board.features()
        assert isinstance(f, BoardFeatures)

    def test_features_starting_position(self):
        board = Board()
        f = board.features()
        assert f.white_men == 20
        assert f.white_kings == 0
        assert f.black_men == 20
        assert f.black_kings == 0
        assert f.turn == 1  # White to move
        assert f.material_balance == 0.0
        assert f.phase == "opening"

    def test_features_mobility(self):
        board = Board()
        f = board.features()
        assert f.mobility == len(board.legal_moves)

    def test_features_after_captures(self):
        # Create a position with pieces captured
        board = Board.from_fen("W:WK25:BK30")
        f = board.features()
        assert f.white_men == 0
        assert f.white_kings == 1
        assert f.black_men == 0
        assert f.black_kings == 1
        assert f.phase == "endgame"

    def test_features_is_immutable(self):
        board = Board()
        f = board.features()
        with pytest.raises(Exception):  # FrozenInstanceError
            f.white_men = 100


class TestToTensor:
    """Tests for board.to_tensor() method."""

    def test_tensor_shape(self):
        board = Board()
        tensor = board.to_tensor()
        assert tensor.shape == (4, 50)

    def test_tensor_dtype(self):
        board = Board()
        tensor = board.to_tensor()
        assert tensor.dtype == np.float32

    def test_tensor_starting_position_white_perspective(self):
        board = Board()
        tensor = board.to_tensor(perspective=Color.WHITE)
        # Channel 0: own men (white), Channel 2: opponent men (black)
        assert tensor[0].sum() == 20  # White men
        assert tensor[1].sum() == 0   # White kings
        assert tensor[2].sum() == 20  # Black men
        assert tensor[3].sum() == 0   # Black kings

    def test_tensor_starting_position_black_perspective(self):
        board = Board()
        tensor = board.to_tensor(perspective=Color.BLACK)
        # Perspectives are swapped
        assert tensor[0].sum() == 20  # Black men (own)
        assert tensor[2].sum() == 20  # White men (opponent)

    def test_tensor_with_kings(self):
        board = Board.from_fen("W:WK25,K30:BK10,K15")
        tensor = board.to_tensor(perspective=Color.WHITE)
        assert tensor[0].sum() == 0   # No white men
        assert tensor[1].sum() == 2   # 2 white kings
        assert tensor[2].sum() == 0   # No black men
        assert tensor[3].sum() == 2   # 2 black kings

    def test_tensor_american_board(self):
        board = AmericanBoard()
        tensor = board.to_tensor()
        assert tensor.shape == (4, 32)


class TestMoveIndexing:
    """Tests for move indexing and masks."""

    def test_legal_moves_mask_shape(self):
        board = Board()
        mask = board.legal_moves_mask()
        assert mask.shape == (2500,)  # 50 * 50

    def test_legal_moves_mask_count(self):
        board = Board()
        mask = board.legal_moves_mask()
        assert mask.sum() == len(board.legal_moves)

    def test_move_to_index_roundtrip(self):
        board = Board()
        for move in board.legal_moves:
            idx = board.move_to_index(move)
            recovered = board.index_to_move(idx)
            assert move == recovered

    def test_index_to_move_invalid_raises(self):
        board = Board()
        with pytest.raises(ValueError):
            board.index_to_move(0)  # Square 0 to 0 is not legal

    def test_mask_american_board(self):
        board = AmericanBoard()
        mask = board.legal_moves_mask()
        assert mask.shape == (1024,)  # 32 * 32


class TestAgentProtocol:
    """Tests for Agent protocol."""

    def test_simple_agent_is_agent(self):
        class RandomAgent:
            def select_move(self, board):
                import random
                return random.choice(board.legal_moves)

        agent = RandomAgent()
        assert isinstance(agent, Agent)

    def test_agent_can_play(self):
        class FirstMoveAgent:
            def select_move(self, board):
                return board.legal_moves[0]

        board = Board()
        agent = FirstMoveAgent()
        move = agent.select_move(board)
        assert isinstance(move, Move)
        assert move in board.legal_moves


class TestBaseAgent:
    """Tests for BaseAgent class."""

    def test_base_agent_name(self):
        class MyAgent(BaseAgent):
            def select_move(self, board):
                return board.legal_moves[0]

        agent = MyAgent()
        assert agent.name == "MyAgent"

        agent2 = MyAgent(name="CustomName")
        assert agent2.name == "CustomName"

    def test_base_agent_implements_protocol(self):
        class MyAgent(BaseAgent):
            def select_move(self, board):
                return board.legal_moves[0]

        agent = MyAgent()
        assert isinstance(agent, Agent)

    def test_base_agent_as_engine(self):
        class MyAgent(BaseAgent):
            def select_move(self, board):
                return board.legal_moves[0]

        agent = MyAgent(name="TestBot")
        engine = agent.as_engine()
        assert isinstance(engine, Engine)
        assert isinstance(engine, AgentEngine)
        assert engine.name == "TestBot"


class TestAgentEngine:
    """Tests for AgentEngine adapter."""

    def test_agent_engine_is_engine(self):
        class SimpleAgent:
            def select_move(self, board):
                return board.legal_moves[0]

        engine = AgentEngine(SimpleAgent())
        assert isinstance(engine, Engine)

    def test_agent_engine_get_best_move(self):
        class FirstMoveAgent:
            def select_move(self, board):
                return board.legal_moves[0]

        board = Board()
        engine = AgentEngine(FirstMoveAgent())
        move = engine.get_best_move(board)

        assert isinstance(move, Move)
        assert move == board.legal_moves[0]

    def test_agent_engine_with_evaluation(self):
        class FirstMoveAgent:
            def select_move(self, board):
                return board.legal_moves[0]

        board = Board()
        engine = AgentEngine(FirstMoveAgent())
        move, score = engine.get_best_move(board, with_evaluation=True)

        assert isinstance(move, Move)
        assert score == 0.0  # Agents don't provide evaluations

    def test_agent_engine_uses_agent_name(self):
        class NamedAgent:
            name = "CustomBot"

            def select_move(self, board):
                return board.legal_moves[0]

        engine = AgentEngine(NamedAgent())
        assert engine.name == "CustomBot"

    def test_agent_engine_custom_name(self):
        class SimpleAgent:
            def select_move(self, board):
                return board.legal_moves[0]

        engine = AgentEngine(SimpleAgent(), name="OverrideName")
        assert engine.name == "OverrideName"

    def test_agent_engine_tracks_nodes(self):
        class SimpleAgent:
            def select_move(self, board):
                return board.legal_moves[0]

        board = Board()
        engine = AgentEngine(SimpleAgent())
        engine.get_best_move(board)

        assert engine.nodes == 1
        assert engine.inspected_nodes == 1

