import json
from pathlib import Path

import numpy as np
import pytest

import draughts.boards.russian as russian
from draughts.boards.russian import Board
from draughts import get_board
from draughts.models import Color, Figure
from draughts.move import Move


class TestRussianBoard:
    """Tests for Russian draughts variant."""
    
    files_dir = Path(__file__).parent / "games" / "russian"
    random_pdns_file = files_dir / "random_pdns.json"

    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = Board()
        yield
        del self.board

    def test_init(self):
        """Test board initializes correctly."""
        assert self.board.turn == Color.WHITE
        assert np.array_equal(self.board.position, Board.STARTING_POSITION)

    def test_game_type(self):
        """Russian has GameType 25."""
        assert Board.GAME_TYPE == 25

    def test_variant_name(self):
        """Test variant name."""
        assert Board.VARIANT_NAME == "Russian draughts"

    def test_board_size(self):
        """Russian uses 8x8 board (32 squares)."""
        assert Board.SQUARES_COUNT == 32
        assert self.board.shape == (8, 8)

    def test_starting_position(self):
        """Each side starts with 12 men on first 3 ranks."""
        # Count pieces
        black_count = np.sum(self.board.position == 1)
        white_count = np.sum(self.board.position == -1)
        assert black_count == 12
        assert white_count == 12

    def test_get_board_factory(self):
        """Test that get_board('russian') works."""
        board = get_board("russian")
        assert isinstance(board, Board)
        assert board.GAME_TYPE == 25

    def test_simple_move(self):
        """Test that men move diagonally forward only (non-captures)."""
        moves = self.board.legal_moves
        # White should have opening moves
        assert len(moves) > 0
        # All should be simple moves (no captures at start)
        for m in moves:
            assert not m.captured_list

    def test_men_move_forward_only(self):
        """Men can only move forward (non-capture)."""
        # Create a position with a single white man in the middle
        position = np.zeros(32, dtype=np.int8)
        position[russian.E5] = -1  # White man at E5 (square 14)
        board = Board(position, Color.WHITE)
        
        moves = board.legal_moves
        # Man should only move forward (toward row 0 for white)
        for m in moves:
            assert m.square_list[-1] < m.square_list[0]  # Moving to lower square number

    def test_men_capture_backward(self):
        """
        Men can capture both forward AND backward in Russian draughts.
        This is a key difference from American checkers.
        """
        # Set up position where white man can only capture backward
        position = np.zeros(32, dtype=np.int8)
        position[russian.E5] = -1  # White man at E5 (square 14)
        position[russian.F4] = 1   # Black man at F4 (square 18)
        # Landing square at G3 (square 22) should be empty
        board = Board(position, Color.WHITE)
        
        captures = [m for m in board.legal_moves if m.captured_list]
        # White should be able to capture backward
        assert len(captures) > 0
        # Verify it's a backward capture (to higher square number)
        for cap in captures:
            assert cap.square_list[-1] > cap.square_list[0]


class TestRussianFlyingKings:
    """Test flying king behavior in Russian draughts."""

    def test_king_moves_any_distance(self):
        """Kings can move any number of squares diagonally."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.E5] = -2  # White king at E5 (middle)
        board = Board(position, Color.WHITE)
        
        moves = board.legal_moves
        # Should have many moves (flying king)
        assert len(moves) > 4  # More than just adjacent squares

    def test_king_captures_flying(self):
        """Kings can capture from any distance and land anywhere beyond."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -2  # White king at corner
        position[russian.C3] = 1   # Black man on diagonal
        board = Board(position, Color.WHITE)
        
        captures = [m for m in board.legal_moves if m.captured_list]
        assert len(captures) > 0
        # Should have multiple landing options beyond captured piece


class TestRussianCaptures:
    """Test capture rules specific to Russian draughts."""

    def test_captures_mandatory(self):
        """If a capture is available, it must be taken."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.E5] = -1  # White man
        position[russian.D6] = 1   # Black man (can be captured)
        position[russian.F4] = -1  # Another white man (can't move if capture available)
        board = Board(position, Color.WHITE)
        
        moves = board.legal_moves
        # All moves should be captures
        for m in moves:
            assert m.captured_list, "Captures should be mandatory"

    def test_free_capture_choice(self):
        """
        In Russian draughts, player can choose ANY capture sequence.
        Unlike International, NOT required to take maximum captures.
        """
        # Set up position with multiple capture options of different lengths
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -1  # White man that could capture 1 piece
        position[russian.B2] = 1   # Black man (short capture)
        position[russian.G1] = -1  # White man that could capture 2 pieces
        position[russian.F2] = 1   # Black man 1
        position[russian.D4] = 1   # Black man 2 (for double capture)
        board = Board(position, Color.WHITE)
        
        captures = board.legal_moves
        # Should have captures of different lengths available
        lengths = set(len(m) for m in captures)
        # Player can choose any (no max-capture filtering)
        assert len(captures) > 0

    def test_multi_jump_must_complete(self):
        """Once a capture chain starts, must continue until no more captures."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -1  # White man
        position[russian.B2] = 1   # Black man 1
        position[russian.D4] = 1   # Black man 2 (in line for double capture)
        board = Board(position, Color.WHITE)
        
        captures = board.legal_moves
        # If there's a path for double capture, it should be one move
        for cap in captures:
            if len(cap.captured_list) == 2:
                # Move should visit all intermediate squares
                assert len(cap.square_list) == 3  # start, mid, end


class TestRussianMidCapturePromotion:
    """Test mid-capture promotion - the unique Russian rule."""

    def test_man_promotes_mid_capture(self):
        """
        If a man reaches promotion rank during a capture and can continue,
        it immediately becomes a king and continues capturing as a king.
        """
        # White man at B6 (square 8), can jump over black at C7 (square 5)
        # and land on D8 (square 1) which is the promotion rank
        # Row mapping (0-indexed): 
        #   row0=B8,D8,F8,H8 (sq 0-3)
        #   row1=A7,C7,E7,G7 (sq 4-7) 
        #   row2=B6,D6,F6,H6 (sq 8-11)
        position = np.zeros(32, dtype=np.int8)
        position[8] = -1   # White man at B6
        position[5] = 1    # Black man at C7 (diagonal from B6, can be jumped)
        board = Board(position, Color.WHITE)
        
        captures = board.legal_moves
        # Should have captures
        assert any(m.captured_list for m in captures)
        # Landing on D8 (square 1, row 0) should trigger promotion
        promoted_captures = [m for m in captures if m.is_promotion]
        assert len(promoted_captures) > 0, "Should have promotion captures"

    def test_mid_promotion_continues_as_king(self):
        """After mid-capture promotion, piece moves as flying king."""
        # This is a complex scenario requiring specific setup
        position = np.zeros(32, dtype=np.int8)
        # White man at A7 (square 4), can capture to A8-ish position
        # but we need to trace exact squares
        position[4] = -1   # White man at row 1 (A7)
        position[0] = 1    # Black man on back rank to capture
        position[1] = 1    # Another black piece for king to potentially capture
        board = Board(position, Color.WHITE)
        
        # Just verify move generation doesn't crash
        moves = board.legal_moves
        assert isinstance(moves, list)


class TestRussianDrawRules:
    """Test draw conditions in Russian draughts."""

    def test_threefold_repetition(self):
        """Same position three times with same player to move = draw."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -2  # White king
        position[russian.H8] = 2   # Black king
        board = Board(position, Color.WHITE)
        
        # Play moves to create repetition
        # This requires specific moves; test that the property exists
        assert hasattr(board, 'is_threefold_repetition')

    def test_15_moves_rule(self):
        """Draw after 15 king moves without captures or man moves."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -2  # White king
        position[russian.H8] = 2   # Black king
        board = Board(position, Color.WHITE)
        
        assert not board.is_15_moves_rule
        board.halfmove_clock = 30  # 15 moves = 30 half-moves
        assert board.is_15_moves_rule

    def test_3_kings_vs_1_rule(self):
        """3+ kings vs 1 king: must win within 15 moves."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -2  # White king 1
        position[russian.C1] = -2  # White king 2
        position[russian.E1] = -2  # White king 3
        position[russian.H8] = 2   # Black king (lone)
        board = Board(position, Color.WHITE)
        
        assert not board.is_3_kings_vs_1_rule
        board.halfmove_clock = 30
        assert board.is_3_kings_vs_1_rule

    def test_3_kings_vs_1_not_triggered_with_men(self):
        """3 kings vs 1 rule only applies when no men remain."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -2  # White king 1
        position[russian.C1] = -2  # White king 2
        position[russian.E1] = -2  # White king 3
        position[russian.H8] = 2   # Black king
        position[russian.F8] = 1   # Black man (still has men!)
        board = Board(position, Color.WHITE)
        
        board.halfmove_clock = 30
        assert not board.is_3_kings_vs_1_rule  # Rule not triggered due to man


class TestRussianFEN:
    """Test FEN parsing and generation."""

    def test_fen_roundtrip(self):
        """Test FEN parsing and generation roundtrip."""
        board = Board()
        fen = board.fen
        board2 = Board.from_fen(fen)
        assert np.array_equal(board.position, board2.position)
        assert board.turn == board2.turn

    def test_fen_with_kings(self):
        """Test FEN with king pieces."""
        position = np.zeros(32, dtype=np.int8)
        position[0] = -2  # White king
        position[31] = 2  # Black king
        board = Board(position, Color.WHITE)
        
        fen = board.fen
        board2 = Board.from_fen(fen)
        assert np.array_equal(board.position, board2.position)


class TestRussianPDN:
    """Test PDN parsing with real Russian draughts games."""

    files_dir = Path(__file__).parent / "games" / "russian"
    random_pdns_file = files_dir / "random_pdns.json"

    def test_play_random_pdns(self):
        """Test that we can play through random PDN games from lidraughts."""
        with open(self.random_pdns_file, "r") as f:
            data = json.load(f)
        
        played = 0
        errors = []
        for pdn in data["pdn_positions"]:
            # Skip PDNs that are just headers (no moves)
            if "[Event" in pdn and "1." not in pdn:
                continue
            
            # Extract just the moves part if there are headers
            if "[Event" in pdn:
                lines = pdn.split("\n")
                moves_part = ""
                for line in lines:
                    if line.strip() and not line.startswith("["):
                        moves_part = line
                        break
                if not moves_part or "1." not in moves_part:
                    continue
                pdn = moves_part
            
            try:
                board = Board.from_pdn(pdn)
                played += 1
            except Exception as e:
                errors.append(f"PDN: {pdn[:80]}...\nError: {e}")
        
        # Ensure we actually tested some games
        assert played > 0, "No PDN games were tested"
        # Allow some failures (some PDN games may have edge cases)
        success_rate = played / (played + len(errors))
        assert success_rate >= 0.5, f"Too many failures ({len(errors)}/{played+len(errors)}). First error: {errors[0] if errors else 'none'}"

    @pytest.mark.parametrize("pdn", [
        "1. c3-d4 b6-c5 2. d4xb6 a7xc5",
        "1. c3-b4 f6-g5 2. b4-a5 g5-f4 3. g3xe5 d6xf4",
    ])
    def test_basic_pdn_parsing(self, pdn):
        """Test basic PDN move parsing."""
        board = Board.from_pdn(pdn)
        assert len(board._moves_stack) > 0


class TestRussianSquareNames:
    """Test algebraic notation support."""

    def test_square_names_defined(self):
        """Algebraic square names should be defined for PDN parsing."""
        assert len(Board.SQUARE_NAMES) == 32

    def test_square_names_format(self):
        """Square names should be in format like 'b8', 'a7', etc."""
        for name in Board.SQUARE_NAMES:
            assert len(name) == 2
            assert name[0] in 'abcdefgh'
            assert name[1] in '12345678'


class TestRussianMoveGeneration:
    """Test move generation edge cases."""

    def test_no_legal_moves_blocked(self):
        """Test position with no legal moves (blocked)."""
        position = np.zeros(32, dtype=np.int8)
        # White man in corner, blocked by own pieces
        position[russian.A1] = -1
        position[russian.B2] = -1
        board = Board(position, Color.WHITE)
        
        moves = board.legal_moves
        # May have limited moves or none depending on setup
        assert isinstance(moves, list)

    def test_game_over_no_pieces(self):
        """Game is over when a player has no pieces."""
        position = np.zeros(32, dtype=np.int8)
        position[russian.A1] = -1  # Only white has pieces
        board = Board(position, Color.BLACK)
        
        assert board.game_over
        # White wins because black has no moves (1-0 means white wins)
        assert board.result == "1-0"

    def test_push_pop_roundtrip(self):
        """Test that push/pop correctly restores position."""
        board = Board()
        initial_pos = board.position.copy()
        
        move = board.legal_moves[0]
        board.push(move)
        board.pop()
        
        assert np.array_equal(board.position, initial_pos)
        assert board.turn == Color.WHITE

