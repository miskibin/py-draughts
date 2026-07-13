# TurboEngine v4 eval-tuning investigation (negative result)

**Date:** 2026-07-13
**Outcome:** No shippable improvement. A retrained/extended evaluation could not
beat the shipped v3 `TurboEngine` at any tested time control. v3 remains the
engine. This document records what was tried, the measurements, the root-cause
diagnosis, and the reusable tooling that came out of it, so a future attempt
starts informed instead of repeating the dead ends.

## Goal

Produce a stronger `TurboEngine` (v4) by improving only the *evaluation*
(training data + learned features), not the search, while keeping the
pure-Python leaf. Acceptance was a fair head-to-head benchmark vs a frozen v3
snapshot with a positive Elo beyond ~2× standard error, plus a leaf-speed gate.

## What was built (all reviewed, all green)

The engine/trainer changes were implemented and unit-tested even though they
did not yield a strength win:

- **Tapered mg/eg evaluation** — every learned weight packs a middlegame and
  endgame value into one int; the leaf accumulates a packed sum with the same
  number of lookups as v3 and blends by a men-count phase. Verified
  score-identical to v3 when loaded with v3's (non-tapered) weights.
- **Learned king PST** — the king lookup tables can be filled from trained
  values instead of the hand table.
- **Tall 2×4 patterns** — six additional vertical men patterns beside v3's
  eleven horizontal 4×2 patterns.
- **`TPW2` weights format** — carries per-pattern (mg, eg) plus king PST;
  loader keeps `TPW1` back-compat (reads as mg = eg, no king override), so a
  missing/old file behaves exactly as v3.
- **Upgraded offline trainer** — sparse COO features (phase + kings), Texel
  position hygiene (dedup, drop opening plies, drop |eval| > 600cp,
  phase-balance), 180° augmentation, a least-squares `scanreg` objective and a
  result-blend objective.

With the shipped v3 weights, the v4 code path plays **byte-identical** to v3
(regression tests assert this), so none of the above changes behaviour on its
own — the strength question is entirely about the trained weights.

## Results

All Elo figures are v4 minus frozen-v3, from `tools/benchmark_v4.py`
(opening book, colour-swapped, parallel), with ±2·SE where SE is the standard
error of the Elo estimate.

### Iteration 1 — many shallow rollout labels

Scan 3.1 self-play, 0.15 s/move, 40-ply rollouts, ~331k quiet positions.
λ sweep, screened at 150 games @ 0.1 s:

| λ    | Elo vs v3 | win% |
|------|-----------|------|
| 3e-3 | (worse)   | —    |
| 1e-3 | −30       | 45.7 |
| 3e-4 | +18       | 52.7 |
| 1e-4 | −2        | 49.7 |

Best (3e-4) at 0.3 s: −12. Net: **statistical parity with v3.** Lower training
RMSE did **not** predict game strength (1e-4 had the best held-out RMSE but
played even). Kings were starved in this data (few promotions in 40-ply
rollouts), so the learned king PST was under-trained.

### Iteration 2 — deeper, full-game labels

0.5 s/move, full games (kings + real win/loss labels), ~78k positions
(27.8% with a king, 48.9% decisive). Screened at 150 games @ 0.1 s:

| candidate       | Elo vs v3 |
|-----------------|-----------|
| scanreg 3e-4    | −275      |
| scanreg 1e-3    | −200      |
| blend β0.4      | −223      |
| blend β0.6      | −220      |

**Much worse.** Same code as iteration 1 — only the data changed.

### The root cause of the iteration-2 crash

| data           | scan std | scan \|max\| | base std | scale a |
|----------------|----------|--------------|----------|---------|
| iter1 rollouts | 1.40     | 7.2          | 122 cp   | 84.7    |
| iter2 full     | 24.74    | **100.0**    | **253 cp** | 7.0   |

Full games reach lopsided, near-terminal positions where Scan's eval saturates
to ±100 and material imbalance blows the base eval to 253 cp std. Tuning on
decided positions distorts the eval for the balanced middlegame positions that
actually decide games — the classic "remove positions with |score| > 600 cp and
drop decided games" rule from Texel-tuning practice. The `|eval| > 600cp`
hygiene did not save it because the Scan→cp scale collapsed to a = 7, leaving
the whole distribution dominated by large evals.

A merge experiment (iter1 balanced positions + only the balanced, king-bearing
iter2 positions) returned to parity (−2 Elo) but was confounded: adding sparse
low-men king buckets dropped the phase-balance median and over-capped the good
midgame data (346k → 57k after cleaning).

### Feature ablation (and a benchmark-noise lesson)

Ablating the iteration-1 3e-4 candidate by weight-file surgery, 200 games @ 0.1 s:

| variant             | Elo vs v3 |
|---------------------|-----------|
| full                | −14       |
| taper off           | −17       |
| **tall patterns off** | **+38** |
| learned king off    | −4        |
| king = v3 hand PST  | −7        |

The +38 for "tall off" looked like a finding — but re-running at **300 games**
it regressed to **−13** (and tall+king off to −37). At 150–200 games the ±45 Elo
noise is larger than the ~20 Elo effects being chased; the +38 was a noise spike.
**Lesson: use ≥300–500 games before believing a sub-40-Elo difference.**

### Why it tops out at v3 (noise-free measurement)

Rather than fight benchmark noise, we measured eval quality directly on 12,000
held-out balanced positions (ground truth: 0.5 s Scan eval + game result):

| eval     | Pearson vs deep-Scan | result-sign accuracy | result log-loss |
|----------|----------------------|----------------------|-----------------|
| v3       | 0.8503               | 0.9898               | 0.0317          |
| v4 (3e-4)| 0.8578               | 0.9910               | 0.0304          |

v4's eval **is** marginally more accurate — but only ~1% relative. That edge is
below the noise floor in games and is erased by v4's ~1.4% slower leaf.

### Last lever — slow time control

If the small eval edge mattered anywhere it would be at deep search. iter1-3e-4
vs v3 at **0.8 s/move, 400 games**: **−16.5 ± 31 Elo** (47.6% score). Deep search
does not rescue it.

## Conclusion

Across three data regimes, λ sweeps, feature ablations, a result-blend
objective, and time controls from 0.1 s to 0.8 s, the best result is
**statistical parity with v3**. The shipped v3 pattern eval is already near the
ceiling of what pattern-evaluation-trained-on-Scan-labels achieves; the extra
capacity (taper, tall patterns, learned kings) is neutral-to-slightly-negative,
and the ~1% eval-accuracy gain does not convert to Elo. This is a genuine
ceiling of the *approach*, not a fixable bug.

Leaf speed was never the blocker: the v4 eval profiled at 0.986× v3's nps
(1.4% slower), well inside the ≤20% gate.

## Recommendations for a future v5

- A materially stronger eval needs a different function class — e.g. an **NNUE**
  leaf. That breaks the pure-Python constraint (needs a C or optional-numpy
  fast path), so it is a deliberate architecture decision, not a tuning knob.
- Alternatively, invest in **search** (LMR/aspiration/move-ordering/TT tuning),
  which at these fast time controls has more headroom than the eval.
- If revisiting eval tuning: keep the **balanced rollout** distribution (never
  full games), fix the phase-balance median sensitivity in `clean_samples`, and
  budget for **≥500-game** benchmarks so real ~20-Elo effects clear the noise.

## Reusable tooling produced

- **`tools/profile_turbo.py`** — nodes/s profiler for any engine module over a
  fixed position set; used for the leaf-speed gate.
- **`tools/elo_benchmark.py`** — head-to-head benchmark that reports Elo with a
  proper standard error and confidence interval (the missing piece in the
  built-in `Benchmark`, which reports a point Elo only).

The full experiment (v4 engine code, `TPW2`, the upgraded trainer, the
`benchmark_v4.py`/ablation/eval-accuracy scripts) lives on the unmerged
`engine/turbo-v4` branch as the record.
