"""
Tactical test suite for the alpha-beta engine.

Each entry is ``(variant, fen, expected_move, depth, description)``. The
expected move was cross-validated at depth ≥ 6 across the supported variants.
The suite is used as a regression net: every search-strength change must
keep these tests green before being considered safe to merge.

Run a subset locally with::

    pytest test/test_tactical.py -k <substring>

Add new puzzles freely — the only requirement is that the expected move is
stable at the given search depth (verify by running the engine at depths
``d`` and ``d+2`` and confirming they agree).
"""
from __future__ import annotations

import pytest

from draughts import (
    AlphaBetaEngine,
    AmericanBoard,
    FrisianBoard,
    RussianBoard,
    StandardBoard,
)


_BOARDS = {
    "standard": StandardBoard,
    "american": AmericanBoard,
    "russian": RussianBoard,
    "frisian": FrisianBoard,
}


# ---------------------------------------------------------------------------
# Tactical positions
#   variant, fen, expected_move (UCI string), depth, description
# ---------------------------------------------------------------------------

TACTICS: list[tuple[str, str, str, int, str]] = [
    # ---- forced single legal capture / chain ----
    ("standard", "W:W31,32:B27,28", "31x33", 4, "Standard forced double capture"),
    ("standard", "W:W32:B19,28",    "32x14", 4, "Standard forced multi-capture"),
    ("standard", "W:W30,31,32:B26,27", "31x22", 4, "Standard pick best capture"),
    ("american", "W:W14:B10",       "14x7",  4, "American forced jump"),
    ("russian",  "W:W23,32:B19,20", "23x16", 4, "Russian forced capture"),

    # ---- only one legal move ----
    ("standard", "W:W6:B45",        "6-1",   2, "Standard man at promotion (only move)"),

    # ---- material-winning tactics, depth ≥ 4 ----
    ("standard", "W:W31,33:B19",        "33-29", 4, "Standard material-winning plan"),
    ("standard", "W:WK20,K30:B5",       "20-15", 4, "Standard 2K vs 1m easy win"),
    ("standard", "W:W33,40:B17,28",     "33x11", 4, "Standard winning multi-capture"),
    ("standard", "B:W22,28:B17,18,19",  "18x27", 4, "Standard black winning capture"),

    # ---- variant-specific tactics ----
    ("frisian",  "W:W31,32:B27,28", "31x33", 4, "Frisian double capture"),
    ("frisian",  "W:W23:B33",       "23x43", 4, "Frisian vertical king capture"),
    ("american", "B:W14,18:B11",    "11-16", 4, "American positional retreat"),
    ("russian",  "W:W23,24:B18,20", "23x14", 4, "Russian winning combination"),
]


@pytest.mark.parametrize("variant,fen,expected,depth,desc", TACTICS)
def test_tactical_position(variant: str, fen: str, expected: str, depth: int, desc: str) -> None:
    """Engine at the given depth must find the locked-in best move."""
    Cls = _BOARDS[variant]
    board = Cls.from_fen(fen)
    eng = AlphaBetaEngine(depth_limit=depth)
    move, score = eng.get_best_move(board, with_evaluation=True)
    assert str(move) == expected, (
        f"[{desc}] depth={depth} variant={variant} fen={fen}\n"
        f"  expected: {expected}\n"
        f"  got     : {move} (score={score:.2f})"
    )


@pytest.mark.parametrize("variant,fen,expected,depth,desc", TACTICS)
def test_tactical_position_holds_at_higher_depth(
    variant: str, fen: str, expected: str, depth: int, desc: str
) -> None:
    """Same expectation must hold at depth+2 (no late regressions)."""
    Cls = _BOARDS[variant]
    board = Cls.from_fen(fen)
    eng = AlphaBetaEngine(depth_limit=depth + 2)
    move = eng.get_best_move(board)
    assert str(move) == expected, (
        f"[{desc}] depth={depth + 2} variant={variant} fen={fen}\n"
        f"  expected: {expected}, got: {move}"
    )
