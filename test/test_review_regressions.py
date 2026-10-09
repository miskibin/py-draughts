"""Concrete regressions found during the engine/performance review."""

import copy
import random

import pytest

from draughts import (
    AntidraughtsBoard,
    BenchmarkStats,
    Board,
    BreakthroughBoard,
    Color,
    FrisianBoard,
    FryskBoard,
    GameResult,
    Move,
    TurboEngine,
)
from draughts.benchmark import _play_game
from draughts.boards._draw import advance_clock, endgame_limits
from draughts.engines import turbo
from tools.compare_turbo import paired_summary


def test_threefold_includes_initial_position_and_pop():
    board = Board.from_fen("W:WK1,31:BK50,20")
    cycle = ["1-6", "50-45", "6-1", "45-50"]
    for move in cycle:
        board.push_uci(move)
    assert not board.is_threefold_repetition
    for move in cycle:
        board.push_uci(move)
    assert board.is_threefold_repetition
    assert copy.deepcopy(board).is_threefold_repetition
    board.pop()
    assert not board.is_threefold_repetition


def test_threefold_detects_longer_than_four_ply_cycle():
    board = Board.from_fen("W:WK1,31:BK50,20")
    cycle = ["1-7", "50-44", "7-12", "44-39", "12-1", "39-50"]
    for move in cycle * 2:
        board.push_uci(move)
    assert board.is_threefold_repetition


def test_same_moves_do_not_imply_same_positions():
    board = Board.from_fen("W:WK1,31:BK50,20")
    # Black advances a man while White shuffles its king. White's identical
    # moves at plies 1/5/9 must not trigger the old heuristic draw.
    for move in ["1-6", "20-24", "6-1", "24-30", "1-6", "30-34", "6-1", "34-39", "1-6"]:
        board.push_uci(move)
    assert not board.is_threefold_repetition


@pytest.mark.parametrize(
    "counts,expected",
    [
        ((0, 1, 0, 1), (-1, 10)),
        ((0, 2, 0, 1), (-1, 10)),
        ((1, 1, 0, 1), (-1, 10)),
        ((0, 3, 0, 1), (32, -1)),
        ((1, 2, 0, 1), (32, -1)),
        ((2, 1, 0, 1), (32, -1)),
        ((0, 2, 0, 2), (-1, -1)),
        ((2, 0, 0, 1), (-1, -1)),
    ],
)
def test_fmjd_endgame_material_conditions(counts, expected):
    assert endgame_limits(*counts) == expected
    assert endgame_limits(*counts[2:], *counts[:2]) == expected


def test_endgame_clock_survives_man_move_and_board_copy():
    board = Board.from_fen("W:W31,K1:BK50")
    assert board._endgame_remaining == (-1, 10)
    board.push_uci("31-26")
    assert board.halfmove_clock == 0
    assert board._endgame_remaining == (-1, 9)
    assert board.copy()._endgame_remaining == (-1, 9)
    assert copy.deepcopy(board)._endgame_remaining == (-1, 9)
    board.pop()
    assert board._endgame_remaining == (-1, 10)


def test_king_vs_king_five_move_rule():
    board = Board.from_fen("W:WK1:BK50")
    cycle = ["1-7", "50-44", "7-12", "44-39", "12-1", "39-50"]
    for move in (cycle * 2)[:9]:
        board.push_uci(move)
    assert not board.is_5_moves_rule
    board.push_uci(cycle[3])
    assert board.is_5_moves_rule


def test_sixteen_move_clock_survives_capture_into_five_move_ending():
    board = Board.from_fen("W:WK1,K2,K3:BK50")
    wm, wk, bm, bk = TurboEngine._convert(board)
    # A previously active 16-move clock keeps counting while the new
    # five-move clock starts; captures do not give another sixteen moves.
    assert advance_clock(wm, wk ^ turbo.BIT[2], bm, bk, (7, -1)) == (6, 10)
    assert advance_clock(wm, wk, bm, bk, (0, -1))[0] == 0


def test_board_reconstructs_clock_across_capture_and_undo():
    board = Board.from_fen("B:WK1,K2,K33:BK50")
    assert board._endgame_remaining == (32, -1)
    board.push_uci("50x28")
    assert board._endgame_remaining == (31, 10)
    assert copy.deepcopy(board)._endgame_remaining == (31, 10)
    assert board.copy()._endgame_remaining == (31, 10)
    board.pop()
    assert board._endgame_remaining == (32, -1)


def test_quiet_moves_do_not_share_mutable_capture_lists():
    first, second = Move([30, 25]), Move([31, 26])
    first.captured_list.append(12)
    first.captured_entities.append(1)
    assert second.captured_list == second.captured_entities == []
    assert Move([32, 27]).captured_list == []


@pytest.mark.parametrize("notation", ["1x23x12x23", "1x12x23x23"])
def test_explicit_capture_path_must_match_order_and_length(notation):
    legal = Move([0, 11, 22], [6, 17], [1, 1])
    with pytest.raises(ValueError):
        Move.from_uci(notation, [legal])
    assert Move.from_uci("1x23", [legal]) is legal
    assert Move.from_uci("1x12x23", [legal]) is legal


@pytest.mark.parametrize("fen", ["W:W31:B20garbage", "W:W31:B20K", "W:W31:B20,ZZ"])
def test_fen_rejects_truncated_black_piece_list(fen):
    with pytest.raises(ValueError):
        Board.from_fen(fen)


@pytest.mark.parametrize("cls", [FrisianBoard, FryskBoard, AntidraughtsBoard, BreakthroughBoard])
def test_turbo_rejects_other_ten_by_ten_variants(cls):
    with pytest.raises(ValueError, match="international"):
        TurboEngine(depth_limit=1).get_best_move(cls())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"depth_limit": 0},
        {"depth_limit": -1},
        {"time_limit": 0},
        {"time_limit": -1},
        {"time_limit": float("nan")},
        {"time_limit": float("inf")},
    ],
)
def test_invalid_search_budgets_are_rejected(kwargs):
    with pytest.raises(ValueError):
        TurboEngine(**kwargs)


def test_terminal_loss_at_quiescence_horizon():
    board = Board.from_fen("W:W6:B1")  # blocked man; neither side can capture
    engine = TurboEngine(depth_limit=1)
    assert not board.legal_moves
    score = engine._negamax(*engine._convert(board), True, 0, -turbo.INF, turbo.INF, 3, 0)
    assert score == -turbo.MATE + 3


def test_forced_capture_evaluation_searches_the_move():
    board = Board.from_fen("W:W28:B23")
    move, score = TurboEngine(depth_limit=1).get_best_move(board, with_evaluation=True)
    assert str(move) == "28x19"
    assert score > 600  # capturing the last piece is a terminal win


def test_clock_draw_and_terminal_win_precedence():
    board = Board.from_fen("W:W6:B1")
    engine = TurboEngine(depth_limit=1)
    score = engine._negamax(*engine._convert(board), True, 0, -turbo.INF, turbo.INF, 1, 50, (0, 0))
    assert score == -turbo.MATE + 1


def test_tt_mate_scores_are_relative_to_current_ply():
    board = Board.from_fen("W:W28:B23")
    engine = TurboEngine(depth_limit=1)
    bits = engine._convert(board)
    first = engine._negamax(*bits, True, 1, -turbo.INF, turbo.INF, 1, 0)
    second = engine._negamax(*bits, True, 1, -turbo.INF, turbo.INF, 7, 0)
    assert first == turbo.MATE - 2
    assert second == turbo.MATE - 8


def test_tt_does_not_overstate_depth_after_forced_reply_extension():
    board = Board.from_fen("W:W28:B23")
    engine = TurboEngine(depth_limit=1)
    bits = engine._convert(board)
    engine._negamax(*bits, True, 1, -turbo.INF, turbo.INF, 1, 0)
    assert engine.tt[(*bits, True, 0, (-1, -1))][0] == 1


def test_search_counts_third_occurrence_not_second():
    board = Board.from_fen("W:WK1,31:BK50,20")
    engine = TurboEngine(depth_limit=1)
    bits = engine._convert(board)
    key = (*bits, True)
    engine._path[key] = 2
    assert engine._negamax(*bits, True, 1, -turbo.INF, turbo.INF, 1, 8) == 0
    engine._path[key] = 1
    # A cached position without this history must not override repetition.
    engine._negamax(*bits, True, 1, -turbo.INF, turbo.INF, 1, 4)
    assert engine._path[key] == 1


def test_search_does_not_reuse_tt_scores_at_different_draw_clocks():
    board = Board.from_fen("W:WK1,31:BK50,20")
    bits = TurboEngine._convert(board)
    warmed = TurboEngine(depth_limit=2)
    warmed._negamax(*bits, True, 2, -turbo.INF, turbo.INF, 1, 0)
    warm_score = warmed._negamax(*bits, True, 2, -turbo.INF, turbo.INF, 1, 49)
    fresh_score = TurboEngine(depth_limit=2)._negamax(*bits, True, 2, -turbo.INF, turbo.INF, 1, 49)
    assert warm_score == fresh_score


def test_dodge_extension_preserves_draw_clocks(monkeypatch):
    board = Board.from_fen("W:WK1,31:BK50,20")
    engine = TurboEngine(depth_limit=1)
    calls = []
    monkeypatch.setattr(turbo, "_has_capture", lambda *args: True)
    monkeypatch.setattr(engine, "_negamax", lambda *args: calls.append(args) or 0)
    engine._qs_quiet(*engine._convert(board), True, -100, 100, 3, True, 49, (2, 3))
    assert calls[0][-2:] == (49, (2, 3))


def test_aspiration_bound_is_not_salvaged_as_an_exact_score(monkeypatch):
    board = Board()
    engine = TurboEngine(depth_limit=1)
    bits = engine._convert(board)
    moves = turbo._gen_quiets(*bits, True)
    monkeypatch.setattr(engine, "_negamax", lambda *args: -20)
    engine._root_iter(*bits, True, 0, moves, 1, -10, 10)
    assert engine._partial_mv is None  # 20 is a fail-high bound
    assert not engine._path


def test_aspiration_retry_clears_previous_partial_result(monkeypatch):
    board = Board()
    engine = TurboEngine(depth_limit=1)
    bits = engine._convert(board)
    moves = turbo._gen_quiets(*bits, True)
    engine._partial_mv, engine._partial_score = moves[-1], 1000

    def timeout(*args):
        raise turbo._Timeout

    monkeypatch.setattr(engine, "_negamax", timeout)
    with pytest.raises(turbo._Timeout):
        engine._root_iter(*bits, True, 0, moves, 1, -100, 100)
    assert engine._partial_mv is None
    assert not engine._path


def test_exact_partial_result_survives_timeout(monkeypatch):
    board = Board()
    engine = TurboEngine(depth_limit=1)
    bits = engine._convert(board)
    moves = turbo._gen_quiets(*bits, True)
    calls = 0

    def result_then_timeout(*args):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise turbo._Timeout
        return -5

    monkeypatch.setattr(engine, "_negamax", result_then_timeout)
    move, score = engine._search_root(*bits, True, 0)
    assert move == moves[0]
    assert score == 5
    assert engine.completed_depth == 0
    assert not engine._path


def test_static_eval_cache_has_fixed_capacity(monkeypatch):
    monkeypatch.setattr(turbo, "EVAL_CACHE_MAX", 2)
    monkeypatch.setattr(turbo, "_has_capture", lambda *args: False)
    engine = TurboEngine(depth_limit=1)
    for fen in ("W:W31:B20", "W:W32:B20", "W:W33:B20"):
        bits = engine._convert(Board.from_fen(fen))
        assert engine._qs_quiet(*bits, True, -1000, 1000, 1, False) == turbo._evaluate(*bits, True)
    assert len(engine._eval_cache) == 2


def test_folded_evaluation_matches_independent_unfolded_formula():
    rng = random.Random(1917)
    for _ in range(500):
        wm = wk = bm = bk = 0
        boards = [0, 0, 0, 0]
        for bit in turbo.BIT:
            kind = rng.randrange(5)
            if kind < 4:
                boards[kind] |= bit
        wm, wk, bm, bk = boards
        material = sum(
            turbo.WM_T[c][(wm >> (7 * c)) & 127]
            + turbo.WK_T[c][(wk >> (7 * c)) & 127]
            - turbo.BM_T[c][(bm >> (7 * c)) & 127]
            - turbo.BK_T[c][(bk >> (7 * c)) & 127]
            for c in range(9)
        )
        pattern = sum(row[index] for row, index in zip(turbo.PAT_W, turbo.pattern_indices(wm, bm)))
        empty = turbo.SQ_MASK ^ (wm | wk | bm | bk)
        mobility = turbo.MOBILITY_WEIGHT * (
            ((wm >> 6) & empty).bit_count()
            + ((wm >> 7) & empty).bit_count()
            - ((bm << 6) & empty).bit_count()
            - ((bm << 7) & empty).bit_count()
        )
        skew = turbo.SKEW_WEIGHT * (
            abs(
                ((bm | bk) & turbo.LEFT_MASK).bit_count()
                - ((bm | bk) & turbo.RIGHT_MASK).bit_count()
            )
            - abs(
                ((wm | wk) & turbo.LEFT_MASK).bit_count()
                - ((wm | wk) & turbo.RIGHT_MASK).bit_count()
            )
        )
        expected = material + pattern + mobility + skew
        assert turbo._evaluate(*boards, True) == expected
        assert turbo._evaluate(*boards, False) == -expected


class FirstMove:
    nodes = 0

    def get_best_move(self, board):
        return board.legal_moves[0]


@pytest.mark.parametrize(
    "cls,fen,winner",
    [
        (Board, "W:W28:B23", Color.WHITE),
        (AntidraughtsBoard, "W:W28:B23", Color.BLACK),
        (BreakthroughBoard, "W:W6:B20", Color.WHITE),
    ],
)
def test_benchmark_recognizes_last_ply_and_variant_wins(cls, fen, winner):
    result = _play_game(FirstMove(), FirstMove(), cls, 1, True, ("fixture", fen), 1)
    assert result.winner == winner
    assert result.termination != "max_moves"


def test_benchmark_averages_black_to_move_openings_correctly():
    game = GameResult(
        game_number=1,
        moves=3,
        e1_color=Color.WHITE,
        starting_color=Color.BLACK,
        e1_time=2,
        e2_time=6,
    )
    stats = BenchmarkStats(e1_name="a", e2_name="b", results=[game])
    assert stats.avg_time_e1 == 2
    assert stats.avg_time_e2 == 3
    assert BenchmarkStats(e1_name="a", e2_name="b").elo_diff == 0


def test_benchmark_accepts_wrapped_fen_from_board():
    fen = Board.from_fen("W:W28:B23").fen
    result = _play_game(FirstMove(), FirstMove(), Board, 1, True, ("fixture", fen), 1)
    assert result.winner == Color.WHITE


def test_paired_elo_does_not_claim_zero_uncertainty_for_all_wins():
    game = {"score": 1, "termination": "1-0", "seconds": [0, 0], "nodes": [0, 0]}
    result = paired_summary([{"games": [game, game]} for _ in range(4)])
    assert result["elo_95_ci"][0] < result["relative_elo"]
    assert result["relative_elo"] == float("inf")
