# Changelog

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
