# Changelog

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
