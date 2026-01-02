import pytest

from draughts.move import Move

from test._test_helpers import board_after_random_play, seeded_range


@pytest.mark.parametrize("variant", ["standard", "american"])
@pytest.mark.parametrize("seed", list(seeded_range(10)))
def test_uci_roundtrip_for_all_legal_moves_on_random_position(variant, seed):
    """For a position, every legal move's UCI should parse back to the same move."""
    board = board_after_random_play(variant, seed=seed, plies=20)
    legal_moves = list(board.legal_moves)

    for move in legal_moves:
        uci = str(move)
        parsed = Move.from_uci(uci, iter(legal_moves))
        assert parsed == move
        assert str(parsed) == uci
