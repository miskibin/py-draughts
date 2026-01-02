import numpy as np
import pytest

from draughts import get_board

from test._test_helpers import seeded_range


def _snapshot(board):
    return {
        "turn": board.turn,
        "halfmove_clock": board.halfmove_clock,
        "pos": board.position.copy(),
        "stack_len": len(board._moves_stack),
        "fen": board.fen,
    }


def _assert_state_equal(board, snapshot):
    assert board.turn == snapshot["turn"]
    assert board.halfmove_clock == snapshot["halfmove_clock"]
    assert len(board._moves_stack) == snapshot["stack_len"]
    assert board.fen == snapshot["fen"]
    assert np.array_equal(board.position, snapshot["pos"])


@pytest.mark.parametrize(
    "variant,seed,plies",
    [
        *[("standard", seed, 40) for seed in seeded_range(10)],
        *[("american", seed, 40) for seed in seeded_range(10)],
    ],
)
def test_push_pop_roundtrip_random_play(variant, seed, plies):
    """Random legal play should be perfectly reversible via pop()."""
    import random

    board = get_board(variant)
    rng = random.Random(seed)

    snapshots = [_snapshot(board)]
    played = []

    for _ in range(plies):
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            break
        move = rng.choice(legal_moves)
        board.push(move)
        played.append(move)
        snapshots.append(_snapshot(board))

    while played:
        expected_after_pop = snapshots[-2]
        last_played = played.pop()

        popped = board.pop()
        assert popped == last_played
        _assert_state_equal(board, expected_after_pop)

        snapshots.pop()

    _assert_state_equal(board, snapshots[0])


@pytest.mark.parametrize("variant", ["standard", "american"])
def test_every_legal_move_is_reversible_from_start(variant):
    """From the initial position, every legal move must push/pop cleanly."""
    board = get_board(variant)
    start = _snapshot(board)

    for move in list(board.legal_moves):
        board.push(move)
        board.pop()
        _assert_state_equal(board, start)
