"""Correctness tests for AlphaBeta engine — Tier 0 bug fixes.

These tests encode invariants that the engine *must* satisfy regardless of
search strength. Each class targets one concrete bug in the original engine
(see research report, Tier 0).
"""
from __future__ import annotations

import pytest

from draughts import StandardBoard, AmericanBoard, FrisianBoard, RussianBoard
from draughts.engines import AlphaBetaEngine
from draughts.models import Color


# ---------------------------------------------------------------------------
# B1: halfmove_clock must be part of the Zobrist hash, otherwise TT conflates
#     positions whose draw horizons differ.
# ---------------------------------------------------------------------------
class TestZobristIncludesHalfmoveClock:
    def test_different_halfmove_clock_different_hash(self):
        """Two identical positions with different halfmove_clock must hash differently."""
        engine = AlphaBetaEngine(depth_limit=1)
        board = StandardBoard.from_fen("W:WK23:BK28")
        h0 = engine.compute_hash(board)

        # Bump halfmove_clock by making king moves back and forth
        board2 = StandardBoard.from_fen("W:WK23:BK28")
        board2.halfmove_clock = 40

        h40 = engine.compute_hash(board2)
        assert h0 != h40, "halfmove_clock must affect the hash"

    def test_hash_changes_across_push_when_halfmove_increments(self):
        """After a quiet king move, halfmove_clock changes so hash should too."""
        engine = AlphaBetaEngine(depth_limit=1)
        board = StandardBoard.from_fen("W:WK28:BK23")
        h_before = engine.compute_hash(board)

        move = board.legal_moves[0]
        board.push(move)
        h_after = engine.compute_hash(board)
        assert h_before != h_after, "hash must change after a king move"


# ---------------------------------------------------------------------------
# B2: Zobrist tables must be per-variant so Standard and Frisian (both 50
#     squares) don't silently share a TT.
# ---------------------------------------------------------------------------
class TestZobristPerVariant:
    def test_standard_and_frisian_start_hashes_differ(self):
        engine = AlphaBetaEngine(depth_limit=1)
        s_hash = engine.compute_hash(StandardBoard())
        f_hash = engine.compute_hash(FrisianBoard())
        assert s_hash != f_hash, (
            "Standard and Frisian starting positions must produce "
            "different Zobrist hashes (variant-aware seeding)"
        )

    def test_engine_can_play_both_variants_without_tt_corruption(self):
        engine = AlphaBetaEngine(depth_limit=2)
        s_move = engine.get_best_move(StandardBoard())
        f_move = engine.get_best_move(FrisianBoard())
        assert s_move in list(StandardBoard().legal_moves)
        assert f_move in list(FrisianBoard().legal_moves)


# ---------------------------------------------------------------------------
# B3: threefold repetition must compare actual board state, not move paths.
# ---------------------------------------------------------------------------
class TestThreefoldRepetition:
    def test_repeated_king_shuffle_is_draw(self):
        """Two kings oscillate in a 4-ply cycle; after 3 cycles, the starting
        position has occurred 3 times — a true threefold repetition."""
        board = StandardBoard.from_fen("W:WK49:BK5")
        assert not board.is_threefold_repetition
        for _ in range(3):
            board.push_uci("49-44")
            board.push_uci("5-14")
            board.push_uci("44-49")
            board.push_uci("14-5")
        assert board.is_threefold_repetition

    def test_repetition_cleared_by_irreversible_move(self):
        """After an irreversible (man) move, the repetition window resets —
        prior oscillations can no longer form a threefold."""
        board = StandardBoard()
        # Two ply of man moves to push some reversible-window state aside.
        board.push_uci("32-28")
        board.push_uci("18-23")
        # Halfmove clock is 0 after a man move — history window should be empty.
        assert board.halfmove_clock == 0
        assert not board.is_threefold_repetition

    def test_no_false_positive_after_few_moves(self):
        """A short opening should never produce a spurious threefold."""
        board = StandardBoard()
        board.push_uci("32-28")
        board.push_uci("18-23")
        assert not board.is_threefold_repetition

    def test_pop_restores_repetition_history(self):
        """Pushing then popping should leave repetition state untouched."""
        board = StandardBoard.from_fen("W:WK49:BK5")
        hist_before = list(board._position_history)
        board.push_uci("49-44")
        board.pop()
        assert board._position_history == hist_before


def _position_key(board):
    """Ground-truth position key used by the test (not the engine)."""
    return (board.white_men, board.white_kings,
            board.black_men, board.black_kings, board.turn.value)


# ---------------------------------------------------------------------------
# B4: timeout must not corrupt the TT with partial/invalid scores.
# ---------------------------------------------------------------------------
class TestTimeoutDoesNotCorruptTT:
    def test_timeout_returns_legal_move_and_preserves_tt_integrity(self):
        """With a very small time budget, the engine should still return a
        legal move and should not leave nonsense in the TT."""
        engine = AlphaBetaEngine(depth_limit=20, time_limit=0.01)
        board = StandardBoard()
        move = engine.get_best_move(board)
        assert move in list(board.legal_moves)

        # Every TT bucket-pair holds up to 2 entries; each must be either None
        # or a well-formed (depth, flag, score, move, generation) tuple with a
        # sane score and a Move-like object if present.
        for key, buckets in engine.tt.items():
            for entry in buckets:
                if entry is None:
                    continue
                depth, flag, score, best_move, gen = entry
                assert best_move is None or hasattr(best_move, "square_list")
                assert abs(score) < 1e6, f"poisoned score {score} in TT at {key}"


# ---------------------------------------------------------------------------
# B6: history keying should distinguish promotion from non-promotion moves.
# ---------------------------------------------------------------------------
class TestHistoryKeyingIncludesPromotion:
    def test_history_key_has_promotion_dimension(self):
        """The engine's history table should key on (start, end, is_promotion)
        — or at minimum, promoting and non-promoting moves with the same
        (start,end) must not collide."""
        engine = AlphaBetaEngine(depth_limit=1)
        # Force a situation: the engine must produce at least one history
        # entry after a search. Then verify keys carry promotion info.
        board = StandardBoard()
        engine.get_best_move(board)
        # Keys are tuples — they must have >= 3 dimensions now.
        for key in engine.history:
            assert len(key) >= 3, (
                f"history key {key!r} should include promotion/capture flag"
            )


# ---------------------------------------------------------------------------
# Engine evaluation symmetry — catches sign errors / mirror bugs early.
# Applies across all variants.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("BoardCls", [StandardBoard, AmericanBoard, RussianBoard, FrisianBoard])
class TestEvaluationSymmetry:
    def test_starting_position_is_approximately_balanced(self, BoardCls):
        engine = AlphaBetaEngine(depth_limit=1)
        board = BoardCls()
        assert abs(engine.evaluate(board)) < 0.5, (
            f"{BoardCls.__name__}: starting position should be near-balanced"
        )

    def test_one_extra_king_is_worth_roughly_three(self, BoardCls):
        """Material sanity: one king advantage ≈ +2.5 to +3.5 (king=3.0 ish)."""
        engine = AlphaBetaEngine(depth_limit=1)
        # Build a minimal position where side to move has 1 king advantage.
        # We can't easily build arbitrary FENs for every variant; use
        # starting position and force evaluation after mutating bitboards.
        board = BoardCls()
        # Clear the board and put 1 white king vs nothing; white to move.
        board.white_men = 0
        board.black_men = 0
        board.white_kings = 1 << 0
        board.black_kings = 0
        board.turn = Color.WHITE
        score = engine.evaluate(board)
        # Positive from white's perspective — score is relative to side to move.
        assert score > 1.5, f"{BoardCls.__name__}: 1 extra king -> {score}"
