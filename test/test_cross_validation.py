"""Cross-validation of standard (international) move generation against Scan.

This suite drives the harness in ``tools/cross_validate_moves.py``, which diffs
``StandardBoard.legal_moves`` against the Scan engine (the oracle behind lidraughts
analysis) over many generated positions. The full module auto-skips when the
patched Scan oracle binary is unavailable (e.g. on CI), so it never breaks the
default ``pytest test/`` run.

To run it locally, build the oracle (see ``tools/cross_validate_moves.py``) and
either put ``scan_oracle`` on the search path or point ``$SCAN_ORACLE`` at it.
"""

from __future__ import annotations

import pytest

from draughts.boards.standard import Board
from draughts.models import Color
from tools.cross_validate_moves import (
    Position,
    ScanOracle,
    _position_from_board,
    find_scan_binary,
    py_legal_map,
    run_campaign,
)

SCAN = find_scan_binary()

pytestmark = pytest.mark.skipif(
    SCAN is None,
    reason="Scan oracle binary not found (set $SCAN_ORACLE); skipping cross-validation.",
)


@pytest.fixture(scope="module")
def oracle():
    with ScanOracle(SCAN) as o:
        yield o


def _diff(board: Board, oracle: ScanOracle):
    pos = _position_from_board(board, "case")
    okeys = oracle.legal_moves(pos.hub())
    pkeys = set(py_legal_map(board).keys())
    return okeys, pkeys


# --------------------------------------------------------------------------- #
# Hand-picked positions with tricky capture geometry.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "fen",
    [
        "W:W31-50:B1-20",  # start position
        "B:W31-50:B1-20",  # start, black to move
        "W:WK4:B13,32,37,20",  # two distinct max-capture routes (issue #29)
        "W:WK2:B7,8,17,18",  # flying-king windmill (issue #34)
        "W:B:WK2,28,31,44:B20,K50",  # king multi-capture
        "W:B:W6,24,28,38,41:B13,K49",  # king cannot recross captured square
        "W:WK47:B9,19,29,28,38",  # long flying-king chains
        "W:WK1,K50:BK5,K46,23,24",  # multiple kings both sides
    ],
)
def test_known_positions_match_oracle(fen, oracle):
    board = Board.from_fen(fen)
    okeys, pkeys = _diff(board, oracle)
    assert okeys is not None, f"oracle rejected position {fen}"
    assert pkeys == okeys, (
        f"legal-move mismatch for {fen}\n"
        f"  py_only={sorted(pkeys - okeys)}\n"
        f"  oracle_only={sorted(okeys - pkeys)}"
    )


# --------------------------------------------------------------------------- #
# A small deterministic campaign across every generator family. Kept modest so
# it stays fast; the standalone tool runs thousands.
# --------------------------------------------------------------------------- #
def test_generated_campaign_has_no_mismatches():
    summary = run_campaign(
        count=400,
        seed=12345,
        families=[
            "playout",
            "random",
            "capture_dense",
            "many_kings",
            "near_promo",
            "windmill",
        ],
        scan=SCAN,
        report_path=None,
        verbose=False,
    )
    assert summary["checked"] >= 200, f"too few positions checked: {summary}"
    assert summary["mismatch_count"] == 0, (
        f"{summary['mismatch_count']} mismatches; first few: {summary['mismatches'][:3]}"
    )
