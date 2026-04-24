"""Tactical regression suite for AlphaBeta engine.

These are hand-crafted positions where the best move is unambiguous. Any
search-strength change (LMR, null-move, futility, …) that regresses tactics
breaks one of these tests. The suite is intentionally small and fast to keep
CI cheap; extend it with Lidraughts puzzles when a PDN corpus is available.
"""
from __future__ import annotations

import pytest

from draughts import StandardBoard, AmericanBoard
from draughts.engines import AlphaBetaEngine


# ---------------------------------------------------------------------------
# Evaluation: material math must be sane (man=1, king=3).
# ---------------------------------------------------------------------------
class TestEvaluationMaterialMath:
    """evaluate() returns a score from the side-to-move's perspective.
    Positive = the side to move is ahead."""

    @pytest.mark.parametrize("fen, expected_sign", [
        # White has 2 men, black has 1 man; white to move -> positive.
        ("W:W6,46:B1", +1),
        # White has 1 man, black has 2 men; white to move -> negative.
        ("W:W6:B1,46", -1),
        # White has 1 king, black has 1 man; white to move -> positive (king > man).
        ("W:WK23:B1", +1),
        # Same material but black to move; black is down -> negative.
        ("B:WK23:B1", -1),
    ])
    def test_material_sign_is_correct(self, fen, expected_sign):
        engine = AlphaBetaEngine(depth_limit=1)
        board = StandardBoard.from_fen(fen)
        score = engine.evaluate(board)
        assert (score > 0) == (expected_sign > 0), (
            f"FEN={fen}: got {score}, expected sign {expected_sign}"
        )

    def test_two_kings_versus_one_king_is_about_three_pawns_up(self):
        """A single king is worth ≈ 3 men (the Scan prior). 2K-1K ≈ +3 for the
        side with more kings. This tests the raw evaluator, not search — no
        tactical interactions are possible here."""
        engine = AlphaBetaEngine(depth_limit=1)
        # FEN format: one `K` prefix per king-list entry.
        board = StandardBoard.from_fen("W:WK11,K13:BK48")
        score = engine.evaluate(board)
        # White has 2 kings, black has 1; score is from white's perspective.
        assert 2.0 < score < 4.5, f"2K vs 1K eval = {score}, expected ~3"

    def test_eval_is_colour_symmetric(self):
        """Swapping the side to move must flip the sign of the evaluation
        (the position itself doesn't change, only whose perspective)."""
        engine = AlphaBetaEngine(depth_limit=1)
        board_w = StandardBoard.from_fen("W:WK11:BK48")
        board_b = StandardBoard.from_fen("B:WK11:BK48")
        sw = engine.evaluate(board_w)
        sb = engine.evaluate(board_b)
        assert abs(sw + sb) < 0.2, f"not symmetric: {sw} vs {sb}"


# ---------------------------------------------------------------------------
# Tactical puzzles.
# ---------------------------------------------------------------------------
class TestTacticsAmerican:
    def test_picks_capture_when_optional(self):
        """American allows non-captures. A shallow engine must still prefer a
        free capture over a quiet move."""
        board = AmericanBoard.from_fen("W:W22,31:B18,24")
        engine = AlphaBetaEngine(depth_limit=2)
        move = engine.get_best_move(board)
        assert move.captured_list, (
            f"engine skipped a free capture in {board.fen}, played {move}"
        )


class TestTacticsStandard:
    def test_engine_prefers_bigger_multi_capture(self):
        """Standard enforces maximum captures in legal_moves. The engine must
        play a 2-capture chain when one is available — a sanity check that
        forced-capture flow isn't broken by pruning."""
        # White man at 38 chains: 38 -> 29 (captures 33) -> 20 (captures 24).
        board = StandardBoard.from_fen("W:W38:B33,24")
        engine = AlphaBetaEngine(depth_limit=3)
        move = engine.get_best_move(board)
        assert move.captured_list, f"no capture played: {move}"
        assert len(move.captured_list) >= 2, (
            f"expected multi-capture, got {move} with "
            f"{len(move.captured_list)} captures"
        )


# ---------------------------------------------------------------------------
# Search stability: deeper search should not produce a worse move for the
# side to move than shallower search across a handful of quiet midgame
# positions. This catches over-aggressive pruning regressions.
# ---------------------------------------------------------------------------
class TestSearchStability:
    @pytest.mark.parametrize("plies", [0, 6, 10])
    def test_deeper_is_never_catastrophically_worse(self, plies):
        from test._test_helpers import standard_board_after_random_play
        board = standard_board_after_random_play(seed=7, plies=plies)
        if board.game_over:
            pytest.skip("random play ended the game early")

        e_shallow = AlphaBetaEngine(depth_limit=2)
        e_deep = AlphaBetaEngine(depth_limit=4)

        _, s_shallow = e_shallow.get_best_move(board, with_evaluation=True)
        _, s_deep = e_deep.get_best_move(board, with_evaluation=True)

        # Deep search sees further and its score is more accurate. It should
        # not be dramatically lower than the shallow estimate (some drift is
        # OK — tactical shots change perspective — but a huge gap signals
        # broken pruning).
        assert s_deep > s_shallow - 5.0, (
            f"deep search much worse than shallow after {plies} random plies: "
            f"shallow={s_shallow:+.2f}, deep={s_deep:+.2f}"
        )


# ---------------------------------------------------------------------------
# End-to-end: a depth-4 engine should beat or draw a depth-2 engine of the
# same type over a handful of seeded games. This is our cheapest proxy for
# "the engine gets stronger with depth," which must hold if search is sane.
# ---------------------------------------------------------------------------
class TestDepthScalesWithStrength:
    def test_deep_beats_shallow_in_self_play(self):
        from draughts.models import Color
        wins, losses, draws = 0, 0, 0
        for seed in range(4):
            board = StandardBoard()
            e_deep = AlphaBetaEngine(depth_limit=5)
            e_shallow = AlphaBetaEngine(depth_limit=3)
            deep_is_white = (seed % 2 == 0)

            plies = 0
            while not board.game_over and plies < 140:
                eng = (e_deep if (board.turn == Color.WHITE) == deep_is_white
                       else e_shallow)
                board.push(eng.get_best_move(board))
                plies += 1

            if board.result == "1/2-1/2" or board.result == "-":
                draws += 1
            elif (board.result == "1-0") == deep_is_white:
                wins += 1
            else:
                losses += 1

        # Deeper engine must never lose to the shallower one in this tiny
        # test. If it ever does, something in search pruning is broken.
        assert losses == 0, f"deep lost games: {wins}W {losses}L {draws}D"
        # And it should be winning the majority.
        assert wins >= 2, f"deep didn't dominate: {wins}W {losses}L {draws}D"
