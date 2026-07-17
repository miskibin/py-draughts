"""Performance and correctness guards for the unified move-generation core.

The diagonal variants (standard 10x10, american, russian, brazilian 8x8) all
route their move generation through the shared ghost-layout bitboard core in
``draughts.boards._core``. This module pins that core down from two directions:

* **Correctness** -- ``perft`` node counts (the number of distinct move
  sequences to a fixed depth from the start position) are exact invariants of
  the rules. They are the standard regression anchor for a move generator: any
  bug in move/capture generation, the maximum-capture rule, or promotion shifts
  a count and fails here. Standard ``perft`` agrees with the independent
  international generator in ``draughts.engines.turbo`` (see
  ``test_turbo.test_perft``), so the two implementations cross-check.

* **Throughput** -- a single coarse wall-clock ceiling on a fixed perft
  workload. It exists only to catch a *catastrophic* regression (e.g. someone
  reintroducing per-square Python recursion in place of the whole-board bitboard
  ops), not to police small fluctuations. The ceiling carries ~15x headroom over
  the observed runtime on ordinary hardware so it stays green on shared, noisy
  CI machines.
"""

from __future__ import annotations

import time

import pytest

from draughts import AmericanBoard, BrazilianBoard, RussianBoard, StandardBoard
from draughts.boards.base import BaseBoard


def perft(board: BaseBoard, depth: int) -> int:
    """Count leaf nodes of the move tree to ``depth`` via push/pop."""
    if depth == 0:
        return 1
    total = 0
    for move in board.legal_moves:
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total


# Exact perft node counts from the start position of each variant. Standard is
# the canonical BikDam sequence (9, 81, 658, 4265, 27117, 167140); the 8x8 and
# american rows were computed from this core and double as regression anchors.
PERFT_ANCHORS: dict[type[BaseBoard], dict[int, int]] = {
    StandardBoard: {1: 9, 2: 81, 3: 658, 4: 4265, 5: 27117},
    AmericanBoard: {1: 7, 2: 49, 3: 379, 4: 2872, 5: 23582},
    RussianBoard: {1: 7, 2: 49, 3: 302, 4: 1469, 5: 7482, 6: 37986},
    BrazilianBoard: {1: 7, 2: 49, 3: 302, 4: 1469, 5: 7473, 6: 37628},
}

# (variant, depth) pairs for the throughput ceiling. Each runs in well under a
# second on ordinary hardware; the combined observed runtime is < ~1 s.
THROUGHPUT_WORKLOAD: list[tuple[type[BaseBoard], int]] = [
    (StandardBoard, 5),
    (AmericanBoard, 5),
    (RussianBoard, 6),
    (BrazilianBoard, 6),
]

# Generous absolute ceiling for the whole workload. Observed ~0.8 s here, so
# this is ~15x headroom -- large enough to absorb slow/noisy CI runners while
# still failing hard if the per-square recursion ever comes back.
THROUGHPUT_CEILING_SECONDS = 12.0


@pytest.mark.parametrize(
    "board_class,depth,expected",
    [
        (bc, d, n)
        for bc, anchors in PERFT_ANCHORS.items()
        for d, n in sorted(anchors.items())
    ],
    ids=lambda v: v.__module__.rsplit(".", 1)[-1] if isinstance(v, type) else str(v),
)
def test_perft_node_counts(board_class: type[BaseBoard], depth: int, expected: int) -> None:
    """Move generation produces exactly the known node count at each depth."""
    assert perft(board_class(), depth) == expected


def test_move_generation_throughput_ceiling() -> None:
    """A fixed multi-variant perft workload completes under a generous ceiling.

    Structural, not a micro-benchmark: the perft results are re-checked against
    the anchors (so this also guards correctness), and only a catastrophic
    slowdown -- an order of magnitude past the ~15x headroom -- can breach the
    time ceiling.
    """
    start = time.perf_counter()
    for board_class, depth in THROUGHPUT_WORKLOAD:
        nodes = perft(board_class(), depth)
        assert nodes == PERFT_ANCHORS[board_class][depth]
    elapsed = time.perf_counter() - start
    assert elapsed < THROUGHPUT_CEILING_SECONDS, (
        f"move-generation workload took {elapsed:.2f}s "
        f"(ceiling {THROUGHPUT_CEILING_SECONDS:.0f}s); "
        "a catastrophic move-generation regression is likely"
    )
