from __future__ import annotations

import random
from typing import Iterable

from draughts import StandardBoard, AmericanBoard, FrisianBoard, RussianBoard
from draughts.boards.base import BaseBoard


# Local variant lookup for test compatibility
BOARDS = {
    "standard": StandardBoard,
    "american": AmericanBoard,
    "frisian": FrisianBoard,
    "russian": RussianBoard,
}


def get_board(variant: str, fen: str | None = None) -> BaseBoard:
    """Create a board by variant name (test helper)."""
    board_cls = BOARDS[variant]
    if fen:
        return board_cls.from_fen(fen)
    return board_cls()


def seeded_range(n: int) -> Iterable[int]:
    """A readable helper for parametrizing many seeds."""
    return range(n)


def board_after_random_play(
    variant: str,
    *,
    seed: int,
    plies: int,
):
    """Return a board after `plies` random legal plies from the start.

    Deterministic given `seed`. Use this to exercise invariants across many positions.
    """
    board = get_board(variant)
    rng = random.Random(seed)

    for _ in range(plies):
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            break
        board.push(rng.choice(legal_moves))

    return board


def standard_board_after_random_play(*, seed: int, plies: int) -> StandardBoard:
    """Like board_after_random_play, but returns the concrete StandardBoard type."""
    board = StandardBoard()
    rng = random.Random(seed)

    for _ in range(plies):
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            break
        board.push(rng.choice(legal_moves))

    return board
