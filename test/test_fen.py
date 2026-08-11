"""FEN parsing/emission guarantees shared by every variant.

Complements the per-variant board tests with checks that run over all eight
variants uniformly:

* men on their own promotion row are rejected (issue #47), while kings there
  and men on the *opponent's* promotion row stay legal;
* ``board.fen`` -> ``from_fen`` round-trips bit-exactly from randomly played
  positions, so the emitter can never produce a FEN the parser refuses or
  reinterprets.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from test._test_helpers import BOARDS

VARIANTS = sorted(BOARDS)


def _squares(mask: int) -> list[int]:
    """1-indexed squares of a promotion-row bitmask."""
    return [i + 1 for i in range(mask.bit_length()) if mask & (1 << i)]


# --------------------------------------------------------------------------- #
# Issue #47: a man on its own promotion row is an illegal FEN.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("variant", VARIANTS)
def test_rejects_man_on_own_promotion_row(variant):
    cls = BOARDS[variant]
    white_promo = _squares(cls.PROMO_WHITE)
    black_promo = _squares(cls.PROMO_BLACK)
    last = cls.SQUARES_COUNT

    for sq in white_promo:
        with pytest.raises(ValueError, match="promotion"):
            cls.from_fen(f"W:W{sq}:B{last}")
    for sq in black_promo:
        with pytest.raises(ValueError, match="promotion"):
            cls.from_fen(f"W:WK1:B{sq}")


@pytest.mark.parametrize("variant", VARIANTS)
def test_rejects_range_touching_promotion_row(variant):
    """Ranges expand square by square, so a range grazing the promotion row
    must be rejected just like an explicit square (issue #47 + #33)."""
    cls = BOARDS[variant]
    first_white_promo = _squares(cls.PROMO_WHITE)[0]
    with pytest.raises(ValueError, match="promotion"):
        cls.from_fen(f"W:W{first_white_promo}-{first_white_promo + 1}:B{cls.SQUARES_COUNT}")


@pytest.mark.parametrize("variant", VARIANTS)
def test_accepts_king_on_promotion_row(variant):
    cls = BOARDS[variant]
    wp = _squares(cls.PROMO_WHITE)[0]
    bp = _squares(cls.PROMO_BLACK)[0]
    board = cls.from_fen(f"W:WK{wp}:BK{bp}")
    assert board._get(wp - 1) == -2
    assert board._get(bp - 1) == 2


@pytest.mark.parametrize("variant", VARIANTS)
def test_accepts_man_on_opponent_promotion_row(variant):
    """A man one move away from crowning stands on the *opponent's* side of
    the board and never on its own promotion row -- placing a white man on
    black's promotion row (and vice versa) must stay legal."""
    cls = BOARDS[variant]
    white_on_black_promo = _squares(cls.PROMO_BLACK)[0]
    black_on_white_promo = _squares(cls.PROMO_WHITE)[0]
    board = cls.from_fen(f"W:W{white_on_black_promo}:B{black_on_white_promo}")
    assert board._get(white_on_black_promo - 1) == -1
    assert board._get(black_on_white_promo - 1) == 1


# --------------------------------------------------------------------------- #
# Round-trip: fen -> from_fen must reproduce the position bit-for-bit for
# every variant, from many randomly played (hence legal) positions.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("seed", range(5))
def test_fen_roundtrip_random_play(variant, seed):
    cls = BOARDS[variant]
    board = cls()
    rng = random.Random(seed)

    for _ in range(60):
        fen = board.fen
        clone = cls.from_fen(fen)
        assert clone.white_men == board.white_men, fen
        assert clone.white_kings == board.white_kings, fen
        assert clone.black_men == board.black_men, fen
        assert clone.black_kings == board.black_kings, fen
        assert clone.turn == board.turn, fen
        # And the reparsed board must emit the identical string again.
        assert clone.fen == fen

        moves = board.legal_moves
        if not moves:
            break
        board.push(rng.choice(moves))


@pytest.mark.parametrize("variant", VARIANTS)
def test_emitted_fen_never_places_man_on_promotion_row(variant):
    """The emitter's own output must satisfy the parser's promotion-row rule:
    push() crowns every man that lands on the row, so a man there can only
    appear through state corruption -- random play must never surface one."""
    cls = BOARDS[variant]
    board = cls()
    rng = random.Random(1234)
    for _ in range(120):
        assert board.white_men & cls.PROMO_WHITE == 0
        assert board.black_men & cls.PROMO_BLACK == 0
        moves = board.legal_moves
        if not moves:
            break
        board.push(rng.choice(moves))


# --------------------------------------------------------------------------- #
# Parser robustness: forms that must parse and forms that must raise.
# --------------------------------------------------------------------------- #
def test_wrapped_and_bare_fens_parse_identically():
    cls = BOARDS["standard"]
    bare = cls.from_fen("B:W31,K6:B20,K45")
    wrapped = cls.from_fen('[FEN "B:W31,K6:B20,K45"]')
    assert np.array_equal(bare.position, wrapped.position)
    assert bare.turn == wrapped.turn


def test_lowercase_fen_parses():
    cls = BOARDS["standard"]
    board = cls.from_fen("b:w31,k6:b20")
    assert board.turn.value == 1  # black
    assert board._get(30) == -1
    assert board._get(5) == -2


@pytest.mark.parametrize(
    "fen",
    [
        "",  # empty
        "X:W31:B20",  # bad turn token
        "W:W31;B20",  # bad separator
        "W31:B20",  # missing turn field
        "W:WB:B20",  # stray piece letter inside list
    ],
)
def test_malformed_fens_raise(fen):
    with pytest.raises(ValueError):
        BOARDS["standard"].from_fen(fen)
