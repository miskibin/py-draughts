# Changelog

## 1.8.3

Bug fixes:

- **FEN side-to-move token** (#26): `board.fen` no longer duplicates the side-to-move token. Output is now the canonical `[FEN "<turn>:W<white>:B<black>"]` instead of `W:W:...` / `W:B:...`.
- **One-sided FEN parsing** (#28): `Board.from_fen` now accepts valid positions where one side has no pieces (e.g. `B:W50:B`). Legacy FENs carrying the old duplicated token still parse.
- **`push()` validation** (#27): applying a `Move` whose source square is empty or holds an opponent piece now raises `ValueError` instead of silently corrupting the board with a phantom king.
- **Ambiguous captures** (#29): capture moves that share the same start and end square but follow different routes are now rendered with their full path (e.g. `4x27x38x15`), and `push_uci` requires the full path to disambiguate them instead of guessing.
