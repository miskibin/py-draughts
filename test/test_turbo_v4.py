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
