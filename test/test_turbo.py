"""Tests for TurboEngine: move-generator correctness (perft + cross-check)
and engine behavior."""

import random

import pytest

from draughts import Board
from draughts.engines.turbo import (
    B2S,
    SQ_MASK,
    TurboEngine,
    _gen_captures,
    _gen_quiets,
    perft_from_board,
)
from draughts.models import Color

# Perft anchors for the international start position (Aart Bik / BikDam).
PERFT_EXPECTED = {1: 9, 2: 81, 3: 658, 4: 4265, 5: 27117, 6: 167140}


def test_layout_mask_matches_scan():
    assert SQ_MASK == 0x7DF3EF9F7CFBE7DF


@pytest.mark.parametrize("depth,expected", sorted(PERFT_EXPECTED.items()))
def test_perft(depth, expected):
    assert perft_from_board(Board(), depth) == expected


def _internal_moveset(board: Board):
    wm, wk, bm, bk = TurboEngine._convert(board)
    white = board.turn == Color.WHITE
    moves = _gen_captures(wm, wk, bm, bk, white) or _gen_quiets(wm, wk, bm, bk, white)
    out = set()
    for frm, to, caps in moves:
        squares = set()
        c = caps
        while c:
            lsb = c & -c
            squares.add(B2S[lsb.bit_length() - 1])
            c ^= lsb
        out.add((B2S[frm.bit_length() - 1], B2S[to.bit_length() - 1], frozenset(squares)))
    return out


def _board_moveset(board: Board):
    return {
        (m.square_list[0], m.square_list[-1], frozenset(m.captured_list)) for m in board.legal_moves
    }


def test_movegen_matches_board_on_random_games():
    rng = random.Random(7)
    for _ in range(30):
        board = Board()
        for _ in range(120):
            legal = board.legal_moves
            if not legal or board.game_over:
                break
            assert _internal_moveset(board) == _board_moveset(board), board.fen
            board.push(rng.choice(legal))


def test_engine_returns_legal_move():
    board = Board()
    engine = TurboEngine(depth_limit=4)
    for _ in range(30):
        if board.game_over:
            break
        move = engine.get_best_move(board)
        assert any(
            move.square_list == m.square_list and move.captured_list == m.captured_list
            for m in board.legal_moves
        )
        board.push(move)


def test_engine_with_evaluation():
    board = Board()
    move, score = TurboEngine(depth_limit=3).get_best_move(board, with_evaluation=True)
    assert move is not None
    assert isinstance(score, float)


def test_engine_respects_time_limit():
    import time

    board = Board()
    engine = TurboEngine(depth_limit=None, time_limit=0.2)
    t0 = time.perf_counter()
    engine.get_best_move(board)
    assert time.perf_counter() - t0 < 2.0


def test_engine_beats_random():
    rng = random.Random(3)
    engine = TurboEngine(depth_limit=4)
    wins = 0
    games = 4
    for i in range(games):
        board = Board()
        engine_is_white = i % 2 == 0
        while not board.game_over and len(board._moves_stack) < 300:
            is_engine_turn = (board.turn == Color.WHITE) == engine_is_white
            if is_engine_turn:
                move = engine.get_best_move(board)
            else:
                move = rng.choice(board.legal_moves)
            board.push(move)
        result = board.result
        if (engine_is_white and result == "1-0") or (not engine_is_white and result == "0-1"):
            wins += 1
    assert wins == games


def test_engine_rejects_non_international_board():
    from draughts.boards.american import Board as AmericanBoard

    with pytest.raises(ValueError):
        TurboEngine(depth_limit=3).get_best_move(AmericanBoard())


def test_shipped_weights_are_active():
    """The distributed turbo_weights.bin must load into a non-zero pattern
    eval (a regression guard against a missing/corrupt weights file)."""
    from draughts.engines import turbo

    assert turbo._weights_path() == turbo.WEIGHTS_FILE
    weights = turbo._load_pattern_weights()
    assert any(any(row) for row in weights)


@pytest.mark.parametrize("sentinel", ["none", "off", "0", "disabled"])
def test_turbo_weights_env_disables_pattern_term(monkeypatch, sentinel):
    """TURBO_WEIGHTS=<sentinel> disables the trained pattern correction so the
    eval falls back to the v2 hand eval (all-zero pattern weights)."""
    from draughts.engines import turbo

    monkeypatch.setenv("TURBO_WEIGHTS", sentinel)
    assert turbo._weights_path() is None
    weights = turbo._load_pattern_weights()
    assert all(not any(row) for row in weights)


def test_turbo_weights_env_custom_path(monkeypatch):
    """A custom TURBO_WEIGHTS path is honoured; a missing file degrades to the
    zero (hand-eval) fallback rather than raising."""
    from draughts.engines import turbo

    monkeypatch.setenv("TURBO_WEIGHTS", "/nonexistent/turbo_weights.bin")
    assert turbo._weights_path() == "/nonexistent/turbo_weights.bin"
    weights = turbo._load_pattern_weights()
    assert all(not any(row) for row in weights)
