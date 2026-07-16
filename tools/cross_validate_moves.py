"""Cross-validate py-draughts standard (international) move generation against Scan.

Scan (by Fabien Letouzey) is the engine behind lidraughts analysis. This harness
drives a patched Scan binary that answers a custom ``list-moves`` hub command with
the full legal move set for a position, then diffs it against
``draughts.boards.standard.Board.legal_moves`` over thousands of diverse positions.

Move-notation ambiguity is handled by normalising every move on both sides to the
tuple ``(origin, destination, frozenset(captured_squares))``:
  * py-draughts ``Move`` -> ``(square_list[0]+1, square_list[-1]+1, {c+1 ...})``
  * Scan hub move ``from x to x cap x cap`` -> ``(from, to, {caps})``
Under FMJD rules two capture sequences with the same origin, destination and
captured set are the same move, so a set comparison of these keys is the exact
legal-move-set comparison.

Usage:
    python tools/cross_validate_moves.py --count 3000 --seed 1 \
        --families playout,random,capture_dense,many_kings,near_promo,windmill \
        --report /tmp/report.json [--scan /path/to/scan_oracle]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from draughts.boards.standard import Board  # noqa: E402
from draughts.models import Color  # noqa: E402
from draughts.move import Move  # noqa: E402

# Square constraints for the 10x10 board (standard 1..50 numbering).
NUM_SQUARES = 50
WHITE_MAN_SQUARES = list(range(6, 51))  # white men may not sit on promotion row 1-5
BLACK_MAN_SQUARES = list(range(1, 46))  # black men may not sit on promotion row 46-50
ALL_SQUARES = list(range(1, 51))

MoveKey = tuple[int, int, frozenset]


# --------------------------------------------------------------------------- #
# Oracle
# --------------------------------------------------------------------------- #
def find_scan_binary(explicit: Optional[str] = None) -> Optional[Path]:
    """Locate the patched Scan oracle binary (supports the ``list-moves`` command)."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("SCAN_ORACLE"):
        candidates.append(os.environ["SCAN_ORACLE"])
    # Common scratch/build locations.
    candidates += [
        "scan_oracle",
        "./scan_oracle",
        str(Path.home() / "scan" / "scan_oracle"),
    ]
    for c in candidates:
        p = Path(c)
        if p.exists() and os.access(p, os.X_OK):
            return p.resolve()
    return None


class ScanOracle:
    """Subprocess wrapper around the patched Scan binary (hub protocol).

    The binary must be launched from a directory containing ``scan.ini`` and a
    ``data/`` folder. ``list-moves`` needs neither the eval nor the opening book,
    so we skip the ``init`` handshake entirely for speed.
    """

    def __init__(self, binary: Path, variant: str = "normal"):
        self.binary = Path(binary)
        self.variant = variant
        self.proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "ScanOracle":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [str(self.binary), "hub"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=str(self.binary.parent),
        )
        if self.variant != "normal":
            self._send(f"set-param name=variant value={self.variant}")

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            self._send("quit")
            self.proc.wait(timeout=2.0)
        except Exception:
            self.proc.kill()
        finally:
            self.proc = None

    def _send(self, line: str) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def legal_moves(self, hub_pos: str) -> Optional[set[MoveKey]]:
        """Return the oracle's legal-move key set, or ``None`` if it rejects the position."""
        assert self.proc and self.proc.stdout
        self._send(f"pos pos={hub_pos}")
        self._send("list-moves")
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Scan oracle closed unexpectedly")
            line = line.strip()
            if line.startswith("movelist"):
                return _parse_scan_movelist(line)
            if line.startswith("error"):
                # Bad position (e.g. men on promotion row) -> caller should skip.
                return None


def _parse_scan_movelist(line: str) -> set[MoveKey]:
    keys: set[MoveKey] = set()
    tokens = line.split()[1:]  # drop leading "movelist"
    for tok in tokens:
        keys.add(_parse_scan_move(tok))
    return keys


def _parse_scan_move(tok: str) -> MoveKey:
    if "-" in tok:  # quiet move "from-to"
        a, b = tok.split("-")
        return (int(a), int(b), frozenset())
    parts = tok.split("x")  # "from x to x cap x cap ..."
    origin, dest = int(parts[0]), int(parts[1])
    caps = frozenset(int(p) for p in parts[2:])
    return (origin, dest, caps)


# --------------------------------------------------------------------------- #
# py-draughts side
# --------------------------------------------------------------------------- #
def py_move_key(move: Move) -> MoveKey:
    return (
        move.square_list[0] + 1,
        move.square_list[-1] + 1,
        frozenset(c + 1 for c in move.captured_list),
    )


def py_legal_map(board: Board) -> dict[MoveKey, Move]:
    """Map normalized key -> a representative py-draughts Move for the position."""
    out: dict[MoveKey, Move] = {}
    for m in board.legal_moves:
        out.setdefault(py_move_key(m), m)
    return out


# --------------------------------------------------------------------------- #
# Position construction
# --------------------------------------------------------------------------- #
@dataclass
class Position:
    label: str
    wm: set[int] = field(default_factory=set)
    wk: set[int] = field(default_factory=set)
    bm: set[int] = field(default_factory=set)
    bk: set[int] = field(default_factory=set)
    turn: Color = Color.WHITE

    def hub(self) -> str:
        side = "W" if self.turn == Color.WHITE else "B"
        chars = []
        for sq in range(1, 51):
            if sq in self.wm:
                chars.append("w")
            elif sq in self.wk:
                chars.append("W")
            elif sq in self.bm:
                chars.append("b")
            elif sq in self.bk:
                chars.append("B")
            else:
                chars.append("e")
        return side + "".join(chars)

    def board(self) -> Board:
        arr = np.zeros(NUM_SQUARES, dtype=np.int8)
        for sq in self.wm:
            arr[sq - 1] = -1
        for sq in self.wk:
            arr[sq - 1] = -2
        for sq in self.bm:
            arr[sq - 1] = 1
        for sq in self.bk:
            arr[sq - 1] = 2
        return Board(starting_position=arr, turn=self.turn)

    def fen(self) -> str:
        return self.board().fen

    def valid(self) -> bool:
        """Cheap structural validity: disjoint, both sides present, men off promo rows."""
        occ = self.wm | self.wk | self.bm | self.bk
        if len(occ) != len(self.wm) + len(self.wk) + len(self.bm) + len(self.bk):
            return False
        if not (self.wm | self.wk) or not (self.bm | self.bk):
            return False
        if any(sq < 6 for sq in self.wm):
            return False
        if any(sq > 45 for sq in self.bm):
            return False
        return True


def _random_position(rng: random.Random, label: str, *, n_min: int, n_max: int,
                     king_ratio: float, man_pool_w=WHITE_MAN_SQUARES,
                     man_pool_b=BLACK_MAN_SQUARES) -> Optional[Position]:
    """Generic random placement respecting man/promotion constraints."""
    total = rng.randint(n_min, n_max)
    n_white = rng.randint(1, total - 1)
    n_black = total - n_white
    used: set[int] = set()
    pos = Position(label=label, turn=rng.choice([Color.WHITE, Color.BLACK]))

    def place(n: int, king_pool, man_pool, king_set: set, man_set: set) -> bool:
        for _ in range(n):
            is_king = rng.random() < king_ratio
            pool = king_pool if is_king else man_pool
            choices = [s for s in pool if s not in used]
            if not choices:
                # fall back to a king anywhere if the man pool is exhausted
                choices = [s for s in king_pool if s not in used]
                is_king = True
                if not choices:
                    return False
            sq = rng.choice(choices)
            used.add(sq)
            (king_set if is_king else man_set).add(sq)
        return True

    if not place(n_white, ALL_SQUARES, man_pool_w, pos.wk, pos.wm):
        return None
    if not place(n_black, ALL_SQUARES, man_pool_b, pos.bk, pos.bm):
        return None
    return pos if pos.valid() else None


# --------------------------------------------------------------------------- #
# Family generators
# --------------------------------------------------------------------------- #
def gen_random(rng: random.Random, n: int) -> Iterable[Position]:
    made = 0
    guard = 0
    while made < n and guard < n * 50:
        guard += 1
        p = _random_position(rng, "random", n_min=2, n_max=24, king_ratio=0.25)
        if p:
            made += 1
            yield p


def gen_capture_dense(rng: random.Random, n: int) -> Iterable[Position]:
    """Dense central tangles to force long multi-capture chains."""
    center = [s for s in range(15, 37)]
    made = 0
    guard = 0
    while made < n and guard < n * 60:
        guard += 1
        p = _random_position(
            rng, "capture_dense", n_min=10, n_max=30, king_ratio=0.3,
            man_pool_w=[s for s in WHITE_MAN_SQUARES if s in center or rng.random() < 0.5],
            man_pool_b=[s for s in BLACK_MAN_SQUARES if s in center or rng.random() < 0.5],
        )
        if p:
            made += 1
            yield p


def gen_many_kings(rng: random.Random, n: int) -> Iterable[Position]:
    made = 0
    guard = 0
    while made < n and guard < n * 50:
        guard += 1
        p = _random_position(rng, "many_kings", n_min=2, n_max=14, king_ratio=0.9)
        if p:
            made += 1
            yield p


def gen_near_promo(rng: random.Random, n: int) -> Iterable[Position]:
    """Men near their promotion rows, with enemies positioned to enable captures
    that cross the promotion row (international: a man crossing mid-capture does NOT
    promote)."""
    made = 0
    guard = 0
    while made < n and guard < n * 80:
        guard += 1
        pos = Position(label="near_promo", turn=rng.choice([Color.WHITE, Color.BLACK]))
        used: set[int] = set()
        # White men near row 2-3 (squares 6-15), black men near row 8-9 (36-45),
        # plus a scattering of enemies in the middle to be jumped.
        for _ in range(rng.randint(1, 4)):
            choices = [s for s in range(6, 21) if s not in used]
            if choices:
                sq = rng.choice(choices)
                used.add(sq)
                pos.wm.add(sq)
        for _ in range(rng.randint(1, 4)):
            choices = [s for s in range(31, 46) if s not in used]
            if choices:
                sq = rng.choice(choices)
                used.add(sq)
                pos.bm.add(sq)
        # scattered enemies + a few kings in the middle
        for _ in range(rng.randint(2, 8)):
            choices = [s for s in range(11, 41) if s not in used]
            if not choices:
                break
            sq = rng.choice(choices)
            used.add(sq)
            r = rng.random()
            if r < 0.3:
                pos.wk.add(sq)
            elif r < 0.6:
                pos.bk.add(sq)
            elif r < 0.8 and sq in BLACK_MAN_SQUARES:
                pos.bm.add(sq)
            elif sq in WHITE_MAN_SQUARES:
                pos.wm.add(sq)
            else:
                pos.wk.add(sq)
        if pos.valid():
            made += 1
            yield pos


def gen_windmill(rng: random.Random, n: int) -> Iterable[Position]:
    """Flying-king windmill / coup-turc style rings: a lone king with a loop of
    enemy men so a capture would want to revisit an already-captured square."""
    # Hand-picked ring seeds (square sets of enemy men around a king square).
    seeds = [
        (2, {7, 8, 17, 18}),       # issue #34 windmill
        (3, {8, 9, 18, 19}),
        (28, {22, 23, 32, 33}),
        (27, {21, 22, 31, 32}),
        (28, {17, 18, 19, 22, 23, 24, 32, 33, 34, 37, 38, 39}),  # big ring
        (14, {9, 10, 19, 20, 23, 24}),
    ]
    made = 0
    guard = 0
    while made < n and guard < n * 40:
        guard += 1
        king_sq, ring = rng.choice(seeds)
        turn = Color.WHITE
        pos = Position(label="windmill", turn=turn)
        pos.wk.add(king_sq)
        # ring pieces are black; randomly drop a couple and/or add extra kings
        ring = set(ring)
        for r in list(ring):
            if rng.random() < 0.15:
                ring.discard(r)
        for r in ring:
            if r == king_sq:
                continue
            if rng.random() < 0.2 and r not in (king_sq,):
                pos.bk.add(r)
            elif r in BLACK_MAN_SQUARES:
                pos.bm.add(r)
            else:
                pos.bk.add(r)
        # optional extra friendly king elsewhere
        if rng.random() < 0.3:
            free = [s for s in range(40, 51)
                    if s not in (pos.wk | pos.wm | pos.bm | pos.bk)]
            if free:
                pos.wk.add(rng.choice(free))
        if pos.valid() and (pos.bm or pos.bk):
            made += 1
            yield pos


def gen_playout(rng: random.Random, oracle: ScanOracle, n: int,
                max_depth: int = 60) -> Iterable[Position]:
    """Random playouts from the start position. Every advancing move is drawn from
    the intersection of the oracle's and py-draughts' legal sets, so reachability
    can never be skewed by a py-draughts bug. Each visited position is yielded."""
    made = 0
    while made < n:
        board = Board()
        depth = rng.randint(1, max_depth)
        for _ in range(depth):
            pos = _position_from_board(board, "playout")
            if not pos.valid():
                break
            made += 1
            yield pos
            if made >= n:
                return
            okeys = oracle.legal_moves(pos.hub())
            if not okeys:
                break
            pmap = py_legal_map(board)
            agreed = [pmap[k] for k in okeys if k in pmap]
            if not agreed:
                break
            board.push(rng.choice(agreed))


def _position_from_board(board: Board, label: str) -> Position:
    pos = Position(label=label, turn=board.turn)
    for sq in range(1, 51):
        v = int(board.position[sq - 1])
        if v == -1:
            pos.wm.add(sq)
        elif v == -2:
            pos.wk.add(sq)
        elif v == 1:
            pos.bm.add(sq)
        elif v == 2:
            pos.bk.add(sq)
    return pos


# --------------------------------------------------------------------------- #
# Campaign
# --------------------------------------------------------------------------- #
@dataclass
class Mismatch:
    label: str
    fen: str
    hub: str
    py_only: list
    oracle_only: list
    py_moves: list
    oracle_moves: list


def _keys_to_strs(keys: Iterable[MoveKey]) -> list[str]:
    out = []
    for origin, dest, caps in keys:
        if caps:
            out.append(f"{origin}x{dest}x" + "x".join(str(c) for c in sorted(caps)))
        else:
            out.append(f"{origin}-{dest}")
    return sorted(out)


def run_campaign(count: int, seed: int, families: list[str], scan: Path,
                 report_path: Optional[str] = None, verbose: bool = True) -> dict:
    rng = random.Random(seed)
    mismatches: list[Mismatch] = []
    per_family: dict[str, int] = {}
    skipped = 0
    checked = 0

    # Allocate counts across families (playout gets a bigger share).
    weights = {
        "playout": 3.0, "random": 2.0, "capture_dense": 2.0,
        "many_kings": 1.0, "near_promo": 1.5, "windmill": 1.0,
    }
    active = [f for f in families]
    wsum = sum(weights.get(f, 1.0) for f in active)
    alloc = {f: max(1, int(count * weights.get(f, 1.0) / wsum)) for f in active}

    with ScanOracle(scan) as oracle:
        def check(pos: Position) -> None:
            nonlocal checked, skipped
            okeys = oracle.legal_moves(pos.hub())
            if okeys is None:
                skipped += 1
                return
            try:
                pmap = py_legal_map(pos.board())
            except Exception as e:  # noqa: BLE001
                skipped += 1
                if verbose:
                    print(f"  [skip] py-draughts raised on {pos.hub()}: {e}")
                return
            pkeys = set(pmap.keys())
            checked += 1
            per_family[pos.label] = per_family.get(pos.label, 0) + 1
            if pkeys != okeys:
                py_only = pkeys - okeys
                oracle_only = okeys - pkeys
                mismatches.append(Mismatch(
                    label=pos.label,
                    fen=pos.fen(),
                    hub=pos.hub(),
                    py_only=_keys_to_strs(py_only),
                    oracle_only=_keys_to_strs(oracle_only),
                    py_moves=_keys_to_strs(pkeys),
                    oracle_moves=_keys_to_strs(okeys),
                ))
                if verbose:
                    print(f"  [MISMATCH:{pos.label}] {pos.fen()}")
                    print(f"      py_only={_keys_to_strs(py_only)}")
                    print(f"      oracle_only={_keys_to_strs(oracle_only)}")

        gens = {
            "random": lambda k: gen_random(rng, k),
            "capture_dense": lambda k: gen_capture_dense(rng, k),
            "many_kings": lambda k: gen_many_kings(rng, k),
            "near_promo": lambda k: gen_near_promo(rng, k),
            "windmill": lambda k: gen_windmill(rng, k),
            "playout": lambda k: gen_playout(rng, oracle, k),
        }

        for fam in active:
            if fam not in gens:
                print(f"  [warn] unknown family {fam}, skipping")
                continue
            target = alloc[fam]
            if verbose:
                print(f"[family {fam}] target {target} positions")
            for pos in gens[fam](target):
                check(pos)

    summary = {
        "seed": seed,
        "requested": count,
        "checked": checked,
        "skipped": skipped,
        "per_family": per_family,
        "mismatch_count": len(mismatches),
        "mismatches": [vars(m) for m in mismatches],
    }
    if report_path:
        Path(report_path).write_text(json.dumps(summary, indent=2))
        if verbose:
            print(f"\nReport written to {report_path}")
    if verbose:
        print(f"\n=== Campaign summary ===")
        print(f"  checked={checked} skipped={skipped} mismatches={len(mismatches)}")
        print(f"  per_family={per_family}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument(
        "--families",
        default="playout,random,capture_dense,many_kings,near_promo,windmill",
    )
    ap.add_argument("--report", default=None)
    ap.add_argument("--scan", default=None, help="Path to patched Scan oracle binary")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    scan = find_scan_binary(args.scan)
    if scan is None:
        print("ERROR: Scan oracle binary not found. Set --scan or $SCAN_ORACLE.",
              file=sys.stderr)
        return 2

    families = [f.strip() for f in args.families.split(",") if f.strip()]
    summary = run_campaign(
        count=args.count, seed=args.seed, families=families,
        scan=scan, report_path=args.report, verbose=not args.quiet,
    )
    return 1 if summary["mismatch_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
