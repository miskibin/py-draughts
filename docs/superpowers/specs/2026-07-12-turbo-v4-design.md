# TurboEngine v4 — design

Date: 2026-07-12
Status: approved (user, this session)
Scope: approach B — deeper training data + richer eval features. Search untouched.
Constraint: pure-Python leaf; weights file stays well under 1 MB.

## Goal

Beat the shipped v3 TurboEngine in a fair head-to-head benchmark at equal
time per move, by improving the *evaluation* (training data + learned
features), not the search.

## 1. Eval architecture (`draughts/engines/turbo.py`)

Three additions, each chosen for near-zero leaf cost:

1. **Tapered mg/eg evaluation via packed scores.** Every learned weight
   stores middlegame and endgame values packed into a single int
   (`(mg + K) << SHIFT | (eg + K)`), so the leaf accumulates a packed sum
   with the same number of lookups as v3, unpacks once per eval, and blends
   linearly by phase. Phase = total men on board (40 → 0), computed from
   bit counts. Extra leaf cost ≈ one unpack + one blend per eval.
2. **Learned king PST.** The existing `WK_T` / `BK_T` chunked lookup tables
   are already read every eval; v4 fills them from trained values (per
   phase) instead of hand values. Zero extra leaf cost. v3 learned nothing
   about kings.
3. **Tall patterns.** Keep the 11 horizontal 4×2 men blocks; add 2×4 tall
   blocks (2 dark squares per row × 4 rows = 8 trits, 3^8 = 6561 entries),
   which capture file/column structure — the analogue of Scan's column
   view. A tall block spans ~26 internal bits, so its index is extracted in
   two chunked lookups (2× the cost of a horizontal pattern). Start with
   +5 tall patterns; the final count is decided by the profiling gate.

Search code is not modified, so the benchmark is a clean A/B of the eval.

## 2. Training data

- Generator: Scan 3.1 self-play rollouts from randomized openings
  (as v3), move time raised 0.05 s → **0.15 s**.
- ~10 000 games across ≤ 8 workers (≈ 1.5–2 h wall clock).
- Position hygiene (Texel best practice):
  - quiet positions only (no capture pending either side) — as v3;
  - **dedup** by (wm, wk, bm, bk);
  - drop positions with **|Scan score| > 600 cp** (decided);
  - drop the first plies right after the random opening;
  - **phase-balance**: bucket by total men, cap per bucket.
- Keep 180° colour-swap augmentation. Target ≈ 600–800 k rows post-aug.

## 3. Trainer (`tools/train_pattern_eval.py`)

- Feature representation moves from fixed-width `cells[N,P]` to sparse COO
  `(row, weight_index, value)`: king count varies per position, and each
  feature occurrence now emits two entries — mg column × phase and eg
  column × (1 − phase).
- Objective unchanged from v3's best (`scanreg`): least-squares regression
  of (fixed v2 hand base + learned terms) toward Scan's score, Adam + L2.
  Pattern weights and king PST trained jointly. Scale factor `a` aligning
  Scan units to engine centipawns refit on the new data.
- Resource guardrails: workers ≤ 8, chunked feature building, `.npz` cache
  on D:, expected peak RAM < 6 GB (15 GB free at design time), RAM
  monitored during the run.

## 4. Weights format

- New magic `TPW2`: header + men-pattern weights (mg, eg int16) + king PST
  (mg, eg int16). ~0.5 MB total at 16 patterns.
- Loader accepts `TPW1` (v3) by reading flat weights as mg = eg, and keeps
  the all-zeros fallback when the file is missing — same contract as v3.

## 5. Verification gates (must pass before weights ship)

1. **Profiling:** fixed position set at fixed depth; nodes/s regression of
   v4 leaf vs v3 must be **≤ 20 %**, else tall patterns are trimmed.
   cProfile hotspot snapshot recorded.
2. **Benchmark:** frozen v3 snapshot vs v4 via `draughts.Benchmark`:
   ≥ 200 games at 0.1 s/move and ≥ 100 games at 0.3 s/move, opening book +
   colour swap, workers ≈ 6. Ship only on **positive Elo ≥ ~2× standard
   error**.
3. Test suite green; perft unchanged; new tests for TPW2 loading and
   tapered-eval sanity.

## 6. Risks / fallbacks

- Tall patterns too slow in pure Python → profiling gate trims them; worst
  case v4 = taper + learned king PST + better data (still a real upgrade).
- Deeper labels shift Scan score scale → `scanreg` refits `a` (as v3).
- v4 could lose to v3 → benchmark gate blocks shipping; `turbo_weights.bin`
  replaced only on pass.

## Out of scope

- NNUE / neural eval (kills pure-Python leaf speed).
- 12–16-trit Scan-size patterns (30 MB weights, package bloat).
- Search changes (LMR/aspiration tuning) — separate experiment later.
