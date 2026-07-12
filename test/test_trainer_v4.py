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


# --- Task 6: COO features (phase + kings) + TPW2 writer ---------------------

def test_coo_fit_recovers_planted_king_weight(tmp_path, monkeypatch):
    """Synthetic planted-signal recovery + writer/loader round-trip.

    Plant a white king on square 22 worth +150 mg / +90 eg *over*
    ``KING_VALUE``. Build ~2000 random-men positions that all carry that
    king, set the regression target to ``base + planted_king_contribution``
    (computed through the exact COO forward model so it is self-consistent
    with the fit), and require the fit to recover both the mg and eg deltas
    within +-15. Then write the trained vector to a TPW2 file and confirm it
    round-trips byte-for-byte through ``turbo._load_weights_file``.
    """
    import numpy as np

    from draughts.engines import turbo
    from draughts.engines.turbo import BIT, N_PATTERNS_ALL, PAT_ENTRIES
    from tools.train_pattern_eval import (
        build_features_coo,
        fit_regression_coo,
        write_weights_tpw2,
    )

    KBASE = N_PATTERNS_ALL * PAT_ENTRIES * 2  # 223074
    n_weights = KBASE + 100
    KSQ = 22  # white king square carrying the planted signal

    rng = random.Random(0)
    samples = []
    for _ in range(2000):
        n_wm = rng.randint(5, 18)
        n_bm = rng.randint(5, 18)
        pool = [s for s in range(50) if s != KSQ]
        picks = rng.sample(pool, n_wm + n_bm)
        wm = 0
        for s in picks[:n_wm]:
            wm |= BIT[s]
        bm = 0
        for s in picks[n_wm:n_wm + n_bm]:
            bm |= BIT[s]
        wk = BIT[KSQ]  # planted white king
        bk = 0
        # 7-tuple (wm,wk,bm,bk,sw,res,ply); sw/res unused (target overridden).
        samples.append((wm, wk, bm, bk, 0.0, 0.5, 10))

    base, rows, cols, vals, _ = build_features_coo(samples)

    # Plant the ground-truth weights and synthesise the target through the
    # same E = base + bincount(rows, w[cols]*vals) forward model the fit uses.
    w_true = np.zeros(n_weights)
    w_true[KBASE + KSQ * 2] = 150.0
    w_true[KBASE + KSQ * 2 + 1] = 90.0
    target = base + np.bincount(
        rows, weights=w_true[cols] * vals, minlength=len(base)
    )

    # L2 (lam) must be large enough to suppress the ~66k rare, low-usage
    # pattern cells (which would otherwise memorise the target and starve the
    # king column) yet small enough not to over-shrink the king weight, which
    # is present in every row and is the only feature that generalises.
    w, tr_rmse, val_rmse, base_rmse = fit_regression_coo(
        base, rows, cols, vals, target, n_weights,
        lam=1e-3, iters=400, lr=5.0,
    )

    assert abs(w[KBASE + KSQ * 2] - 150) < 15, w[KBASE + KSQ * 2]
    assert abs(w[KBASE + KSQ * 2 + 1] - 90) < 15, w[KBASE + KSQ * 2 + 1]

    # writer -> loader round-trip equality.
    p = tmp_path / "v4.bin"
    write_weights_tpw2(str(p), w)
    monkeypatch.setattr(turbo, "WEIGHTS_FILE", str(p))
    loaded = turbo._load_weights_file()
    assert loaded is not None
    pat_h, pat_t, kpst = loaded
    assert len(pat_h) == turbo.N_PATTERNS
    assert len(pat_t) == turbo.N_PATTERNS_T
    assert len(kpst) == 50
    # king PST cell round-trips exactly (int16-rounded).
    assert kpst[KSQ] == (
        int(round(w[KBASE + KSQ * 2])),
        int(round(w[KBASE + KSQ * 2 + 1])),
    )
    # a men-pattern cell round-trips through the packed layout.
    assert pat_h[0][0] == turbo.pack(int(round(w[0])), int(round(w[1])))
    # tall block present and well-formed (last global pattern, index 16).
    assert pat_t[N_PATTERNS_ALL - turbo.N_PATTERNS - 1][0] == turbo.pack(
        int(round(w[(16 * PAT_ENTRIES) * 2])),
        int(round(w[(16 * PAT_ENTRIES) * 2 + 1])),
    )
