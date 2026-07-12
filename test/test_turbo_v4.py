"""Regression test for Task 2 of the TurboEngine v4 plan: the packed
tapered (mg/eg) eval core must be exactly score-preserving versus the
frozen v3 reference (mg == eg everywhere until v4 weights exist)."""

import random

from draughts import Board
from draughts.engines import turbo
from tools.checkpoints import turbo_v3


def _random_positions(n=300, seed=7):
    rng = random.Random(seed)
    out = []
    b = Board()
    for _ in range(n):
        if b.game_over or rng.random() < 0.02:
            b = Board()
        b.push(rng.choice(b.legal_moves))
        out.append(turbo.TurboEngine._convert(b) + (b.turn.name == "WHITE",))
    return out


def test_packed_eval_matches_v3_exactly():
    for wm, wk, bm, bk, wtm in _random_positions():
        assert turbo._evaluate(wm, wk, bm, bk, wtm) == \
            turbo_v3._evaluate(wm, wk, bm, bk, wtm)


def _crafted_king_positions(n=200, seed=11):
    """Deterministic synthetic positions guaranteed to contain BOTH white
    and black kings plus men: the random-walk block above almost never
    promotes (seed 7 yields zero white kings), so this block is what
    actually exercises the packed WK_T/BK_T paths with nonzero values."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        n_wk = rng.randint(1, 6)
        n_bk = rng.randint(1, 6)
        n_wm = rng.randint(4, 19)
        n_bm = rng.randint(4, 19)  # max total 6+6+19+19 = 50 distinct squares
        squares = rng.sample(range(50), n_wk + n_bk + n_wm + n_bm)
        it = iter(squares)
        wk = sum(turbo.BIT[next(it)] for _ in range(n_wk))
        bk = sum(turbo.BIT[next(it)] for _ in range(n_bk))
        wm = sum(turbo.BIT[next(it)] for _ in range(n_wm))
        bm = sum(turbo.BIT[next(it)] for _ in range(n_bm))
        for wtm in (True, False):
            out.append((wm, wk, bm, bk, wtm))
    return out


def test_packed_eval_matches_v3_with_kings():
    positions = _crafted_king_positions()
    # Coverage guard: every composition has white AND black kings.
    assert all(wk and bk for _, wk, _, bk, _ in positions)
    for wm, wk, bm, bk, wtm in positions:
        assert turbo._evaluate(wm, wk, bm, bk, wtm) == \
            turbo_v3._evaluate(wm, wk, bm, bk, wtm)


# --- Task 3: tall 2x4 patterns (must be a zero-weight no-op) ----------------

def test_tall_pattern_indices_match_bruteforce():
    rng = random.Random(3)
    for _ in range(200):
        wm = bm = 0
        for s in rng.sample(range(50), rng.randint(4, 30)):
            if rng.random() < 0.5:
                wm |= turbo.BIT[s]
            else:
                bm |= turbo.BIT[s]
        idxs = turbo.pattern_indices(wm, bm)
        assert len(idxs) == turbo.N_PATTERNS_ALL
        for p, squares in enumerate(turbo.PATTERNS_H + turbo.PATTERNS_T):
            want = sum(
                (1 if wm & turbo.BIT[sq] else 2 if bm & turbo.BIT[sq] else 0) * 3 ** i
                for i, sq in enumerate(squares))
            assert idxs[p] == want, (p, squares)


def test_untrained_tall_patterns_are_noop():
    # with shipped TPW1 (11-pattern) weights, tall weights are zero:
    # scores must still equal v3 exactly (reuses the Task 2 check).
    test_packed_eval_matches_v3_exactly()
