"""
Offline trainer for TurboEngine v3's pattern evaluation.

Pipeline
--------
1. GENERATE self-play games with the frozen v2 checkpoint engine (fixed shallow
   depth) from many randomised openings, so positions are diverse.
2. SAMPLE fully-quiet positions (neither side has a capture) after the opening,
   label each with the game's final result from White's perspective.
3. FIT a Texel logistic model  p(white win) = sigmoid(K * E_white)  where
      E_white = base_v2_eval  +  sum_p  pattern_weight[p][idx_p]
   The v2 hand eval is a FIXED offset; only the pattern weights (a residual
   correction over men) and the scale K are trained, with L2 regularisation
   (most 3^8 pattern cells are rare).  180-degree colour-swapped augmentation
   removes side bias and doubles the signal.
4. WRITE the int16 weights to draughts/engines/turbo_weights.bin.

Runtime stays pure-Python: turbo.py loads the .bin with the stdlib only.

Usage:
    PYTHONPATH=D:/py-draughts python tools/train_pattern_eval.py \
        --games 6000 --workers 10 --depth 4 --out <bin path>

Only numpy is required here (offline); scipy is optional.
"""

from __future__ import annotations

import argparse
import os
import pickle
import random
import struct
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CKPT = os.path.join(
    os.environ.get("TURBO_CKPT_DIR", ""), ""
) if os.environ.get("TURBO_CKPT_DIR") else None
for p in (REPO,):
    if p not in sys.path:
        sys.path.insert(0, p)

# Checkpoint dir (frozen v2 engine) must be importable in workers too.
_CKPT_DIR = os.environ.get(
    "TURBO_CKPT_DIR",
    r"C:\Users\skibi\AppData\Local\Temp\claude\D--py-draughts"
    r"\2e8b3c62-698f-4a1d-9820-d432102b137a\scratchpad\checkpoints",
)
if _CKPT_DIR not in sys.path:
    sys.path.insert(0, _CKPT_DIR)


# ---------------------------------------------------------------------------
# Self-play data generation (worker side)
# ---------------------------------------------------------------------------

def _gen_games(args) -> list[tuple[int, int, int, int, float]]:
    """Play ``n`` self-play games; return sampled (wm,wk,bm,bk,result_white)."""
    seed, n, depth, max_plies, min_open, max_open, cap = args
    rng = random.Random(seed)

    from draughts import Board
    from draughts.models import Color
    import turbo_v2 as v2  # frozen checkpoint engine + movegen

    eng = v2.TurboEngine(depth_limit=depth, time_limit=None)
    samples: list[tuple[int, int, int, int, float]] = []

    for _ in range(n):
        board = Board()
        n_open = rng.randint(min_open, max_open)
        # Random opening plies for diversity.
        ok = True
        for _ in range(n_open):
            legal = board.legal_moves
            if not legal or board.game_over:
                ok = False
                break
            board.push(rng.choice(legal))
        if not ok:
            continue

        game_positions: list[tuple[int, int, int, int]] = []
        plies = 0
        while not board.game_over and plies < max_plies:
            wm, wk, bm, bk = v2.TurboEngine._convert(board)
            white = board.turn == Color.WHITE
            # Fully-quiet position: neither side has a capture.
            if not v2._has_capture(wm, wk, bm, bk, white) and not v2._has_capture(
                wm, wk, bm, bk, not white
            ):
                game_positions.append((wm, wk, bm, bk))
            move = eng.get_best_move(board)
            board.push(move)
            plies += 1

        # Result from White's perspective.
        if board.is_draw or plies >= max_plies:
            result = 0.5
        elif board.game_over:
            # Side to move has no moves -> it lost.
            result = 0.0 if board.turn == Color.WHITE else 1.0
        else:
            result = 0.5

        if len(game_positions) > cap:
            game_positions = rng.sample(game_positions, cap)
        for wm, wk, bm, bk in game_positions:
            samples.append((wm, wk, bm, bk, result))

    return samples


def _gen_games_scan(args):
    """Short Scan self-play rollouts; label every fully-quiet position with
    Scan's own search score (white perspective).  One search per ply already
    happens to pick the move, so the eval label is essentially free."""
    (seed, n, scan_path, move_time, roll_plies, min_open, max_open,
     cap) = args
    rng = random.Random(seed)

    from draughts import Board
    from draughts.models import Color
    import turbo_v2 as v2
    from draughts.engines import HubEngine

    samples = []
    with HubEngine(scan_path, time_limit=move_time) as eng:
        for _ in range(n):
            board = Board()
            n_open = rng.randint(min_open, max_open)
            ok = True
            for _ in range(n_open):
                lm = board.legal_moves
                if not lm or board.game_over:
                    ok = False
                    break
                board.push(rng.choice(lm))
            if not ok:
                continue

            game_positions = []  # (wm,wk,bm,bk, scan_white)
            hist = []            # positions in play order, to attach result
            plies = 0
            while not board.game_over and plies < roll_plies:
                wm, wk, bm, bk = v2.TurboEngine._convert(board)
                white = board.turn == Color.WHITE
                quiet = (not v2._has_capture(wm, wk, bm, bk, white)) and (
                    not v2._has_capture(wm, wk, bm, bk, not white)
                )
                mv, sc = eng.get_best_move(board, with_evaluation=True)
                if quiet:
                    sw = sc if white else -sc
                    game_positions.append((wm, wk, bm, bk, sw, plies))
                board.push(mv)
                plies += 1

            if board.is_draw or plies >= roll_plies:
                res = 0.5
            elif board.game_over:
                res = 0.0 if board.turn == Color.WHITE else 1.0
            else:
                res = 0.5

            if len(game_positions) > cap:
                game_positions = rng.sample(game_positions, cap)
            for wm, wk, bm, bk, sw, ply in game_positions:
                samples.append((wm, wk, bm, bk, sw, res, ply))
    return samples


def generate_scan(n_games, workers, scan_path, move_time, roll_plies,
                  min_open, max_open, cap, seed0):
    per = max(1, n_games // workers)
    tasks = []
    remaining, s = n_games, seed0
    while remaining > 0:
        g = min(per, remaining)
        tasks.append((s, g, scan_path, move_time, roll_plies,
                      min_open, max_open, cap))
        remaining -= g
        s += 1
    all_samples = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_gen_games_scan, t) for t in tasks]
        done = 0
        for f in as_completed(futs):
            all_samples.extend(f.result())
            done += 1
            print(f"  scan worker {done}/{len(tasks)} done, "
                  f"{len(all_samples)} samples, "
                  f"{time.perf_counter()-t0:.0f}s", flush=True)
    print(f"generated {len(all_samples)} scan-labelled samples in "
          f"{time.perf_counter()-t0:.0f}s")
    return all_samples


def generate(n_games, workers, depth, max_plies, min_open, max_open, cap, seed0):
    tasks = []
    per = max(1, n_games // workers)
    remaining = n_games
    s = seed0
    while remaining > 0:
        g = min(per, remaining)
        tasks.append((s, g, depth, max_plies, min_open, max_open, cap))
        remaining -= g
        s += 1

    all_samples: list = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_gen_games, t) for t in tasks]
        done = 0
        for f in as_completed(futs):
            all_samples.extend(f.result())
            done += 1
            print(
                f"  worker {done}/{len(tasks)} done, "
                f"{len(all_samples)} samples, {time.perf_counter()-t0:.0f}s",
                flush=True,
            )
    print(f"generated {len(all_samples)} raw samples in "
          f"{time.perf_counter()-t0:.0f}s")
    return all_samples


# ---------------------------------------------------------------------------
# Texel-style position hygiene
# ---------------------------------------------------------------------------

def clean_samples(samples, max_abs=600.0, skip_plies=4, bucket_cap_mult=2.0,
                  a=1.0, seed=0):
    """Clean up Scan-labelled rollout samples before feature building.

    ``samples`` are 7-tuples ``(wm, wk, bm, bk, sw, res, ply)`` as produced
    by ``_gen_games_scan``.  Applied in order:

      1. drop samples from the first ``skip_plies`` rollout plies (still
         close to the random opening, not representative quiet positions).
      2. drop samples where ``|a * sw| > max_abs`` (blown-out Scan scores --
         near-certain wins/losses/mate scores carry little Texel signal and
         can dominate the loss).
      3. de-duplicate by board key ``(wm, wk, bm, bk)``, keeping the first
         occurrence (the same position recurs across rollouts/games via
         transpositions and would otherwise be over-weighted).
      4. phase-balance: bucket the remaining samples by total man count
         (``bit_count(wm) + bit_count(bm)``), cap each bucket at
         ``int(bucket_cap_mult * median_nonempty_bucket_size)``, and
         randomly (``random.Random(seed)``) down-sample buckets above the
         cap.  Relative order is otherwise preserved.
    """
    out = [smp for smp in samples if smp[6] >= skip_plies]
    out = [smp for smp in out if abs(a * smp[4]) <= max_abs]

    seen = set()
    deduped = []
    for smp in out:
        key = smp[0], smp[1], smp[2], smp[3]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(smp)
    out = deduped

    buckets: dict = {}
    for i, smp in enumerate(out):
        wm, bm = smp[0], smp[2]
        men_total = bin(wm).count("1") + bin(bm).count("1")
        buckets.setdefault(men_total, []).append(i)

    sizes = sorted(len(idxs) for idxs in buckets.values() if idxs)
    if not sizes:
        return out
    mid = len(sizes) // 2
    median = (sizes[mid] if len(sizes) % 2
              else (sizes[mid - 1] + sizes[mid]) / 2.0)
    cap = int(bucket_cap_mult * median)

    rng = random.Random(seed)
    keep = set()
    for idxs in buckets.values():
        if len(idxs) > cap:
            keep.update(rng.sample(idxs, cap))
        else:
            keep.update(idxs)
    return [smp for i, smp in enumerate(out) if i in keep]


# ---------------------------------------------------------------------------
# Feature extraction + 180-degree augmentation
# ---------------------------------------------------------------------------

def _rot_map():
    """Internal-bit remap for a 180-degree board rotation (square s -> 49-s)."""
    import turbo_v2 as v2
    # bit -> bit for rotated square
    remap = {}
    for s in range(50):
        remap[v2.S2B[s]] = v2.S2B[49 - s]
    return remap


def _rot_bb(bb, remap):
    out = 0
    b = bb
    while b:
        lsb = b & -b
        bit = lsb.bit_length() - 1
        out |= 1 << remap[bit]
        b ^= lsb
    return out


def _men_pst(v2, wm, bm):
    """v2's men material+PST contribution (white perspective)."""
    s = 0
    for c in range(9):
        sh = c * 7
        s += v2.WM_T[c][(wm >> sh) & 127] - v2.BM_T[c][(bm >> sh) & 127]
    return s


def _base_white(v2, wm, wk, bm, bk, mode):
    """White-perspective fixed base eval, depending on the model formulation.

    mode 'full'   : entire v2 hand eval; patterns are a pure residual.
    mode 'matref' : v2 eval minus men PST plus flat men material, so patterns
                    learn ALL men positional value (advancement/centre/shape)
                    jointly instead of only interaction corrections.
    """
    full = v2._evaluate(wm, wk, bm, bk, True)
    if mode == "full":
        return full
    if mode == "matref":
        flat = 100 * (bin(wm).count("1") - bin(bm).count("1"))
        return full - _men_pst(v2, wm, bm) + flat
    raise ValueError(mode)


def build_features(samples, mode="full"):
    """Return (base, cells, result, scan) numpy arrays incl. augmented mirrors.

    Samples may be 5-tuples (wm,wk,bm,bk,result), 6-tuples
    (wm,wk,bm,bk,scan_white,result), or 7-tuples
    (wm,wk,bm,bk,scan_white,result,ply) -- the trailing ``ply`` (rollout
    position, used by ``clean_samples`` for hygiene) is ignored here.
    ``scan`` is NaN when unavailable.
    """
    import numpy as np
    import turbo_v2 as v2
    from draughts.engines.turbo import (
        pattern_indices,
        N_PATTERNS,
        PAT_ENTRIES,
    )

    remap = _rot_map()
    P = N_PATTERNS
    N = len(samples) * 2
    base = np.empty(N, dtype=np.float32)
    cells = np.empty((N, P), dtype=np.int32)
    result = np.empty(N, dtype=np.float32)
    scan = np.empty(N, dtype=np.float32)
    offs = np.arange(P, dtype=np.int32) * PAT_ENTRIES

    i = 0
    for s in samples:
        if len(s) >= 6:
            wm, wk, bm, bk, sw, res = s[0], s[1], s[2], s[3], s[4], s[5]
        else:
            wm, wk, bm, bk, res = s
            sw = float("nan")
        base[i] = _base_white(v2, wm, wk, bm, bk, mode)
        cells[i] = offs + np.asarray(pattern_indices(wm, bm), dtype=np.int32)
        result[i] = res
        scan[i] = sw
        i += 1
        # 180-deg rotate + colour swap; result and scan negate.
        rwm = _rot_bb(bm, remap)
        rbm = _rot_bb(wm, remap)
        rwk = _rot_bb(bk, remap)
        rbk = _rot_bb(wk, remap)
        base[i] = _base_white(v2, rwm, rwk, rbm, rbk, mode)
        cells[i] = offs + np.asarray(pattern_indices(rwm, rbm), dtype=np.int32)
        result[i] = 1.0 - res
        scan[i] = -sw
        i += 1
    return base, cells, result, scan


# ---------------------------------------------------------------------------
# v4: sparse COO features (phase-tapered patterns + king PST) + fixed base
#
# The v4 weight vector is one flat array laid out as (see
# .superpowers/sdd/v4-shared-constants.md):
#
#   cols 0 .. KBASE-1 : men patterns, col = (p*6561 + idx)*2 + (0=mg | 1=eg)
#                       with global pattern index p in 0..16 (11 horizontal
#                       then 6 tall, matching turbo.pattern_indices' order).
#   KBASE = 17*6561*2 : white-king PST, col = KBASE + sq*2 + (0=mg | 1=eg).
#
# Every emitted feature is phase-scaled: mg cols carry ``ph`` and eg cols
# carry ``1-ph`` (ph = min(men, 40)/40, kings excluded), so a fitted weight
# pair (wmg, weg) reproduces turbo's ``(mg*men + eg*(40-men))/40`` blend.
# A black king on square s mirrors the white table at square 49-s, negated
# (val = -ph / -(1-ph)), exactly as turbo's BK table mirrors WK.
# ---------------------------------------------------------------------------

def _rot_map_turbo():
    """Internal-bit 180-degree remap (square s -> 49-s) using the live
    turbo layout, so v4 augmentation doesn't depend on the ephemeral
    ``turbo_v2`` checkpoint being importable."""
    from draughts.engines.turbo import S2B
    return {S2B[s]: S2B[49 - s] for s in range(50)}


def _v3_king_sq_val(v3, sq):
    """v3's per-square hand king value (white perspective), reproducing the
    ``k = KING_VALUE + KING_CENTER_BONUS*(min(row,9-row)+min(f,9-f))//2``
    folded into v3's WK_T/BK_T tables (wk_pst[sq] == bk_pst[sq] there)."""
    row = sq // 5
    f = v3._file_of(sq)
    return v3.KING_VALUE + v3.KING_CENTER_BONUS * (
        min(row, 9 - row) + min(f, 9 - f)
    ) // 2


def _king_pst_sum_v3(v3, wk, bk):
    """v3's white-perspective hand king-PST contribution: sum of per-square
    king values for white kings minus black kings (matches the WK_T/BK_T
    terms inside ``v3._evaluate``)."""
    from draughts.engines.turbo import B2S
    s = 0
    b = wk
    while b:
        lsb = b & -b
        s += _v3_king_sq_val(v3, B2S[lsb.bit_length() - 1])
        b ^= lsb
    b = bk
    while b:
        lsb = b & -b
        s -= _v3_king_sq_val(v3, B2S[lsb.bit_length() - 1])
        b ^= lsb
    return s


def _base_white_v4(v3, wm, wk, bm, bk):
    """v4 fixed base eval (white perspective).

    Takes the frozen v3 hand+pattern eval, *removes* the hand king positional
    PST (both the flat KING_VALUE material and the center bonus folded into
    it), and adds back flat ``KING_VALUE * (n_wk - n_bk)`` material. The king
    positional value is then re-learned by the trainable king PST features;
    ``turbo._build_eval_tables(king_pst)`` scores white square s as
    ``pack(KING_VALUE + kmg[s], KING_VALUE + keg[s])``, so the learned weight
    is a delta over this flat KING_VALUE.
    """
    from draughts.engines.turbo import KING_VALUE
    full = v3._evaluate(wm, wk, bm, bk, True)
    kps = _king_pst_sum_v3(v3, wk, bk)
    n_wk = wk.bit_count()
    n_bk = bk.bit_count()
    return float(full - kps + KING_VALUE * (n_wk - n_bk))


def _base_scan_arrays(samples):
    """(base, scan) numpy arrays over the *raw* (un-augmented) samples, used
    to fit the Scan->engine-cp scale ``a`` before cleaning/feature building."""
    import numpy as np
    from tools.checkpoints import turbo_v3 as v3

    n = len(samples)
    base = np.empty(n, dtype=np.float64)
    scan = np.empty(n, dtype=np.float64)
    for i, smp in enumerate(samples):
        base[i] = _base_white_v4(v3, smp[0], smp[1], smp[2], smp[3])
        scan[i] = smp[4] if len(smp) >= 5 else float("nan")
    return base, scan


def build_features_coo(samples, a=1.0):
    """Sparse COO features for the v4 regression, with 180-degree mirrors.

    Returns ``(base, rows, cols, vals, target)`` where ``base`` and
    ``target`` are per-row (length ``2*len(samples)`` incl. mirrors) and
    ``rows/cols/vals`` are parallel COO arrays. The regression eval is
    ``E = base + bincount(rows, w[cols]*vals)`` and ``target = a * scan``
    (mirror rows negate the Scan label, as in ``build_features``).
    """
    import numpy as np
    from tools.checkpoints import turbo_v3 as v3
    from draughts.engines.turbo import (
        pattern_indices,
        N_PATTERNS_ALL,
        PAT_ENTRIES,
        B2S,
    )

    KBASE = N_PATTERNS_ALL * PAT_ENTRIES * 2
    remap = _rot_map_turbo()

    N = len(samples) * 2
    base = np.empty(N, dtype=np.float64)
    target = np.empty(N, dtype=np.float64)
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []

    def emit(r, wm, wk, bm, bk):
        men = bin(wm).count("1") + bin(bm).count("1")
        if men > 40:
            men = 40
        ph = men / 40.0
        eg = 1.0 - ph
        for p, idx in enumerate(pattern_indices(wm, bm)):
            c = (p * PAT_ENTRIES + idx) * 2
            rows.append(r); cols.append(c); vals.append(ph)
            rows.append(r); cols.append(c + 1); vals.append(eg)
        b = wk
        while b:
            lsb = b & -b
            s = B2S[lsb.bit_length() - 1]
            c = KBASE + s * 2
            rows.append(r); cols.append(c); vals.append(ph)
            rows.append(r); cols.append(c + 1); vals.append(eg)
            b ^= lsb
        b = bk
        while b:
            lsb = b & -b
            s = B2S[lsb.bit_length() - 1]
            c = KBASE + (49 - s) * 2
            rows.append(r); cols.append(c); vals.append(-ph)
            rows.append(r); cols.append(c + 1); vals.append(-eg)
            b ^= lsb

    i = 0
    for smp in samples:
        wm, wk, bm, bk = smp[0], smp[1], smp[2], smp[3]
        sw = smp[4] if len(smp) >= 5 else 0.0
        base[i] = _base_white_v4(v3, wm, wk, bm, bk)
        target[i] = a * sw
        emit(i, wm, wk, bm, bk)
        i += 1
        # 180-degree rotate + colour swap; Scan label negates.
        rwm = _rot_bb(bm, remap)
        rbm = _rot_bb(wm, remap)
        rwk = _rot_bb(bk, remap)
        rbk = _rot_bb(wk, remap)
        base[i] = _base_white_v4(v3, rwm, rwk, rbm, rbk)
        target[i] = a * (-sw)
        emit(i, rwm, rwk, rbm, rbk)
        i += 1

    return (
        base,
        np.asarray(rows, dtype=np.int64),
        np.asarray(cols, dtype=np.int64),
        np.asarray(vals, dtype=np.float64),
        target,
    )


# ---------------------------------------------------------------------------
# Texel fit (Adam gradient descent, full batch)
# ---------------------------------------------------------------------------

def _sigmoid(x):
    import numpy as np
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def fit_k(E, y, lo=0.001, hi=0.03, n=60):
    """1-D fit of K minimising MSE of sigmoid(K*E) vs y."""
    import numpy as np
    best_k, best_mse = lo, 1e9
    for k in np.linspace(lo, hi, n):
        mse = float(np.mean((_sigmoid(k * E) - y) ** 2))
        if mse < best_mse:
            best_mse, best_k = mse, k
    return best_k, best_mse


def _metrics(E, y, K):
    import numpy as np
    p = _sigmoid(K * E)
    mse = float(np.mean((p - y) ** 2))
    eps = 1e-12
    ll = float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    return mse, ll


def fit(base, cells, y, n_weights, lam, iters, lr, k0, val_frac=0.1, seed=0):
    """Train pattern weights (residual on fixed v2 base) via log-loss.

    K is held fixed at ``k0`` during weight training (co-training K is
    ill-conditioned), then refit 1-D on the trained eval at the end.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    N = len(y)
    P = cells.shape[1]
    idx = rng.permutation(N)
    n_val = int(N * val_frac)
    val, tr = idx[:n_val], idx[n_val:]

    w = np.zeros(n_weights, dtype=np.float64)
    K = float(k0)
    cells_tr = cells[tr]
    flat_tr = cells_tr.ravel()
    Ntr = len(tr)
    base_tr = base[tr].astype(np.float64)
    y_tr = y[tr].astype(np.float64)

    mw = np.zeros_like(w); vw = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8

    for t in range(1, iters + 1):
        E = base_tr + w[cells_tr].sum(axis=1)
        p = _sigmoid(K * E)
        # log-loss gradient wrt E: K*(p-y)/N   (clean, no vanishing p(1-p))
        gE = (K / Ntr) * (p - y_tr)
        gw = np.bincount(flat_tr, weights=np.repeat(gE, P), minlength=n_weights)
        gw += 2.0 * lam * w  # L2 on the mean log-loss

        mw = b1 * mw + (1 - b1) * gw
        vw = b2 * vw + (1 - b2) * gw * gw
        w -= lr * (mw / (1 - b1 ** t)) / (np.sqrt(vw / (1 - b2 ** t)) + eps)

        if t % 25 == 0 or t == iters:
            Et = base_tr + w[cells_tr].sum(axis=1)
            Ev = base[val] + w[cells[val]].sum(axis=1)
            tr_mse, tr_ll = _metrics(Et, y_tr, K)
            v_mse, v_ll = _metrics(Ev, y[val], K)
            print(f"  iter {t:4d}  tr_mse={tr_mse:.5f} val_mse={v_mse:.5f}  "
                  f"val_ll={v_ll:.5f}  |w|max={np.abs(w).max():.1f}  "
                  f"nz={int(np.count_nonzero(np.abs(w)>0.5))}", flush=True)

    # Refit K on trained eval (train split), then report on val.
    Etr = base_tr + w[cells_tr].sum(axis=1)
    K, _ = fit_k(Etr, y_tr)
    Ev = base[val] + w[cells[val]].sum(axis=1)
    v_mse, v_ll = _metrics(Ev, y[val], K)
    tr_mse, _ = _metrics(Etr, y_tr, K)
    return w, K, tr_mse, v_mse


def fit_regression(base, cells, target, n_weights, lam, iters, lr,
                   val_frac=0.1, seed=0):
    """Least-squares: teach (base + patterns) -> target eval (Scan, v2 units).

    Convex in w; Adam.  Returns (w, train_rmse, val_rmse, base_val_rmse)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    N = len(target)
    P = cells.shape[1]
    idx = rng.permutation(N)
    n_val = int(N * val_frac)
    val, tr = idx[:n_val], idx[n_val:]

    w = np.zeros(n_weights, dtype=np.float64)
    cells_tr = cells[tr]
    flat_tr = cells_tr.ravel()
    Ntr = len(tr)
    base_tr = base[tr].astype(np.float64)
    tgt_tr = target[tr].astype(np.float64)

    base_val_rmse = float(np.sqrt(np.mean((base[val] - target[val]) ** 2)))
    mw = np.zeros_like(w); vw = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8

    for t in range(1, iters + 1):
        resid = base_tr + w[cells_tr].sum(axis=1) - tgt_tr
        gw = np.bincount(flat_tr, weights=np.repeat((2.0 / Ntr) * resid, P),
                         minlength=n_weights)
        gw += 2.0 * lam * w
        mw = b1 * mw + (1 - b1) * gw
        vw = b2 * vw + (1 - b2) * gw * gw
        w -= lr * (mw / (1 - b1 ** t)) / (np.sqrt(vw / (1 - b2 ** t)) + eps)
        if t % 50 == 0 or t == iters:
            rv = base[val] + w[cells[val]].sum(axis=1) - target[val]
            print(f"  iter {t:4d}  train_rmse="
                  f"{np.sqrt(np.mean(resid**2)):.2f}  "
                  f"val_rmse={np.sqrt(np.mean(rv**2)):.2f}  "
                  f"(base {base_val_rmse:.2f})  |w|max={np.abs(w).max():.1f}  "
                  f"nz={int(np.count_nonzero(np.abs(w)>0.5))}", flush=True)

    rtr = base_tr + w[cells_tr].sum(axis=1) - tgt_tr
    rv = base[val] + w[cells[val]].sum(axis=1) - target[val]
    return (w, float(np.sqrt(np.mean(rtr ** 2))),
            float(np.sqrt(np.mean(rv ** 2))), base_val_rmse)


def fit_regression_coo(base, rows, cols, vals, target, n_weights, lam, iters,
                       lr, val_frac=0.1, seed=0):
    """Least-squares fit of sparse COO features toward ``target`` (Adam).

    ``E = base + bincount(rows, w[cols]*vals)`` per row; the gradient is
    ``gw = bincount(cols, (2/Ntr)*resid[rows]*vals) + 2*lam*w`` with the
    residuals of the held-out validation rows masked to zero so the split is
    leak-free while keeping the brief's single-bincount form. Returns
    ``(w, train_rmse, val_rmse, base_val_rmse)``.
    """
    import numpy as np
    base = np.asarray(base, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    rows = np.asarray(rows, dtype=np.int64)
    cols = np.asarray(cols, dtype=np.int64)
    vals = np.asarray(vals, dtype=np.float64)

    N = len(base)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(N)
    n_val = int(N * val_frac)
    is_val = np.zeros(N, dtype=bool)
    is_val[perm[:n_val]] = True
    tr_mask = ~is_val
    Ntr = int(tr_mask.sum())

    base_val_rmse = (
        float(np.sqrt(np.mean((base[is_val] - target[is_val]) ** 2)))
        if n_val else float("nan")
    )

    w = np.zeros(n_weights, dtype=np.float64)
    mw = np.zeros_like(w)
    vw = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8

    for t in range(1, iters + 1):
        E = base + np.bincount(rows, weights=w[cols] * vals, minlength=N)
        resid = E - target
        g_resid = resid.copy()
        g_resid[is_val] = 0.0  # leak-free: val rows contribute no gradient
        gw = np.bincount(
            cols, weights=(2.0 / Ntr) * g_resid[rows] * vals,
            minlength=n_weights,
        )
        gw += 2.0 * lam * w
        mw = b1 * mw + (1 - b1) * gw
        vw = b2 * vw + (1 - b2) * gw * gw
        w -= lr * (mw / (1 - b1 ** t)) / (np.sqrt(vw / (1 - b2 ** t)) + eps)

        if t % 50 == 0 or t == iters:
            tr_rmse = float(np.sqrt(np.mean(resid[tr_mask] ** 2)))
            v_rmse = (float(np.sqrt(np.mean(resid[is_val] ** 2)))
                      if n_val else float("nan"))
            print(f"  iter {t:4d}  train_rmse={tr_rmse:.2f}  "
                  f"val_rmse={v_rmse:.2f}  (base {base_val_rmse:.2f})  "
                  f"|w|max={np.abs(w).max():.1f}  "
                  f"nz={int(np.count_nonzero(np.abs(w) > 0.5))}", flush=True)

    E = base + np.bincount(rows, weights=w[cols] * vals, minlength=N)
    resid = E - target
    tr_rmse = float(np.sqrt(np.mean(resid[tr_mask] ** 2)))
    v_rmse = (float(np.sqrt(np.mean(resid[is_val] ** 2)))
              if n_val else float("nan"))
    return w, tr_rmse, v_rmse, base_val_rmse


def write_weights(path, w, n_pat, n_ent):
    import numpy as np
    wi = np.clip(np.round(w), -32000, 32000).astype("<i2")
    with open(path, "wb") as f:
        f.write(b"TPW1")
        f.write(struct.pack("<HH", n_pat, n_ent))
        f.write(wi.tobytes())
    print(f"wrote {path} ({os.path.getsize(path)} bytes, "
          f"nonzero={int(np.count_nonzero(wi))}/{len(wi)})")


def write_weights_tpw2(path, w):
    """Write the flat v4 weight vector as a TPW2 file, exactly as
    ``turbo._load_weights_file`` reads it: ``TPW2`` magic, ``<HHHH`` header
    (nH, nT, entries, n_king), then int16 men weights (mg/eg interleaved,
    ``(nH+nT)*6561*2`` of them) followed by int16 king weights (``50*2``,
    mg/eg interleaved). The men block is ``w[:KBASE]`` verbatim and the king
    block is ``w[KBASE:KBASE+100]`` verbatim -- the trainer layout and the
    file layout share one index formula, so no reshuffle is needed.
    """
    import numpy as np
    from draughts.engines.turbo import N_PATTERNS, N_PATTERNS_T, PAT_ENTRIES

    KBASE = (N_PATTERNS + N_PATTERNS_T) * PAT_ENTRIES * 2
    w = np.asarray(w, dtype=np.float64)
    men = np.clip(np.round(w[:KBASE]), -32000, 32000).astype("<i2")
    king = np.clip(np.round(w[KBASE:KBASE + 100]), -32000, 32000).astype("<i2")
    with open(path, "wb") as f:
        f.write(b"TPW2")
        f.write(struct.pack("<HHHH", N_PATTERNS, N_PATTERNS_T, PAT_ENTRIES, 50))
        f.write(men.tobytes())
        f.write(king.tobytes())
    print(f"wrote {path} ({os.path.getsize(path)} bytes, TPW2, "
          f"men_nz={int(np.count_nonzero(men))}/{len(men)}  "
          f"king_nz={int(np.count_nonzero(king))}/{len(king)})")


# ---------------------------------------------------------------------------

def _load_or_generate_samples(args):
    """Reuse pickled ``--samples-in`` if present, else self-play generate.
    Scan-labelled rollouts (7-tuples) when ``--label scan``, else v2 self-play
    5-tuples. Shared by ``--gen-only`` and the ``--v4`` training path."""
    if args.samples_in and os.path.exists(args.samples_in):
        print(f"loading samples from {args.samples_in}")
        with open(args.samples_in, "rb") as f:
            samples = pickle.load(f)
        print(f"  {len(samples)} samples")
        return samples
    if args.label == "scan":
        return generate_scan(
            args.games, args.workers, args.scan_exe, args.move_time,
            args.roll_plies, args.min_open, args.max_open, args.cap, args.seed,
        )
    return generate(
        args.games, args.workers, args.depth, args.max_plies,
        args.min_open, args.max_open, args.cap, args.seed,
    )


def _train_v4(args):
    """v4 training pipeline: generate -> fit Scan/engine scale a -> clean ->
    COO features -> least-squares fit -> TPW2 weights.

    Ordering note: ``a`` is fit on the RAW base/scan of ALL generated samples
    first, so ``clean_samples``' ``max_abs`` (default 600) filters in engine-cp
    units; only then are the surviving samples turned into COO features with
    the same ``a`` applied to the target (target = a * scan)."""
    import numpy as np
    from draughts.engines.turbo import N_PATTERNS_ALL, PAT_ENTRIES

    samples = _load_or_generate_samples(args)
    if args.samples_out:
        with open(args.samples_out, "wb") as f:
            pickle.dump(samples, f)
        print(f"saved {len(samples)} samples -> {args.samples_out}")

    # Fit Scan -> engine-cp scale on raw samples (before any hygiene).
    base_all, scan_all = _base_scan_arrays(samples)
    denom = float(np.sum(scan_all * scan_all))
    a = float(np.sum(base_all * scan_all) / denom) if denom else 1.0
    print(f"scan->engine-cp scale a={a:.4f}  "
          f"(base std={base_all.std():.1f}cp, "
          f"scan std={scan_all.std():.1f})")

    cleaned = clean_samples(samples, max_abs=600.0, a=a, seed=args.seed)
    print(f"clean_samples: {len(samples)} -> {len(cleaned)} samples")

    base, rows, cols, vals, target = build_features_coo(cleaned, a=a)
    KBASE = N_PATTERNS_ALL * PAT_ENTRIES * 2
    n_weights = KBASE + 100
    print(f"  COO features: N={len(base)} rows (incl. mirrors)  "
          f"nnz={len(rows)}  n_weights={n_weights}")

    w, tr_rmse, val_rmse, base_rmse = fit_regression_coo(
        base, rows, cols, vals, target, n_weights,
        args.lam, args.iters, args.lr,
    )
    gap = (100 * (base_rmse - val_rmse) / base_rmse) if base_rmse else 0.0
    print(f"trained: train_rmse={tr_rmse:.2f}  val_rmse={val_rmse:.2f}  "
          f"(base {base_rmse:.2f})  gap_closed={gap:.1f}%")
    write_weights_tpw2(args.out, w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=10000)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--max-plies", type=int, default=180)
    ap.add_argument("--min-open", type=int, default=4)
    ap.add_argument("--max-open", type=int, default=9)
    ap.add_argument("--cap", type=int, default=30, help="max samples/game")
    ap.add_argument("--lam", type=float, default=1e-3)
    ap.add_argument("--iters", type=int, default=400)
    ap.add_argument("--lr", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--mode", default="full", choices=["full", "matref"])
    ap.add_argument("--target", default="result",
                    choices=["result", "scan", "blend", "scanreg"],
                    help="training label source / objective")
    ap.add_argument("--label", default="result", choices=["result", "scan"],
                    help="data generator: v2 self-play vs Scan self-play")
    ap.add_argument("--scan-exe", default=os.path.join(
        REPO, "scan_engine", "scan_31", "scan.exe"))
    ap.add_argument("--move-time", type=float, default=0.15)
    ap.add_argument("--roll-plies", type=int, default=40)
    ap.add_argument("--feat-cache", default=None,
                    help="npz cache for computed features")
    ap.add_argument("--samples-in", default=None, help="reuse pickled samples")
    ap.add_argument("--samples-out", default=None)
    ap.add_argument(
        "--out",
        default=os.path.join(REPO, "draughts", "engines", "turbo_weights.bin"),
    )
    ap.add_argument("--v4", action="store_true",
                    help="v4 path: COO tapered patterns + king PST -> TPW2")
    ap.add_argument("--gen-only", action="store_true",
                    help="generate + save samples (--samples-out) then exit")
    args = ap.parse_args()

    import numpy as np

    if args.gen_only:
        samples = _load_or_generate_samples(args)
        if args.samples_out:
            with open(args.samples_out, "wb") as f:
                pickle.dump(samples, f)
            print(f"saved {len(samples)} samples -> {args.samples_out}")
        else:
            print(f"generated {len(samples)} samples "
                  "(no --samples-out; nothing written)")
        return

    if args.v4:
        _train_v4(args)
        return

    if args.feat_cache and os.path.exists(args.feat_cache):
        print(f"loading feature cache {args.feat_cache}")
        d = np.load(args.feat_cache)
        base, cells, result, scan = (
            d["base"], d["cells"], d["result"], d["scan"])
    else:
        if args.samples_in and os.path.exists(args.samples_in):
            print(f"loading samples from {args.samples_in}")
            with open(args.samples_in, "rb") as f:
                samples = pickle.load(f)
            print(f"  {len(samples)} samples")
        elif args.label == "scan":
            samples = generate_scan(
                args.games, args.workers, args.scan_exe, args.move_time,
                args.roll_plies, args.min_open, args.max_open, args.cap,
                args.seed,
            )
            if args.samples_out:
                with open(args.samples_out, "wb") as f:
                    pickle.dump(samples, f)
                print(f"saved samples -> {args.samples_out}")
        else:
            samples = generate(
                args.games, args.workers, args.depth, args.max_plies,
                args.min_open, args.max_open, args.cap, args.seed,
            )
            if args.samples_out:
                with open(args.samples_out, "wb") as f:
                    pickle.dump(samples, f)
                print(f"saved samples -> {args.samples_out}")
        print(f"building features (mode={args.mode}, +180-deg aug) ...")
        base, cells, result, scan = build_features(samples, args.mode)
        if args.feat_cache:
            np.savez(args.feat_cache, base=base, cells=cells,
                     result=result, scan=scan)
    print(f"  feature matrix: N={len(result)}  P={cells.shape[1]}")

    from draughts.engines.turbo import N_PATTERNS, PAT_ENTRIES
    n_weights = N_PATTERNS * PAT_ENTRIES

    have_scan = np.isfinite(scan).all()
    if args.target in ("scan", "blend", "scanreg") and not have_scan:
        print("WARNING: no scan labels present; falling back to result target")
        args.target = "result"

    if args.target == "scanreg":
        # Direct eval regression: align Scan units to v2 centipawns, then
        # teach (base + patterns) toward Scan's judgment.
        a = float(np.sum(base * scan) / np.sum(scan * scan))
        target = (a * scan).astype(np.float32)
        print(f"scan->v2 scale a={a:.2f}  "
              f"(target eval std={target.std():.1f}cp, "
              f"base std={base.std():.1f}cp)")
        w, tr_rmse, val_rmse, base_rmse = fit_regression(
            base, cells, target, n_weights, args.lam, args.iters, args.lr,
        )
        print(f"trained: train_rmse={tr_rmse:.2f}  val_rmse={val_rmse:.2f}  "
              f"(base {base_rmse:.2f})  gap_closed="
              f"{100*(base_rmse-val_rmse)/base_rmse:.1f}%")
        write_weights(args.out, w, N_PATTERNS, PAT_ENTRIES)
        return

    # Logistic (Texel) targets.
    if have_scan:
        c_scan, _ = fit_k(scan, result, lo=0.01, hi=4.0, n=120)
        y_scan = _sigmoid(c_scan * scan)
        print(f"scan->winprob scale c={c_scan:.4f}  "
              f"(scan white mean={scan.mean():.3f} std={scan.std():.3f})")
    if args.target == "result":
        y = result
    elif args.target == "scan":
        y = y_scan.astype(np.float32)
    else:  # blend
        y = (0.5 * result + 0.5 * y_scan).astype(np.float32)

    k0, base_mse = fit_k(base, y)
    print(f"base-only (patterns off): best K={k0:.5f}  MSE={base_mse:.5f}")
    w, K, tr_mse, val_mse = fit(
        base, cells, y, n_weights, args.lam, args.iters, args.lr, k0,
    )
    print(f"trained: train_mse={tr_mse:.5f}  val_mse={val_mse:.5f}  "
          f"(base val baseline ~{base_mse:.5f})  reduction="
          f"{100*(base_mse-val_mse)/base_mse:.1f}%")
    write_weights(args.out, w, N_PATTERNS, PAT_ENTRIES)


if __name__ == "__main__":
    main()
