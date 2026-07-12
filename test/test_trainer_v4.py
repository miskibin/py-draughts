"""Tests for Task 5 of the TurboEngine v4 plan: trainer position hygiene.

Pure-function tests only -- no Scan engine runs (``clean_samples`` and the
sample-shape handling in ``build_features`` don't need self-play data)."""

import random

from tools.train_pattern_eval import clean_samples


def test_clean_samples_dedup_cap_and_range():
    s = lambda wm, sw, ply: (wm, 0, 1 << 40, 0, sw, 0.5, ply)
    samples = [s(1, 100, 5), s(1, 100, 6),          # dup position -> keep 1
               s(2, 9000, 5),                        # |score| too big -> drop
               s(4, 50, 1),                          # early ply -> drop
               s(8, 50, 5), s(16, 50, 5)]
    out = clean_samples(samples, max_abs=600, skip_plies=4, a=1.0)
    assert [x[0] for x in out] == [1, 8, 16]


def test_clean_samples_score_scaled_by_a():
    s = lambda wm, sw: (wm, 0, 1 << 40, 0, sw, 0.5, 10)
    samples = [s(1, 100), s(2, 400)]
    # a=2.0 doubles the effective score -> 400*2=800 exceeds max_abs=600.
    out = clean_samples(samples, max_abs=600, skip_plies=4, a=2.0)
    assert [x[0] for x in out] == [1]


def test_clean_samples_phase_balance_caps_and_downsamples():
    # Bucket key is popcount(wm) + popcount(bm): "small" sample sits alone in
    # a men_total=1 bucket, "big" samples all share a men_total=3 bucket
    # (wm has 1 bit, bm=0b11 has 2 bits) so the two groups never collide.
    small = [(1, 0, 0, 0, 0.0, 0.5, 10)]
    big = [(1 << i, 0, 0b11, 0, 0.0, 0.5, 10) for i in range(1, 11)]
    # bucket sizes [1, 10] -> median=5.5 -> cap=int(2.0*5.5)=11, no drops.
    out = clean_samples(small + big, max_abs=10_000, skip_plies=0)
    assert len(out) == 11

    # bucket sizes [1, 20] -> median=10.5 -> cap=int(0.5*10.5)=5: the
    # small bucket (size 1) survives uncapped, the big bucket is downsampled.
    big20 = [(1 << i, 0, 0b11, 0, 0.0, 0.5, 10) for i in range(1, 21)]
    out2 = clean_samples(small + big20, max_abs=10_000, skip_plies=0,
                          bucket_cap_mult=0.5, seed=1)
    assert 1 in [x[0] for x in out2]
    assert len(out2) == 1 + 5


def test_clean_samples_downsample_is_seeded_and_reproducible():
    big = [(1 << i, 0, 0, 0, 0.0, 0.5, 10) for i in range(20)]
    out_a = clean_samples(big, max_abs=10_000, skip_plies=0,
                          bucket_cap_mult=0.25, seed=42)
    out_b = clean_samples(big, max_abs=10_000, skip_plies=0,
                          bucket_cap_mult=0.25, seed=42)
    assert [x[0] for x in out_a] == [x[0] for x in out_b]


def test_clean_samples_preserves_stable_order():
    samples = [(1 << i, 0, 0, 0, 0.0, 0.5, 10) for i in range(6)]
    out = clean_samples(samples, max_abs=10_000, skip_plies=0)
    assert [x[0] for x in out] == [1 << i for i in range(6)]


def test_build_features_accepts_7_tuples(monkeypatch):
    # build_features hardcodes P=N_PATTERNS(=11) but pattern_indices now
    # returns 17 entries (11 head + 6 tall patterns from Task 3) -- a known,
    # pre-existing, out-of-scope mismatch unrelated to sample-shape handling.
    # Stub pattern_indices so this test isolates the 7-tuple slicing logic.
    from tools.train_pattern_eval import build_features
    from draughts.engines import turbo

    monkeypatch.setattr(
        turbo, "pattern_indices", lambda wm, bm: [0] * turbo.N_PATTERNS)

    sample7 = (1, 0, 1 << 40, 0, 42.0, 0.5, 3)
    base, cells, result, scan = build_features([sample7])
    assert len(result) == 2  # incl. 180-deg augmented mirror
    assert scan[0] == 42.0
    assert scan[1] == -42.0
    assert result[0] == 0.5
