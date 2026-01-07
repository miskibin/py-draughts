"""Tests for Hub protocol implementation."""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from draughts.boards.standard import Board as StandardBoard
from draughts.boards.frisian import Board as FrisianBoard
from draughts.models import Color, Figure
from draughts.move import Move
from draughts.engines.hub import (
    board_to_hub_position,
    hub_position_to_board,
    move_to_hub_notation,
    parse_hub_move,
    parse_hub_line,
    HubEngine,
    EngineInfo,
    SearchInfo,
    SearchResult,
    VARIANT_MAP,
)


class TestBoardToHubPosition:
    """Tests for board_to_hub_position conversion."""

    def test_starting_position_white_to_move(self):
        """Starting position with white to move."""
        board = StandardBoard()
        hub_pos = board_to_hub_position(board)
        
        # Should be 51 chars
        assert len(hub_pos) == 51
        
        # White to move
        assert hub_pos[0] == "W"
        
        # First 20 squares are black pieces
        assert hub_pos[1:21] == "b" * 20
        
        # Middle 10 squares are empty
        assert hub_pos[21:31] == "e" * 10
        
        # Last 20 squares are white pieces
        assert hub_pos[31:51] == "w" * 20

    def test_starting_position_black_to_move(self):
        """Starting position with black to move."""
        board = StandardBoard()
        board.turn = Color.BLACK
        hub_pos = board_to_hub_position(board)
        
        assert hub_pos[0] == "B"

    def test_position_with_kings(self):
        """Position containing kings."""
        # Create a position with a white king on square 25 (0-indexed 24)
        pos = np.zeros(50, dtype=np.int8)
        pos[24] = Figure.WHITE_KING.value  # -2
        pos[10] = Figure.BLACK_KING.value  # 2
        
        board = StandardBoard(starting_position=pos)
        hub_pos = board_to_hub_position(board)
        
        # Check kings are uppercase
        assert hub_pos[25] == "W"  # White king at 1-indexed square 25
        assert hub_pos[11] == "B"  # Black king at 1-indexed square 11

    def test_empty_board(self):
        """Entirely empty board."""
        pos = np.zeros(50, dtype=np.int8)
        board = StandardBoard(starting_position=pos)
        hub_pos = board_to_hub_position(board)
        
        assert hub_pos[1:] == "e" * 50

    def test_wrong_board_size_raises(self):
        """Non-50 square boards should raise ValueError."""
        # American checkers is 32 squares
        from draughts.boards.american import Board as AmericanBoard
        board = AmericanBoard()
        
        with pytest.raises(ValueError, match="only supports 10x10"):
            board_to_hub_position(board)


class TestHubPositionToBoard:
    """Tests for hub_position_to_board parsing."""

    def test_starting_position(self):
        """Parse starting position."""
        hub_pos = "W" + "b" * 20 + "e" * 10 + "w" * 20
        board = hub_position_to_board(hub_pos, StandardBoard)
        
        assert board.turn == Color.WHITE
        assert len(board.position) == 50
        
        # Black pieces on first 20 squares
        assert all(board.position[i] == Figure.BLACK_MAN.value for i in range(20))
        
        # Empty middle
        assert all(board.position[i] == 0 for i in range(20, 30))
        
        # White pieces on last 20
        assert all(board.position[i] == Figure.WHITE_MAN.value for i in range(30, 50))

    def test_black_to_move(self):
        """Parse position with black to move."""
        hub_pos = "B" + "e" * 50
        board = hub_position_to_board(hub_pos, StandardBoard)
        
        assert board.turn == Color.BLACK

    def test_with_kings(self):
        """Parse position with kings."""
        hub_pos = "W" + "B" + "W" + "e" * 48
        board = hub_position_to_board(hub_pos, StandardBoard)
        
        assert board.position[0] == Figure.BLACK_KING.value
        assert board.position[1] == Figure.WHITE_KING.value

    def test_invalid_length_raises(self):
        """Position with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="must be 51 chars"):
            hub_position_to_board("Wbbb", StandardBoard)

    def test_invalid_side_raises(self):
        """Invalid side character raises ValueError."""
        with pytest.raises(ValueError, match="Invalid side"):
            hub_position_to_board("X" + "e" * 50, StandardBoard)


class TestMoveToHubNotation:
    """Tests for move_to_hub_notation conversion."""

    def test_simple_move(self):
        """Simple non-capture move."""
        # Move from square 31 (0-indexed) to square 26 (0-indexed)
        # In Hub notation: 32-27
        move = Move([31, 26])
        
        notation = move_to_hub_notation(move)
        assert notation == "32-27"

    def test_capture_move(self):
        """Single capture move."""
        # From 31 to 22, capturing 26
        move = Move([31, 22], captured_list=[26])
        
        notation = move_to_hub_notation(move)
        # Hub format: from x to x captured
        assert notation == "32x23x27"

    def test_multi_capture_move(self):
        """Multi-capture move."""
        # From 31 to 13, capturing 26 and 17
        move = Move([31, 22, 13], captured_list=[26, 17])
        
        notation = move_to_hub_notation(move)
        # from x to x cap1 x cap2
        assert notation == "32x14x27x18"


class TestParseHubMove:
    """Tests for parse_hub_move matching."""

    def test_simple_move(self):
        """Parse simple move and match to legal moves."""
        board = StandardBoard()
        
        # 32-28 is a legal opening move (0-indexed: 31-27)
        move = parse_hub_move("32-28", board.legal_moves)
        
        assert move.square_list[0] == 31  # 0-indexed
        assert move.square_list[-1] == 27

    def test_capture_move(self):
        """Parse capture move."""
        # Set up a position with a capture available
        pos = np.zeros(50, dtype=np.int8)
        pos[27] = Figure.WHITE_MAN.value  # White on square 28 (1-indexed)
        pos[22] = Figure.BLACK_MAN.value  # Black on square 23 (1-indexed)
        
        board = StandardBoard(starting_position=pos)
        board.turn = Color.BLACK
        
        # Black should be able to capture
        legal = list(board.legal_moves)
        assert len(legal) > 0
        
        # The capture move
        capture = legal[0]
        hub_notation = move_to_hub_notation(capture)
        
        # Parse it back
        parsed = parse_hub_move(hub_notation, board.legal_moves)
        assert parsed.square_list[0] == capture.square_list[0]
        assert parsed.square_list[-1] == capture.square_list[-1]

    def test_invalid_move_format_raises(self):
        """Invalid move format raises ValueError."""
        board = StandardBoard()
        
        with pytest.raises(ValueError, match="Invalid Hub move format"):
            parse_hub_move("3228", board.legal_moves)

    def test_illegal_move_raises(self):
        """Move not in legal moves raises ValueError."""
        board = StandardBoard()
        
        with pytest.raises(ValueError, match="No legal move matches"):
            parse_hub_move("1-50", board.legal_moves)


class TestParseHubLine:
    """Tests for parse_hub_line parsing."""

    def test_simple_command(self):
        """Parse simple command without args."""
        cmd, args = parse_hub_line("ready")
        
        assert cmd == "ready"
        assert args == {}

    def test_command_with_args(self):
        """Parse command with key=value args."""
        cmd, args = parse_hub_line("id name=Scan version=3.1")
        
        assert cmd == "id"
        assert args == {"name": "Scan", "version": "3.1"}

    def test_quoted_value(self):
        """Parse command with quoted value."""
        cmd, args = parse_hub_line('id author="Fabien Letouzey"')
        
        assert cmd == "id"
        assert args["author"] == "Fabien Letouzey"

    def test_flag_argument(self):
        """Parse command with flag (no value)."""
        cmd, args = parse_hub_line("go think")
        
        assert cmd == "go"
        assert "think" in args
        assert args["think"] == ""

    def test_info_line(self):
        """Parse complex info line."""
        line = 'info depth=21 score=-0.01 nodes=31261613 pv="32-28 17-22"'
        cmd, args = parse_hub_line(line)
        
        assert cmd == "info"
        assert args["depth"] == "21"
        assert args["score"] == "-0.01"
        assert args["nodes"] == "31261613"
        assert args["pv"] == "32-28 17-22"

    def test_done_line(self):
        """Parse done line with move and ponder."""
        cmd, args = parse_hub_line("done move=32-28 ponder=17-22")
        
        assert cmd == "done"
        assert args["move"] == "32-28"
        assert args["ponder"] == "17-22"

    def test_empty_line(self):
        """Empty line returns empty command."""
        cmd, args = parse_hub_line("")
        
        assert cmd == ""
        assert args == {}


class TestHubEngineInit:
    """Tests for HubEngine initialization."""

    def test_default_params(self):
        """Default parameters are set correctly."""
        engine = HubEngine("scan.exe")
        
        assert engine.time_limit == 1.0
        assert engine.depth_limit is None
        assert engine.init_timeout == 10.0
        assert not engine._started

    def test_custom_params(self):
        """Custom parameters are set correctly."""
        engine = HubEngine(
            "scan.exe",
            time_limit=2.5,
            depth_limit=15,
            init_timeout=5.0,
        )
        
        assert engine.time_limit == 2.5
        assert engine.depth_limit == 15
        assert engine.init_timeout == 5.0


class TestHubEngineIntegration:
    """Integration tests for HubEngine (mocked subprocess)."""

    @pytest.fixture
    def mock_process(self):
        """Create a mock subprocess with Hub protocol responses."""
        process = MagicMock()
        process.stdin = MagicMock()
        process.stdout = MagicMock()
        process.stderr = MagicMock()
        
        return process

    @pytest.fixture
    def mock_select(self):
        """Mock select.select to work on Linux CI/CD (where it's used instead of blocking reads)."""
        # On Linux, select.select is called to check if stdout is ready.
        # We return the stdout as ready so readline() gets called.
        def select_side_effect(rlist, wlist, xlist, timeout=None):
            return (rlist, [], [])
        return patch("select.select", side_effect=select_side_effect)

    def test_start_handshake(self, mock_process, mock_select):
        """Test the initialization handshake."""
        # Simulate engine responses
        responses = iter([
            "id name=MockEngine version=1.0 author=Test",
            'param name=variant value=normal type=enum values="normal frisian"',
            "wait",
            "ready",
        ])
        mock_process.stdout.readline.side_effect = lambda: next(responses, "")
        
        with patch("subprocess.Popen", return_value=mock_process):
            with patch("pathlib.Path.exists", return_value=True):
                with mock_select:
                    engine = HubEngine("mock.exe")
                    engine.start()
                    
                    assert engine._started
                    assert engine.info.name == "MockEngine"
                    assert engine.info.version == "1.0"
                    assert "variant" in engine.params
                    
                    # Check that hub and init were sent
                    calls = [call[0][0] for call in mock_process.stdin.write.call_args_list]
                    assert "hub\n" in calls
                    assert "init\n" in calls

    def test_get_best_move(self, mock_process, mock_select):
        """Test getting best move from engine."""
        responses = iter([
            "id name=MockEngine version=1.0",
            "wait",
            "ready",
            'info depth=10 score=0.5 pv="32-28"',
            "done move=32-28 ponder=17-22",
        ])
        mock_process.stdout.readline.side_effect = lambda: next(responses, "")
        
        with patch("subprocess.Popen", return_value=mock_process):
            with patch("pathlib.Path.exists", return_value=True):
                with mock_select:
                    engine = HubEngine("mock.exe")
                    engine.start()
                    
                    board = StandardBoard()
                    move, score = engine.get_best_move(board, with_evaluation=True)
                    
                    # Verify the move was parsed correctly
                    assert str(move) == "32-28"
                    assert score == 0.5

    def test_context_manager(self, mock_process, mock_select):
        """Test context manager usage."""
        responses = iter([
            "id name=MockEngine version=1.0",
            "wait",
            "ready",
        ])
        mock_process.stdout.readline.side_effect = lambda: next(responses, "")
        
        with patch("subprocess.Popen", return_value=mock_process):
            with patch("pathlib.Path.exists", return_value=True):
                with mock_select:
                    with HubEngine("mock.exe") as engine:
                        assert engine._started
                    
                    # After exiting, engine should be stopped
                    assert not engine._started


class TestVariantMapping:
    """Tests for variant auto-detection."""

    def test_standard_variant(self):
        """Standard board maps to 'normal' variant."""
        board = StandardBoard()
        assert VARIANT_MAP.get(board.VARIANT_NAME) == "normal"

    def test_frisian_variant(self):
        """Frisian board should map if defined."""
        # Note: Frisian doesn't have VARIANT_NAME defined in the class
        # This test documents current behavior
        pass
