# Changelog

## Unreleased

## 1.10.0

Bug fixes:

- **FEN promotion-row validation** (#47): `Board.from_fen` now rejects a man
  placed on its own promotion row (e.g. `W:W4:B49` in international draughts —
  both 4 and 49 are promotion squares), since any move ending there crowns the
  piece and only a king can legally occupy it. Kings on the promotion row and
  men on the *opponent's* promotion row are unaffected.
- **Russian king capture continuation**: a capturing king could stop on any
  landing square behind its victim even when another landing square offered a
  further capture. Per the FMJD-64 rules (art. 4.6) the king must land where it
  can continue and capture until no continuation exists; the free choice of
  landing square applies only behind the last captured piece. In
  `B:W12,17,19,23,25,27,29:B1,3,4,7,8,10,11,K13,14` the early stops `13x22`,
  `13x26` and `13x31x20` are no longer generated — `13x31x24x15` is the king's
  only legal move, matching lidraughts/pydraughts. Other variants are
  unaffected (the maximum-capture rule already filtered such stops).

New:

- **Cross-variant FEN test suite**: `test/test_fen.py` checks all eight
  variants uniformly — promotion-row rejection, FEN round-trip fidelity from
  random play, and parser robustness against malformed input. The full
  position/move corpus was additionally cross-validated against the
  independent `pydraughts` package (2,900+ random-play positions across all
  variants with exact legal-move-set parity; American differs only by this
  library's documented optional-captures rule).

- **TurboEngine strength benchmarks + in-depth docs**: `tools/measure_turbo_elo.py`
  measures TurboEngine's strength — a self-play depth ladder, the flagship gap vs
  `SimpleEngine`, and the trained-vs-untrained pattern-eval ablation — reporting
  each as an Elo with a standard error. `tools/generate_turbo_charts.py` renders
  the documentation figures (learned-weight distribution and per-pattern activity,
  the training pipeline, a reproduced Texel training curve, and the measured-Elo
  charts). The engine docs gain a full "How it works / The trained pattern
  evaluation / How it was trained / Measured strength" walkthrough.
- **`TURBO_WEIGHTS` override**: point the environment variable at a custom `.bin`
  produced by `tools/train_pattern_eval.py` to load your own trained pattern
  weights, or set it to `none`/`off` to disable the trained term (v2 hand eval
  only). Unset uses the shipped `turbo_weights.bin`.

## 1.9.0

Breaking changes:

- **`AlphaBetaEngine` removed** (#42): renamed to `SimpleEngine` (identical API — alpha-beta with transposition table and iterative deepening, works on all variants).

New:

- **`TurboEngine`** (#42): new flagship engine for international draughts — Scan-style 63-bit board layout, PVS search with iterative deepening, transposition table, LMR and quiescence, plus a Scan-taught pattern evaluation (~+90 Elo at fixed depth, +176 Elo at 0.25s/move over the hand eval). International 10x10 only; `SimpleEngine` covers the other variants.
- **Cross-validation harness**: `tools/cross_validate_moves.py` and `test/test_cross_validation.py` validate standard-variant move generation against the Scan 3.1 engine; 7,492 positions across adversarial families (multi-capture tangles, windmills, coup-turc, near-promotion) matched Scan exactly. The test auto-skips when the Scan binary is absent.
- **Benchmark tooling** (#42): `tools/profile_turbo.py` (nodes/s profiler) and `tools/elo_benchmark.py` (head-to-head Elo with standard error).

Bug fixes:

- **Russian mid-capture promotion** (#43): a man promoting mid-capture could continue as a king flying over pieces it had already captured (e.g. `13x22x29x11x20` from `B:W15,16,K17,21,25:B9,13`). Captured pieces now block the promoted king for the rest of the sequence; the only legal move in that position is `13x22x29`.

## 1.8.4

Bug fixes:

- **FEN validation** (#33): `Board.from_fen` now rejects illegal FENs (stray characters in a piece list, squares outside `1..SQUARES_COUNT`, and duplicate squares) instead of silently building a corrupt board.
- **FEN square ranges** (#33): piece lists accept dash ranges, e.g. the international start position `W:W31-50:B1-20` (and `K`-prefixed ranges like `WK4-6`).
- **Windmill duplicate captures** (#34): a king capture that reaches the same square capturing the same pieces via different orders is now offered once instead of once per order (standard and Brazilian). Distinct routes capturing different pieces are unaffected.

## 1.8.3

Bug fixes:

- **FEN side-to-move token** (#26): `board.fen` no longer duplicates the side-to-move token. Output is now the canonical `[FEN "<turn>:W<white>:B<black>"]` instead of `W:W:...` / `W:B:...`.
- **One-sided FEN parsing** (#28): `Board.from_fen` now accepts valid positions where one side has no pieces (e.g. `B:W50:B`). Legacy FENs carrying the old duplicated token still parse.
- **`push()` validation** (#27): applying a `Move` whose source square is empty or holds an opponent piece now raises `ValueError` instead of silently corrupting the board with a phantom king.
- **Ambiguous captures** (#29): capture moves that share the same start and end square but follow different routes are now rendered with their full path (e.g. `4x27x38x15`), and `push_uci` requires the full path to disambiguate them instead of guessing.
