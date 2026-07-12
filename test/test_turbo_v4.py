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


# --- Task 4: TPW2 weights format + learned king PST -------------------------

def test_tpw2_roundtrip(tmp_path, monkeypatch):
    import struct as st
    from draughts.engines import turbo
    nH, nT, E = 11, 6, 6561
    rng = random.Random(1)
    men = [rng.randint(-500, 500) for _ in range(2 * (nH + nT) * E)]
    king = [rng.randint(-200, 200) for _ in range(100)]
    p = tmp_path / "w.bin"
    p.write_bytes(b"TPW2" + st.pack("<HHHH", nH, nT, E, 50)
                  + st.pack(f"<{len(men)}h", *men)
                  + st.pack(f"<{len(king)}h", *king))
    monkeypatch.setattr(turbo, "WEIGHTS_FILE", str(p))
    pat_h, pat_t, kpst = turbo._load_weights_file()
    # spot-check packing: pattern 0 cell 0
    assert pat_h[0][0] == turbo.pack(men[0], men[1])
    assert kpst[0] == (king[0], king[1])


def test_king_pst_override_replaces_hand_pst():
    """_build_eval_tables(king_pst) is pure -- exercise it directly (no
    monkeypatching / global mutation) to pin down the exact king semantics
    from the brief: white square s -> pack(KING_VALUE + kmg[s],
    KING_VALUE + keg[s]); black at s mirrors 49 - s, negated."""
    rng = random.Random(5)
    king_pst = tuple((rng.randint(-200, 200), rng.randint(-200, 200)) for _ in range(50))
    _, wk_t, _, bk_t = turbo._build_eval_tables(king_pst)
    for s in range(50):
        b = turbo.S2B[s]
        c, local = divmod(b, 7)
        window = 1 << local
        mg, eg = king_pst[s]
        assert wk_t[c][window] == turbo.pack(turbo.KING_VALUE + mg, turbo.KING_VALUE + eg)
        mirror = 49 - s
        mmg, meg = king_pst[mirror]
        assert bk_t[c][window] == turbo.pack(
            -(turbo.KING_VALUE + mmg), -(turbo.KING_VALUE + meg)
        )


def test_king_pst_none_matches_hand_pst_default():
    # Default (king_pst=None) must reproduce the module's own live tables
    # byte-for-byte: the shipped weights file is TPW1, so _apply_weights_file
    # never rebuilds the king chunk tables, and the hand PST stays in force.
    assert turbo._build_eval_tables(None) == (turbo.WM_T, turbo.WK_T, turbo.BM_T, turbo.BK_T)


def test_load_weights_file_real_tpw1_has_noop_king():
    # The shipped weights file is TPW1: king_pst must be None (hand king PST
    # stays in force) and the tall-pattern block must be an all pack(0, 0)
    # no-op (TPW1 doesn't carry tall weights).
    pat_h, pat_t, king_pst = turbo._load_weights_file()
    assert king_pst is None
    assert len(pat_h) == turbo.N_PATTERNS
    assert len(pat_t) == turbo.N_PATTERNS_T
    zero = turbo.pack(0, 0)
    assert all(v == zero for row in pat_t for v in row)


def test_load_weights_file_tpw2_count_mismatch_is_none(tmp_path, monkeypatch):
    import struct as st
    # Wrong n_king (49 instead of 50) must be rejected -> None (fallback).
    p = tmp_path / "bad.bin"
    p.write_bytes(b"TPW2" + st.pack("<HHHH", 11, 6, 6561, 49))
    monkeypatch.setattr(turbo, "WEIGHTS_FILE", str(p))
    assert turbo._load_weights_file() is None


def test_load_weights_file_missing_file_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(turbo, "WEIGHTS_FILE", str(tmp_path / "does_not_exist.bin"))
    assert turbo._load_weights_file() is None


def test_load_weights_file_bad_magic_is_none(tmp_path, monkeypatch):
    p = tmp_path / "bad_magic.bin"
    p.write_bytes(b"NOPE" + b"\x00" * 20)
    monkeypatch.setattr(turbo, "WEIGHTS_FILE", str(p))
    assert turbo._load_weights_file() is None
