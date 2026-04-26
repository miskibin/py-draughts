"""
Correctness tests for the Tier-0 engine fixes:

* Zobrist hashing — variant-seeded, halfmove-clock aware, push/pop stable,
  promotion-aware, capture-aware (incremental == full recomputation).
* Threefold repetition based on the actual position, not just move squares.
* Safe time-out handling (no TT poisoning, returned move always legal).
* ``Move.capture_value`` drives Frisian-style max-value ordering.
"""
from __future__ import annotations

import random

import pytest

from draughts import (
    AlphaBetaEngine,
    AmericanBoard,
    FrisianBoard,
    RussianBoard,
    StandardBoard,
)
from draughts.move import Move


VARIANTS = [StandardBoard, AmericanBoard, RussianBoard, FrisianBoard]


# ---------------------------------------------------------------------------
# Zobrist
# ---------------------------------------------------------------------------


class TestZobrist:
    def test_standard_and_frisian_have_distinct_seeds(self) -> None:
        eng = AlphaBetaEngine(depth_limit=1)
        assert StandardBoard.SQUARES_COUNT == FrisianBoard.SQUARES_COUNT == 50
        assert eng.compute_hash(StandardBoard()) != eng.compute_hash(FrisianBoard())

    def test_halfmove_clock_changes_hash(self) -> None:
        eng = AlphaBetaEngine(depth_limit=1)
        b1, b2 = StandardBoard(), StandardBoard()
        b2.halfmove_clock = 7
        assert eng.compute_hash(b1) != eng.compute_hash(b2)

    @pytest.mark.parametrize("BoardCls", VARIANTS)
    @pytest.mark.parametrize("seed", range(8))
    def test_hash_stable_across_push_pop(self, BoardCls, seed: int) -> None:
        rng = random.Random(seed)
        board = BoardCls()
        for _ in range(20):
            legal = list(board.legal_moves)
            if not legal:
                return
            board.push(rng.choice(legal))

        legal = list(board.legal_moves)
        if not legal:
            return
        eng = AlphaBetaEngine(depth_limit=1)
        h_before = eng.compute_hash(board)
        board.push(legal[0])
        board.pop()
        assert eng.compute_hash(board) == h_before

    @pytest.mark.parametrize("BoardCls", VARIANTS)
    def test_incremental_hash_matches_full_hash(self, BoardCls) -> None:
        rng = random.Random(123)
        board = BoardCls()
        eng = AlphaBetaEngine(depth_limit=1)
        h = eng.compute_hash(board)

        for _ in range(40):
            legal = list(board.legal_moves)
            if not legal:
                break
            move = rng.choice(legal)
            h_inc = eng._update_hash(h, board, move)
            board.push(move)
            h = eng.compute_hash(board)
            assert h_inc == h, (
                f"incremental {h_inc:#x} != full {h:#x} after {move} on {BoardCls.__name__}"
            )

    def test_promotion_handled_by_incremental_hash(self) -> None:
        # White man at square 6 can move to row 0 = promotion.
        board = StandardBoard.from_fen('W:W6:B45')
        eng = AlphaBetaEngine(depth_limit=1)
        h = eng.compute_hash(board)
        promo = next(
            m for m in board.legal_moves
            if board._pos[m.square_list[0]] == -1
            and (board.PROMO_WHITE & (1 << m.square_list[-1]))
        )
        h_inc = eng._update_hash(h, board, promo)
        board.push(promo)
        assert h_inc == eng.compute_hash(board)


# ---------------------------------------------------------------------------
# Threefold repetition
# ---------------------------------------------------------------------------


class TestThreefoldRepetition:
    def test_threefold_via_position_keys(self) -> None:
        """Inject the same key three times into history; algorithm must fire."""
        board = StandardBoard.from_fen('W:WK41:BK5')
        key = board._position_key()
        # halfmove_clock bounds how far back we scan; bump it so the window covers our history.
        board.halfmove_clock = 8
        # Same key every other ply (positions repeat every 2 plies for the same side to move).
        board._position_keys = [key, ('x', 0, 0, 0, 1), key, ('y', 0, 0, 0, 1), key]
        assert board.is_threefold_repetition is True

    def test_no_false_positive_for_distinct_positions(self) -> None:
        """The old check returned True when move *squares* matched.
        With genuinely distinct positions, we must say False."""
        board = StandardBoard.from_fen('W:WK41:BK5')
        # Two unique king moves apart — no repetition possible.
        board.push(list(board.legal_moves)[0])
        board.push(list(board.legal_moves)[0])
        assert board.is_threefold_repetition is False

    def test_position_keys_synced_with_push_pop(self) -> None:
        """Invariant: ``len(_position_keys) == len(_moves_stack) + 1``."""
        board = StandardBoard()
        rng = random.Random(11)
        for _ in range(30):
            assert len(board._position_keys) == len(board._moves_stack) + 1
            legal = list(board.legal_moves)
            if not legal:
                break
            board.push(rng.choice(legal))
        for _ in range(15):
            assert len(board._position_keys) == len(board._moves_stack) + 1
            board.pop()
        assert len(board._position_keys) == len(board._moves_stack) + 1


# ---------------------------------------------------------------------------
# Time-out safety
# ---------------------------------------------------------------------------


class TestTimeOut:
    @pytest.mark.parametrize("BoardCls", VARIANTS)
    def test_short_timeout_returns_legal_move(self, BoardCls) -> None:
        eng = AlphaBetaEngine(depth_limit=64, time_limit=0.02)
        board = BoardCls()
        move = eng.get_best_move(board)
        assert isinstance(move, Move)
        assert move in list(board.legal_moves)

    def test_no_tt_poisoning_after_timeout(self) -> None:
        """50ms of pure-Python search shouldn't reach beyond modest depth."""
        eng = AlphaBetaEngine(depth_limit=64, time_limit=0.05)
        eng.get_best_move(StandardBoard())
        max_depth = max(
            (e[1] for arr in (eng._tt_dp, eng._tt_ar) for e in arr if e is not None),
            default=0,
        )
        assert max_depth < 30


# ---------------------------------------------------------------------------
# Frisian max-value ordering uses Move.capture_value
# ---------------------------------------------------------------------------


class TestCaptureValueOrdering:
    def test_capture_value_matches_captured_material(self) -> None:
        # 1 man + 1 king
        assert Move([0, 5], [1, 2], [-1, -2]).capture_value == 3.0

    def test_capture_value_zero_for_quiet(self) -> None:
        assert Move([0, 5]).capture_value == 0.0

    def test_quiescence_capture_sort_by_value_first(self) -> None:
        small = Move([0, 5], [1], [-1])              # value 1
        big = Move([0, 5], [1, 2], [-2, -2])         # value 4
        long_chain = Move([0, 5], [1, 2, 3], [-1, -1, -1])  # value 3
        captures = [small, big, long_chain]
        captures.sort(key=lambda m: (m.capture_value, len(m.captured_list)), reverse=True)
        assert captures[0] is big

    def test_alpha_beta_move_ordering_picks_higher_value_capture(self) -> None:
        eng = AlphaBetaEngine(depth_limit=1)
        cap_2_men = Move([0, 5], [1, 2], [-1, -1])              # value 2
        cap_1_king = Move([10, 15], [11], [-2])                  # value 2
        cap_2_kings = Move([20, 25], [21, 22], [-2, -2])         # value 4
        ordered = eng._order_moves([cap_2_men, cap_1_king, cap_2_kings])
        assert ordered[0] is cap_2_kings
