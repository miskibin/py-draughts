from __future__ import annotations

import random
from typing import Iterable

from draughts import (
    AmericanBoard,
    AntidraughtsBoard,
    BrazilianBoard,
    BreakthroughBoard,
    FrisianBoard,
    FryskBoard,
    RussianBoard,
    StandardBoard,
)
from draughts.boards.base import BaseBoard

# Local variant lookup for test compatibility
BOARDS = {
    "standard": StandardBoard,
    "american": AmericanBoard,
    "frisian": FrisianBoard,
    "russian": RussianBoard,
    "brazilian": BrazilianBoard,
    "antidraughts": AntidraughtsBoard,
    "breakthrough": BreakthroughBoard,
    "frysk": FryskBoard,
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


def flown_over_squares(start: int, end: int) -> list[int]:
    """Squares strictly between two capture waypoints along the diagonal flight.

    Uses the shared 8x8 Russian/Brazilian king-ray geometry (both variants share
    the same square numbering). Returns 0-indexed squares from the one adjacent to
    ``start`` up to (but excluding) ``end`` -- i.e. every square the piece passes
    over on that jump. For a man's single jump this is just the captured pivot.

    Returns an empty list if ``end`` is not reachable from ``start`` on a diagonal
    (which should never happen for a well-formed capture segment).
    """
    from draughts.boards.russian import KING_RAYS

    for ray in KING_RAYS[start]:
        if end in ray:
            return list(ray[: ray.index(end)])
    return []


def assert_no_captured_square_recrossed(move) -> None:
    """Assert a capture never lands on, nor flies over, an already-captured square.

    ``move.captured_list[i]`` is the piece jumped on segment ``i`` (between
    ``square_list[i]`` and ``square_list[i + 1]``); it legitimately sits on that
    segment's flight path. Every *other* square flown over, and every landing
    square, must be free of captured pieces -- otherwise the piece has passed over
    or landed on a square still occupied by a previously-captured piece (issue #43).
    """
    captured = set(move.captured_list)
    for i in range(len(move.square_list) - 1):
        start, end = move.square_list[i], move.square_list[i + 1]
        assert end not in captured, (
            f"{move} lands on already-captured square {end + 1}"
        )
        pivot = move.captured_list[i] if i < len(move.captured_list) else None
        for sq in flown_over_squares(start, end):
            if sq == pivot:
                continue
            assert sq not in captured, (
                f"{move} flies over already-captured square {sq + 1}"
            )


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
