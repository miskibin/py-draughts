# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies are managed with **uv** (`uv.lock` is checked in). Sync the env with dev extras:

```bash
uv sync --extra dev
```

Run tests / a single test file / a single test method:

```bash
uv run pytest test/ -v
uv run pytest test/test_standard_board.py -v
uv run pytest test/test_engine.py::TestAlphaBetaEngine::test_engine_returns_valid_move -v
```

Type check (matches CI exactly):

```bash
uv run mypy draughts --ignore-missing-imports
```

Docs build (Sphinx):

```bash
uv run sphinx-build docs/source/ _build
```

CI installs via `pip install -e ".[dev]"` and runs `pytest test/ -v` + the mypy command on Python 3.12 (see `.github/workflows/python-app.yml`). Supported Python versions are 3.9–3.14.

To add a runtime / dev dependency:

```bash
uv add <pkg>
uv add --optional dev <pkg>
```

## Architecture

### Bitboard core (`draughts/boards/`)

All variants derive from `BaseBoard` in `boards/base.py`, which stores position as **four integers** — `white_men`, `white_kings`, `black_men`, `black_kings` — plus `turn` and `halfmove_clock`. This is the hot path: make/unmake, legal move generation, and hashing are bit-twiddling on these ints. `Move` objects record `square_list` (visited) and `captured_list` (captured piece squares) with 0-indexed squares; display/UCI uses 1-indexed.

Variant subclasses (`standard.py`, `american.py`, `frisian.py`, `russian.py`) override `_init_default_position`, `legal_moves`, `is_draw`, and set class-level constants (`SQUARES_COUNT`, `PROMO_WHITE`, `PROMO_BLACK`, `SQUARE_NAMES`, `GAME_TYPE`, `VARIANT_NAME`). Each variant precomputes move/jump/ray tables at module import via a `_build_tables()` helper — do not recompute per-instance.

`Board` (the top-level convenience alias) is `StandardBoard`. `BaseBoard.copy()` is the fast clone path used by search (fresh move stack; shallow copy of bitboards); `__deepcopy__` also copies the move stack.

### Move stack and push/pop

`push(move, is_finished=True)` / `pop(is_finished=True)` are symmetric. The `is_finished=False` form is used internally during multi-step capture generation — do not flip the turn between sub-steps. Captured pieces store their original type in `move.captured_entities` so `pop` can restore them. `halfmove_clock` is snapshotted on the move and restored on pop.

### Notation

- FEN read/write on `BaseBoard`: `from_fen(...)` / `fen`. Kings are prefixed `K` (e.g. `W:WK10,K20:BK35,K45`).
- PDN read/write: `from_pdn(...)` / `pdn`. Accepts both numeric (`32-28`) and algebraic (`c3-d4`) notation; algebraic uses per-variant `SQUARE_NAMES`. Multi-capture chains that are split across tokens in the PDN are re-joined during parse.

### Engines (`draughts/engines/`)

- `Engine` (ABC) — `get_best_move(board, with_evaluation=False)`.
- `AlphaBetaEngine` — negamax + alpha-beta with iterative deepening, Zobrist transposition table (`TT_MAX_SIZE = 500_000`), quiescence, PVS/LMR, killer/history heuristics. Works with any variant. Piece-square tables are generated dynamically from `SQUARES_COUNT`/rows.
- `HubEngine` — subprocess wrapper for external engines speaking the Hub protocol (Scan, Kingsrow). `VARIANT_MAP` translates `BaseBoard.VARIANT_NAME` to Hub variant names; **American (8×8) is not supported by Scan**. Use as a context manager so the subprocess is torn down.
- `Agent` (Protocol) / `BaseAgent` (ABC) / `AgentEngine` — for custom AI. Implement `select_move(board) -> Move`; wrap with `BaseAgent.as_engine()` or `AgentEngine(agent)` to use with `Benchmark` and `Server`.

### ML/RL surface on `BaseBoard`

These methods exist specifically for neural-net agents and tree search — they do not affect normal play performance:

- `to_tensor(perspective=None)` → `(4, SQUARES_COUNT)` float32 (own men, own kings, opp men, opp kings).
- `legal_moves_mask()` → bool array of shape `(SQUARES_COUNT**2,)`. Move index is `from * SQUARES_COUNT + to` (only start/end squares, so multi-capture paths collide on the same index).
- `move_to_index(move)` / `index_to_move(idx)` round-trip via that encoding.
- `features()` → `BoardFeatures` dataclass (material, mobility, phase).
- `copy()` is the fast clone for MCTS/search.

### Benchmarking (`draughts/benchmark.py`)

`Benchmark(e1, e2, games=N).run()` plays engine vs. engine with paired openings from `STANDARD_OPENINGS` (10×10 only) and computes Elo difference, nodes/sec, etc. Uses `ProcessPoolExecutor`, so engines and agents must be picklable.

### Server (`draughts/server/`)

FastAPI + Jinja2 web UI. `Server(board, white_engine=..., black_engine=...).run()` serves on port 8000. Any `Engine` subclass works; `HubEngine` subprocesses are started/stopped by the server lifecycle.

## Repo conventions

- `loguru` is used throughout. The package removes the default stderr handler (id=0) in `draughts/__init__.py` — callers opt in with `logger.add(sys.stderr)`. Don't re-add it at import time.
- Logging is intentionally chatty at `info`/`debug` (e.g. `Board initialized...`). Don't "fix" this.
- `mypy.ini` disables specific error codes for `boards.standard`, `boards.frisian`, `boards.american` because class variables are `...` placeholders overridden in subclasses — don't try to "type" them away.
- Test games live under `test/games/<variant>/` (JSON legal-move counts, PDN replays, random FENs). Add new variant-wide regression cases there rather than inline.
- 0-indexed vs. 1-indexed: bitboard code is 0-indexed; UCI, FEN, PDN, and `__str__` are 1-indexed. `Move.square_list` is 0-indexed, `str(move)` prints 1-indexed.
- `__version__` in `draughts/__init__.py` and `version` in `pyproject.toml` are currently out of sync (`1.5.8` vs `1.6.4`) — bump both when cutting a release.
