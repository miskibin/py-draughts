"""
TurboEngine - fast alpha-beta engine for International (10x10) draughts.

Design follows the architecture of top engines (Scan, Kingsrow) adapted to
pure Python:

- Scan's 63-bit "ghost squares" board layout: all four diagonal directions
  become constant shifts of 6 and 7, so move generation is whole-board
  integer operations with no per-square tables in the hot path.
- Copy-make search on plain ints (no board object, no move stack, no numpy).
- PVS + iterative deepening + aspiration windows + transposition table
  + LMR + single-reply extension + Scan-style EMA history move ordering.
- Quiescence resolves all forced capture chains before evaluating, with a
  one-ply threat extension at the horizon (anti-horizon-effect, as in Scan).
- Integer evaluation computed straight from the bitboards via chunked
  lookup tables (9 x 7-bit chunks per bitboard).
- Trained pattern evaluation (v3): eleven overlapping 4x2 blocks of men
  squares indexed in base 3 (empty/white/black), weights learned by
  regressing the hand eval + patterns toward the Scan 3.1 engine's search
  score on ~294k quiet self-play positions (see tools/train_pattern_eval.py).
  Weights load from ``turbo_weights.bin``; if the file is missing the
  pattern term is zero and the eval falls back to the v2 hand eval.

The engine only supports the standard international board
(``SQUARES_COUNT == 50``); it converts the public board to its internal
layout at the root and maps the chosen move back onto ``board.legal_moves``.
"""

from __future__ import annotations

import math
import os
import struct
import time
from typing import Optional

from draughts.boards._core import CORE_STANDARD
from draughts.boards._draw import advance_clock
from draughts.boards.base import BaseBoard
from draughts.boards.standard import Board as StandardBoard
from draughts.engines.engine import Engine
from draughts.models import Color
from draughts.move import Move

# ---------------------------------------------------------------------------
# 63-bit ghost layout (Scan's board representation)
#
# Squares 1..50 are packed into bits 0..62 with 13 unused "ghost" bits so
# that the four diagonal steps are uniform shifts:
#   +6 = down-left, +7 = down-right, -6 = up-right, -7 = up-left
# (down = toward white's home rank; white men move with -6/-7).
# Row r (r = sq // 5, row 0 = black's back rank) starts at internal bit
# r*5 + (r+1)//2 + r//2*2 ... built programmatically below and verified by
# perft in tests.
# ---------------------------------------------------------------------------


def _build_layout() -> tuple[tuple[int, ...], dict[int, int], int]:
    sq_to_bit: list[int] = []
    bit = 0
    for row in range(10):
        for _ in range(5):
            sq_to_bit.append(bit)
            bit += 1
        bit += 1 if row % 2 == 0 else 2
    bit_to_sq = {b: s for s, b in enumerate(sq_to_bit)}
    mask = 0
    for b in sq_to_bit:
        mask |= 1 << b
    return tuple(sq_to_bit), bit_to_sq, mask


S2B, B2S, SQ_MASK = _build_layout()
BIT = tuple(1 << b for b in S2B)  # square index -> internal single-bit int

PROMO_W = sum(BIT[s] for s in range(0, 5))  # row 0, white promotes here
PROMO_B = sum(BIT[s] for s in range(45, 50))  # row 9, black promotes here

INF = 1 << 20
MATE = 1 << 16
DRAW = 0

# ---------------------------------------------------------------------------
# Evaluation weights (module level - easy to tune between checkpoints)
# ---------------------------------------------------------------------------

MAN_VALUE = 100
KING_VALUE = 320
# Advancement bonus for men, indexed by rows advanced from home rank (0..8).
ADV_BONUS = (0, 2, 4, 8, 12, 18, 26, 38, 52)
# Bonus for men still guarding the back rank (slows premature back-rank moves).
BACK_RANK_BONUS = 6
# Small preference for central files.
CENTER_FILE_BONUS = (0, 1, 2, 3, 4, 4, 3, 2, 1, 0)
KING_CENTER_BONUS = 4
MOBILITY_WEIGHT = 2
SKEW_WEIGHT = 3


def _file_of(sq: int) -> int:
    row, col = divmod(sq, 5)
    return 2 * col + 1 if row % 2 == 0 else 2 * col


def _build_eval_tables():
    """Per-square scores folded (material + PST), then chunked into
    9 lookup tables of 128 entries per bitboard type for O(9) evaluation."""
    wm_pst = [0] * 50
    bm_pst = [0] * 50
    wk_pst = [0] * 50
    bk_pst = [0] * 50
    for sq in range(50):
        row = sq // 5
        f = _file_of(sq)
        center = CENTER_FILE_BONUS[f]
        # White man: home row 9, promotes at row 0.
        adv_w = 9 - row - 1  # rows advanced from home (home row -> 0)
        wm_pst[sq] = MAN_VALUE + ADV_BONUS[max(0, min(8, adv_w))] + center
        if row == 9:
            wm_pst[sq] += BACK_RANK_BONUS
        # Black man mirrors.
        adv_b = row - 1
        bm_pst[sq] = MAN_VALUE + ADV_BONUS[max(0, min(8, adv_b))] + center
        if row == 0:
            bm_pst[sq] += BACK_RANK_BONUS
        k = KING_VALUE + KING_CENTER_BONUS * (min(row, 9 - row) + min(f, 9 - f)) // 2
        wk_pst[sq] = k
        bk_pst[sq] = k

    def chunk(pst: list[int]) -> tuple[tuple[int, ...], ...]:
        tables = []
        for c in range(9):
            lo = c * 7
            t = [0] * 128
            for v in range(128):
                s = 0
                bits = v
                while bits:
                    lsb = bits & -bits
                    b = lo + lsb.bit_length() - 1
                    sq = B2S.get(b)
                    if sq is not None:
                        s += pst[sq]
                    bits ^= lsb
                t[v] = s
            tables.append(tuple(t))
        return tuple(tables)

    return chunk(wm_pst), chunk(wk_pst), chunk(bm_pst), chunk(bk_pst)


WM_T, WK_T, BM_T, BK_T = _build_eval_tables()

# Bind chunk tables once, rather than indexing four nested tables at every leaf.
_MAN_TABLES = tuple((c * 7, WM_T[c], BM_T[c]) for c in range(9))
_KING_TABLES = tuple((c * 7, WK_T[c]) for c in range(9))

# ---------------------------------------------------------------------------
# Trained pattern evaluation (v3)
#
# Scan/Kingsrow's decisive structural lever: overlapping local MEN patterns
# whose weights are learned from game outcomes (Texel tuning), added as a
# correction on top of the frozen v2 hand eval.  Kings stay scalar (rare).
#
# Each pattern is a 4-wide x 2-tall block of board squares (a diamond cluster
# of mutually-diagonal men in real draughts geometry).  Every square is
# encoded as a base-3 trit (0 empty / 1 white man / 2 black man), giving a
# 3^8 = 6561-entry weight table per pattern.  The trit index is extracted with
# two shifts + two masks + two table lookups per pattern (no per-square loop):
# each block spans <= 12 internal bits, so a 2^12 lookup table maps the men
# bitboard window straight to its partial base-3 index.
# ---------------------------------------------------------------------------

PAT_TRITS = 8
PAT_ENTRIES = 3**PAT_TRITS  # 6561
_POW3 = tuple(3**i for i in range(PAT_TRITS))


def _build_patterns() -> tuple[tuple[int, ...], ...]:
    """Board-square membership (8 squares each) of the overlapping men
    patterns.  Deterministic; shared verbatim by the offline trainer."""

    def block(r: int, c0: int) -> tuple[int, ...]:
        return tuple(
            [r * 5 + c for c in range(c0, c0 + 4)] + [(r + 1) * 5 + c for c in range(c0, c0 + 4)]
        )

    pats: list[tuple[int, ...]] = []
    # Nine overlapping row-pairs, alternating horizontal window so every file
    # is covered; plus a second window on the top and bottom bands so the two
    # corner squares (4 and 49) are covered too.
    for r in range(9):
        pats.append(block(r, 0 if r % 2 == 0 else 1))
    pats.append(block(0, 1))
    pats.append(block(8, 1))
    return tuple(pats)


PATTERNS = _build_patterns()
N_PATTERNS = len(PATTERNS)


def _build_pattern_tables():
    """Precompute per-pattern (shift, window-mask, white-table, black-table).

    ``TW[v]`` / ``TB[v]`` map a masked men-bitboard window straight to the
    partial base-3 index contributed by the white / black men it contains;
    bits outside the eight pattern squares contribute nothing, so no runtime
    masking of stray bits is needed."""
    shifts: list[int] = []
    wmasks: list[int] = []
    tws: list[tuple[int, ...]] = []
    tbs: list[tuple[int, ...]] = []
    for pat in PATTERNS:
        bits = [S2B[s] for s in pat]
        sh = min(bits)
        width = max(bits) - sh + 1
        wmask = (1 << width) - 1
        # local bit position -> trit weight
        local = [(b - sh, _POW3[i]) for i, b in enumerate(bits)]
        size = 1 << width
        tw = [0] * size
        tb = [0] * size
        for lb, w in local:
            step = 1 << lb
            # every window value whose bit lb is set gains this trit
            for v in range(size):
                if v & step:
                    tw[v] += w
                    tb[v] += 2 * w
        shifts.append(sh)
        wmasks.append(wmask)
        tws.append(tuple(tw))
        tbs.append(tuple(tb))
    return tuple(shifts), tuple(wmasks), tuple(tws), tuple(tbs)


_PAT_SH, _PAT_WM, _PAT_TW, _PAT_TB = _build_pattern_tables()

WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "turbo_weights.bin")
_PAT_MAGIC = b"TPW1"

# Sentinels that disable the trained pattern term (fall back to the v2 hand
# eval). Handy for A/B measuring the training's Elo contribution.
_NO_WEIGHTS = {"", "none", "off", "0", "disable", "disabled"}


def _weights_path() -> Optional[str]:
    """Resolve the pattern-weights file, honouring the ``TURBO_WEIGHTS``
    override.  Set it to a custom ``.bin`` produced by
    ``tools/train_pattern_eval.py`` to load your own weights, or to one of
    ``none``/``off``/``0`` to run with the pattern term disabled.  Unset uses
    the shipped ``turbo_weights.bin``."""
    override = os.environ.get("TURBO_WEIGHTS")
    if override is None:
        return WEIGHTS_FILE
    if override.strip().lower() in _NO_WEIGHTS:
        return None
    return override


def _load_pattern_weights() -> tuple[tuple[int, ...], ...]:
    """Load trained int16 pattern weights, or fall back to all-zeros (which
    makes the pattern term a no-op, i.e. identical to the v2 hand eval)."""
    zeros = tuple((0,) * PAT_ENTRIES for _ in range(N_PATTERNS))
    path = _weights_path()
    if path is None:
        return zeros
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data[:4] != _PAT_MAGIC:
            return zeros
        n_pat, n_ent = struct.unpack_from("<HH", data, 4)
        if n_pat != N_PATTERNS or n_ent != PAT_ENTRIES:
            return zeros
        vals = struct.unpack_from(f"<{n_pat * n_ent}h", data, 8)
        return tuple(tuple(vals[p * n_ent : (p + 1) * n_ent]) for p in range(n_pat))
    except (OSError, struct.error):
        return zeros


PAT_W = _load_pattern_weights()
PAT_ACTIVE = any(any(row) for row in PAT_W)


def _fold_material_into_patterns():
    """Pay the men material/PST lookup once, at import, not at every leaf.

    The patterns cover every square. Assign each square to its first pattern
    and fold its white/black PST into that pattern's table. This preserves the
    trained evaluation exactly (including overlapping-pattern corrections).
    """
    assigned = set()
    tables = []
    for pattern, weights in zip(PATTERNS, PAT_W):
        additions = []
        for i, sq in enumerate(pattern):
            if sq not in assigned:
                assigned.add(sq)
                bit = S2B[sq]
                w = WM_T[bit // 7][1 << (bit % 7)]
                b = BM_T[bit // 7][1 << (bit % 7)]
                additions.append((_POW3[i], w, -b))
        row = list(weights)
        for div, w, b in additions:
            for index in range(PAT_ENTRIES):
                trit = (index // div) % 3
                row[index] += w if trit == 1 else b if trit == 2 else 0
        tables.append(tuple(row))
    assert len(assigned) == 50
    return tuple(zip(_PAT_SH, _PAT_WM, _PAT_TW, _PAT_TB, tables))


_FOLDED_PAT_TABLES = _fold_material_into_patterns()


def pattern_indices(wm: int, bm: int) -> list[int]:
    """Base-3 pattern indices for a position (used by the offline trainer)."""
    out = []
    for p in range(N_PATTERNS):
        sh = _PAT_SH[p]
        wm_ = _PAT_WM[p]
        out.append(_PAT_TW[p][(wm >> sh) & wm_] + _PAT_TB[p][(bm >> sh) & wm_])
    return out


# Left/right board halves (files 0-3 vs 6-9) for the balance term.
LEFT_MASK = sum(BIT[s] for s in range(50) if _file_of(s) <= 3)
RIGHT_MASK = sum(BIT[s] for s in range(50) if _file_of(s) >= 6)


def _evaluate(wm: int, wk: int, bm: int, bk: int, white_to_move: bool) -> int:
    """Static evaluation, side-to-move relative. No allocations."""
    score = 0
    if PAT_ACTIVE:
        for sh, mask, tw, tb, weights in _FOLDED_PAT_TABLES:
            score += weights[tw[(wm >> sh) & mask] + tb[(bm >> sh) & mask]]
    else:
        for sh, wt, bt in _MAN_TABLES:
            score += wt[(wm >> sh) & 127] - bt[(bm >> sh) & 127]
    if wk or bk:
        for sh, kt in _KING_TABLES:
            score += kt[(wk >> sh) & 127] - kt[(bk >> sh) & 127]
    empty = SQ_MASK ^ (wm | wk | bm | bk)
    # Cheap mobility: quiet man moves (kings excluded - rarely material).
    score += MOBILITY_WEIGHT * (
        ((wm >> 6) & empty).bit_count()
        + ((wm >> 7) & empty).bit_count()
        - ((bm << 6) & empty).bit_count()
        - ((bm << 7) & empty).bit_count()
    )
    # Left/right balance: lopsided formations are weak.
    w_all = wm | wk
    b_all = bm | bk
    score -= SKEW_WEIGHT * abs((w_all & LEFT_MASK).bit_count() - (w_all & RIGHT_MASK).bit_count())
    score += SKEW_WEIGHT * abs((b_all & LEFT_MASK).bit_count() - (b_all & RIGHT_MASK).bit_count())
    return score if white_to_move else -score


# ---------------------------------------------------------------------------
# Move generation (internal move = (from_bit, to_bit, captured_bitboard))
# ---------------------------------------------------------------------------


def _man_capture_dfs(
    frm: int,
    cur: int,
    enemy_rem: int,
    occ: int,
    caps: int,
    out: list[tuple[int, int, int]],
) -> bool:
    """Extend a man capture chain from ``cur``. Captured pieces stay in
    ``occ`` (they block until the move completes) but leave ``enemy_rem``
    (cannot be jumped twice). Returns True if any continuation existed."""
    extended = False
    # dir +6 (down-left)
    mid = cur << 6
    if mid & enemy_rem:
        land = cur << 12
        if land & SQ_MASK and not land & occ:
            extended = True
            if not _man_capture_dfs(frm, land, enemy_rem ^ mid, occ, caps | mid, out):
                out.append((frm, land, caps | mid))
    mid = cur << 7
    if mid & enemy_rem:
        land = cur << 14
        if land & SQ_MASK and not land & occ:
            extended = True
            if not _man_capture_dfs(frm, land, enemy_rem ^ mid, occ, caps | mid, out):
                out.append((frm, land, caps | mid))
    mid = cur >> 6
    if mid & enemy_rem:
        land = cur >> 12
        if land & SQ_MASK and not land & occ:
            extended = True
            if not _man_capture_dfs(frm, land, enemy_rem ^ mid, occ, caps | mid, out):
                out.append((frm, land, caps | mid))
    mid = cur >> 7
    if mid & enemy_rem:
        land = cur >> 14
        if land & SQ_MASK and not land & occ:
            extended = True
            if not _man_capture_dfs(frm, land, enemy_rem ^ mid, occ, caps | mid, out):
                out.append((frm, land, caps | mid))
    return extended


_UP = (6, 7)
_DOWN = (6, 7)


def _build_rays():
    rays = [()] * 63
    for bit in S2B:
        directions = []
        for down, sh in ((True, 6), (True, 7), (False, 6), (False, 7)):
            sq = 1 << bit
            ray = 0
            sq = (sq << sh) if down else (sq >> sh)
            while sq & SQ_MASK:
                ray |= sq
                sq = (sq << sh) if down else (sq >> sh)
            directions.append((down, sh, ray))
        rays[bit] = tuple(directions)
    return tuple(rays)


_RAYS = _build_rays()


def _king_capture_dfs(
    frm: int,
    cur: int,
    enemy_rem: int,
    occ: int,
    caps: int,
    out: list[tuple[int, int, int]],
) -> bool:
    """Flying-king capture chains. ``occ`` excludes the moving king itself
    but keeps captured pieces as blockers."""
    extended = False
    for down, sh, ray in _RAYS[cur.bit_length() - 1]:
        blockers = ray & occ
        if not blockers:
            continue
        sq = (blockers & -blockers) if down else (1 << (blockers.bit_length() - 1))
        if not sq & enemy_rem:
            continue
        victim = sq
        new_enemy = enemy_rem ^ victim
        new_caps = caps | victim
        land = (victim << sh) if down else (victim >> sh)
        while land & SQ_MASK and not land & occ:
            extended = True
            if not _king_capture_dfs(frm, land, new_enemy, occ, new_caps, out):
                out.append((frm, land, new_caps))
            land = (land << sh) if down else (land >> sh)
    return extended


def _gen_captures(wm: int, wk: int, bm: int, bk: int, white: bool) -> list[tuple[int, int, int]]:
    if white:
        men, kings, enemy = wm, wk, bm | bk
    else:
        men, kings, enemy = bm, bk, wm | wk
    if not enemy:
        return []
    all_p = wm | wk | bm | bk
    empty = SQ_MASK ^ all_p

    raw: list[tuple[int, int, int]] = []
    # Vectorized candidate detection: man with adjacent enemy + empty beyond.
    cand = men & (
        ((enemy >> 6) & (empty >> 12))
        | ((enemy >> 7) & (empty >> 14))
        | ((enemy << 6) & (empty << 12))
        | ((enemy << 7) & (empty << 14))
    )
    while cand:
        frm = cand & -cand
        cand ^= frm
        _man_capture_dfs(frm, frm, enemy, all_p ^ frm, 0, raw)
    kb = kings
    while kb:
        frm = kb & -kb
        kb ^= frm
        _king_capture_dfs(frm, frm, enemy, all_p ^ frm, 0, raw)

    if not raw:
        return raw
    # Majority rule: keep only maximum-capture chains, dedupe same outcomes.
    best = 0
    for mv in raw:
        n = mv[2].bit_count()
        if n > best:
            best = n
    if best == 1:
        return raw
    seen = set()
    result = []
    for mv in raw:
        if mv[2].bit_count() == best and mv not in seen:
            seen.add(mv)
            result.append(mv)
    return result


def _gen_quiets(wm: int, wk: int, bm: int, bk: int, white: bool) -> list[tuple[int, int, int]]:
    all_p = wm | wk | bm | bk
    empty = SQ_MASK ^ all_p
    moves: list[tuple[int, int, int]] = []
    if white:
        # White men move up (-6 / -7): target = man >> shift.
        t = (wm >> 6) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((lsb << 6, lsb, 0))
        t = (wm >> 7) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((lsb << 7, lsb, 0))
        kings = wk
    else:
        t = (bm << 6) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((lsb >> 6, lsb, 0))
        t = (bm << 7) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((lsb >> 7, lsb, 0))
        kings = bk
    while kings:
        frm = kings & -kings
        kings ^= frm
        for down, sh in ((True, 6), (True, 7), (False, 6), (False, 7)):
            sq = (frm << sh) if down else (frm >> sh)
            while sq & empty:
                moves.append((frm, sq, 0))
                sq = (sq << sh) if down else (sq >> sh)
    return moves


def _has_capture(wm: int, wk: int, bm: int, bk: int, white: bool) -> bool:
    """Fast capture-existence test (used for the quiescence threat check)."""
    if white:
        men, kings, enemy = wm, wk, bm | bk
    else:
        men, kings, enemy = bm, bk, wm | wk
    if not enemy:
        return False
    all_p = wm | wk | bm | bk
    empty = SQ_MASK ^ all_p
    if men & (
        ((enemy >> 6) & (empty >> 12))
        | ((enemy >> 7) & (empty >> 14))
        | ((enemy << 6) & (empty << 12))
        | ((enemy << 7) & (empty << 14))
    ):
        return True
    kb = kings
    while kb:
        frm = kb & -kb
        kb ^= frm
        for down, sh, ray in _RAYS[frm.bit_length() - 1]:
            blockers = ray & all_p
            if not blockers:
                continue
            sq = (blockers & -blockers) if down else (1 << (blockers.bit_length() - 1))
            if sq & enemy:
                land = (sq << sh) if down else (sq >> sh)
                if land & empty:
                    return True
    return False


def _apply(
    wm: int, wk: int, bm: int, bk: int, white: bool, mv: tuple[int, int, int]
) -> tuple[int, int, int, int, bool]:
    """Copy-make. Returns new bitboards and whether the mover was a man
    (for the halfmove clock)."""
    frm, to, caps = mv
    if white:
        if wm & frm:
            wm ^= frm
            if to & PROMO_W:
                wk |= to
            else:
                wm |= to
            was_man = True
        else:
            wk ^= frm
            wk |= to
            was_man = False
        if caps:
            bm &= ~caps
            bk &= ~caps
    else:
        if bm & frm:
            bm ^= frm
            if to & PROMO_B:
                bk |= to
            else:
                bm |= to
            was_man = True
        else:
            bk ^= frm
            bk |= to
            was_man = False
        if caps:
            wm &= ~caps
            wk &= ~caps
    return wm, wk, bm, bk, was_man


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class _Timeout(Exception):
    pass


TT_FLAG_EXACT = 0
TT_FLAG_LOWER = 1
TT_FLAG_UPPER = 2
TT_MAX = 2_000_000
EVAL_CACHE_MAX = 100_000
MAX_PLY = 128

HIST_INIT = 2048
HIST_MAX = 4096


class TurboEngine(Engine):
    """
    Fast alpha-beta engine for international draughts (10x10 only).

    Args:
        depth_limit: Maximum iterative-deepening depth (default 12).
        time_limit: Soft time budget per move in seconds.
        name: Engine name.

    Example:
        >>> from draughts import Board
        >>> from draughts.engines.turbo import TurboEngine
        >>> engine = TurboEngine(time_limit=0.5)
        >>> move = engine.get_best_move(Board())
    """

    def __init__(
        self,
        depth_limit: Optional[int] = 12,
        time_limit: Optional[float] = None,
        name: Optional[str] = None,
    ):
        if depth_limit is not None and depth_limit < 1:
            raise ValueError("depth_limit must be positive or None")
        if time_limit is not None and (not math.isfinite(time_limit) or time_limit <= 0):
            raise ValueError("time_limit must be finite and positive or None")
        super().__init__(depth_limit, time_limit, name)
        self.tt: dict = {}
        self._eval_cache: dict[tuple[int, int, int, int], int] = {}
        self.hist = [HIST_INIT] * (2 * 64 * 64)
        self.killers: list[list[tuple[int, int, int]]] = [[] for _ in range(MAX_PLY)]
        self.nodes = 0
        self._deadline: Optional[float] = None
        self._path: dict = {}
        self._history: dict = {}
        self.completed_depth = 0
        self._partial_mv: Optional[tuple[int, int, int]] = None
        self._partial_score = -INF

    # -- public API ---------------------------------------------------------

    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool = False
    ) -> Move | tuple[Move, float]:
        if type(board) is not StandardBoard:
            raise ValueError("TurboEngine supports only 10x10 international boards")
        self.nodes = 0
        self.completed_depth = 0
        legal = board.legal_moves
        if not legal:
            raise ValueError("No legal moves available")

        wm, wk, bm, bk = self._convert(board)
        white = board.turn == Color.WHITE
        if len(legal) == 1 and not with_evaluation:
            self.nodes = 1
            return legal[0]

        self._history = {}
        positions = iter(board._reversible_positions())
        next(positions)  # root is added by _root_iter, not twice
        conv = CORE_STANDARD.to_ghost
        for hwm, hwk, hbm, hbk, turn in positions:
            key = (conv(hwm), conv(hwk), conv(hbm), conv(hbk), turn == Color.WHITE)
            self._history[key] = self._history.get(key, 0) + 1
        best_mv, score = self._search_root(
            wm, wk, bm, bk, white, board.halfmove_clock, board._endgame_remaining
        )
        move = self._match_move(best_mv, legal)
        if with_evaluation:
            return move, score / 100.0
        return move

    # -- root ---------------------------------------------------------------

    def _search_root(
        self,
        wm: int,
        wk: int,
        bm: int,
        bk: int,
        white: bool,
        hm_clock: int,
        endgame: tuple[int, int] = (-1, -1),
    ) -> tuple[tuple[int, int, int], int]:
        self.nodes = 0
        self._path = self._history.copy()
        self.killers = [[] for _ in range(MAX_PLY)]
        self.completed_depth = 0
        if len(self.tt) > TT_MAX:
            self.tt.clear()
        if len(self._eval_cache) >= EVAL_CACHE_MAX:
            self._eval_cache.clear()
        self._deadline = time.perf_counter() + self.time_limit if self.time_limit else None
        max_depth = self.depth_limit or 64

        moves = _gen_captures(wm, wk, bm, bk, white) or _gen_quiets(wm, wk, bm, bk, white)
        best_mv = moves[0]
        best_score = -INF
        score = _evaluate(wm, wk, bm, bk, white)
        try:
            for depth in range(1, max_depth + 1):
                if self._deadline is not None and time.perf_counter() >= self._deadline:
                    break
                alpha, beta = -INF, INF
                if depth >= 4:
                    margin = 15
                    alpha, beta = score - margin, score + margin
                while True:
                    mv, sc = self._root_iter(
                        wm, wk, bm, bk, white, hm_clock, moves, depth, alpha, beta, endgame
                    )
                    if sc <= alpha:
                        alpha = max(-INF, alpha - (beta - alpha) * 2)
                    elif sc >= beta:
                        beta = min(INF, beta + (beta - alpha) * 2)
                    else:
                        best_mv, score = mv, sc
                        break
                best_score = score
                self.completed_depth = depth
                # Order root moves: best first for next iteration.
                moves.sort(key=lambda m: m != best_mv)
                if abs(score) > MATE - 256:
                    break
        except _Timeout:
            # Only an exact in-window partial result may replace the completed
            # iteration; unverified fail-high/low bounds are never promoted.
            if self._partial_mv is not None:
                best_mv, best_score = self._partial_mv, self._partial_score
        return best_mv, best_score if best_score != -INF else score

    def _root_iter(
        self,
        wm: int,
        wk: int,
        bm: int,
        bk: int,
        white: bool,
        hm_clock: int,
        moves: list,
        depth: int,
        alpha: int,
        beta: int,
        endgame: tuple[int, int] = (-1, -1),
    ) -> tuple[tuple[int, int, int], int]:
        best_mv = moves[0]
        best = -INF
        # Reset on *every* aspiration retry. Only scores strictly inside the
        # window are exact and eligible to replace the completed iteration.
        self._partial_mv = None
        self._partial_score = -INF
        window_alpha = alpha
        key = (wm, wk, bm, bk, white)
        count = self._path.get(key, 0)
        self._path[key] = count + 1
        try:
            for i, mv in enumerate(moves):
                nwm, nwk, nbm, nbk, was_man = _apply(wm, wk, bm, bk, white, mv)
                nhm = 0 if (mv[2] or was_man) else hm_clock + 1
                clocks = (
                    advance_clock(nwm, nwk, nbm, nbk, endgame)
                    if (nwk and nbk or endgame != (-1, -1))
                    else endgame
                )
                if i == 0:
                    sc = -self._negamax(
                        nwm, nwk, nbm, nbk, not white, depth - 1, -beta, -alpha, 1, nhm, clocks
                    )
                else:
                    sc = -self._negamax(
                        nwm, nwk, nbm, nbk, not white, depth - 1, -alpha - 1, -alpha, 1, nhm, clocks
                    )
                    if alpha < sc < beta:
                        sc = -self._negamax(
                            nwm, nwk, nbm, nbk, not white, depth - 1, -beta, -alpha, 1, nhm, clocks
                        )
                if sc > best:
                    best, best_mv = sc, mv
                    if window_alpha < sc < beta:
                        self._partial_mv, self._partial_score = mv, sc
                if sc > alpha:
                    alpha = sc
                if alpha >= beta:
                    break
        finally:
            if count:
                self._path[key] = count
            else:
                del self._path[key]
        return best_mv, best

    # -- inner nodes --------------------------------------------------------

    def _negamax(
        self,
        wm: int,
        wk: int,
        bm: int,
        bk: int,
        white: bool,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        hm_clock: int,
        endgame: tuple[int, int] = (-1, -1),
    ) -> int:
        self.nodes += 1
        if self._deadline is not None and not self.nodes & 127:
            if time.perf_counter() > self._deadline:
                raise _Timeout

        key = (wm, wk, bm, bk, white)
        path = self._path
        count = path.get(key, 0)
        if count >= 2:
            return DRAW

        if hm_clock >= 50 or 0 in endgame:
            if not (_gen_captures(wm, wk, bm, bk, white) or _gen_quiets(wm, wk, bm, bk, white)):
                return -(MATE - ply)
            return DRAW
        if ply >= MAX_PLY:
            if not (_gen_captures(wm, wk, bm, bk, white) or _gen_quiets(wm, wk, bm, bk, white)):
                return -(MATE - ply)
            return _evaluate(wm, wk, bm, bk, white)

        tt = self.tt
        tt_key = (*key, hm_clock, endgame)
        # A score following reversible moves depends on repetition history.
        # History is irrelevant immediately after an irreversible move.
        entry = tt.get(tt_key)
        tt_move = None
        if entry is not None:
            e_depth, e_flag, e_score, e_move, e_context = entry
            tt_move = e_move
            if e_score >= MATE - MAX_PLY:
                e_score -= ply
            elif e_score <= -MATE + MAX_PLY:
                e_score += ply
            if e_depth >= depth and e_context == (frozenset(path.items()) if hm_clock else None):
                if e_flag == TT_FLAG_EXACT:
                    return e_score
                if e_flag == TT_FLAG_LOWER:
                    if e_score >= beta:
                        return e_score
                elif e_flag == TT_FLAG_UPPER and e_score <= alpha:
                    return e_score

        captures = _gen_captures(wm, wk, bm, bk, white)
        if depth <= 0 and not captures:
            return self._qs_quiet(wm, wk, bm, bk, white, alpha, beta, ply, True, hm_clock, endgame)

        moves = captures or _gen_quiets(wm, wk, bm, bk, white)
        if not moves:
            return -(MATE - ply)  # side to move has no moves: loss

        if depth <= 0:
            # Forced capture: resolve the chain in quiescence style.
            best = -INF
            path[key] = count + 1
            try:
                for mv in moves:
                    nwm, nwk, nbm, nbk, _ = _apply(wm, wk, bm, bk, white, mv)
                    clocks = (
                        advance_clock(nwm, nwk, nbm, nbk, endgame)
                        if (nwk and nbk or endgame != (-1, -1))
                        else endgame
                    )
                    sc = -self._negamax(
                        nwm, nwk, nbm, nbk, not white, 0, -beta, -alpha, ply + 1, 0, clocks
                    )
                    if sc > best:
                        best = sc
                    if sc > alpha:
                        alpha = sc
                    if alpha >= beta:
                        break
            finally:
                if count:
                    path[key] = count
                else:
                    del path[key]
            return best

        # Single-reply extension.
        requested_depth = depth
        if len(moves) == 1:
            depth += 1

        # Scan-style forward pruning: shallow verification search at a
        # raised beta (draughts substitute for null-move pruning).
        if (
            depth >= 3
            and beta == alpha + 1
            and not captures
            and beta < MATE - 512
            and beta > -(MATE - 512)
        ):
            margin = 10 * depth
            new_beta = beta + margin
            v_depth = depth * 2 // 5
            sc = self._negamax(
                wm, wk, bm, bk, white, v_depth, new_beta - 1, new_beta, ply, hm_clock, endgame
            )
            if sc >= new_beta:
                return sc - margin

        # Move ordering: TT move first, then EMA history.
        if len(moves) > 1:
            hist = self.hist
            if captures:
                enemy_kings = bk if white else wk
                moves.sort(
                    key=lambda m: (m == tt_move, (m[2] & enemy_kings).bit_count()), reverse=True
                )
            else:
                killers = self.killers[ply]
                offset = 0 if white else 4096

                def order(m, _h=hist, _tt=tt_move, _k=killers, _o=offset):
                    if m == _tt:
                        return -HIST_MAX - 3
                    if m in _k:
                        return -HIST_MAX - 2 + _k.index(m)
                    return -_h[_o + ((m[0].bit_length() - 1) << 6) + m[1].bit_length() - 1]

                moves.sort(key=order)

        best = -INF
        best_move = None
        flag = TT_FLAG_UPPER
        orig_alpha = alpha
        path[key] = count + 1
        try:
            for i, mv in enumerate(moves):
                nwm, nwk, nbm, nbk, was_man = _apply(wm, wk, bm, bk, white, mv)
                nhm = 0 if (mv[2] or was_man) else hm_clock + 1
                clocks = (
                    advance_clock(nwm, nwk, nbm, nbk, endgame)
                    if (nwk and nbk or endgame != (-1, -1))
                    else endgame
                )
                new_depth = depth - 1

                red = 0
                if not captures and depth >= 3 and i >= 3 and best > -INF:
                    red = 1

                if i == 0:
                    sc = -self._negamax(
                        nwm,
                        nwk,
                        nbm,
                        nbk,
                        not white,
                        new_depth,
                        -beta,
                        -alpha,
                        ply + 1,
                        nhm,
                        clocks,
                    )
                else:
                    sc = -self._negamax(
                        nwm,
                        nwk,
                        nbm,
                        nbk,
                        not white,
                        new_depth - red,
                        -alpha - 1,
                        -alpha,
                        ply + 1,
                        nhm,
                        clocks,
                    )
                    if sc > alpha and (red or sc < beta):
                        sc = -self._negamax(
                            nwm,
                            nwk,
                            nbm,
                            nbk,
                            not white,
                            new_depth,
                            -beta,
                            -alpha,
                            ply + 1,
                            nhm,
                            clocks,
                        )
                if sc > best:
                    best = sc
                    best_move = mv
                if sc > alpha:
                    alpha = sc
                    flag = TT_FLAG_EXACT
                if alpha >= beta:
                    flag = TT_FLAG_LOWER
                    if not captures:
                        hist = self.hist
                        killers = self.killers[ply]
                        if mv not in killers:
                            killers.insert(0, mv)
                            del killers[2:]
                        offset = 0 if white else 4096
                        idx = offset + ((mv[0].bit_length() - 1) << 6) + mv[1].bit_length() - 1
                        hist[idx] += (HIST_MAX - hist[idx]) >> 5
                        for j in range(i):
                            pm = moves[j]
                            idx = offset + ((pm[0].bit_length() - 1) << 6) + pm[1].bit_length() - 1
                            hist[idx] -= hist[idx] >> 5
                    break
        finally:
            if count:
                path[key] = count
            else:
                del path[key]

        if flag == TT_FLAG_EXACT and best <= orig_alpha:
            flag = TT_FLAG_UPPER
        # Depth-preferred replacement: don't let shallow searches (e.g. the
        # forward-pruning verification) clobber deeper analysis; always keep
        # exact PV entries.
        cur = tt.get(tt_key)
        if cur is None or requested_depth >= cur[0] or flag == TT_FLAG_EXACT:
            stored_score = best
            if best >= MATE - MAX_PLY:
                stored_score += ply
            elif best <= -MATE + MAX_PLY:
                stored_score -= ply
            tt[tt_key] = (
                requested_depth,
                flag,
                stored_score,
                best_move,
                frozenset(path.items()) if hm_clock else None,
            )
        return best

    def _qs_quiet(
        self,
        wm: int,
        wk: int,
        bm: int,
        bk: int,
        white: bool,
        alpha: int,
        beta: int,
        ply: int,
        allow_threat_ext: bool,
        hm_clock: int = 0,
        endgame: tuple[int, int] = (-1, -1),
    ) -> int:
        """Quiet leaf: stand pat, unless the opponent threatens a capture -
        then spend one real ply so hanging pieces are seen (Scan's 'dodge')."""
        # The caller has ruled out captures. A flying king has a quiet move iff
        # an adjacent square is empty; no list allocation or ray walk needed.
        empty = SQ_MASK ^ (wm | wk | bm | bk)
        men, kings = (wm, wk) if white else (bm, bk)
        targets = ((men >> 6) | (men >> 7)) if white else ((men << 6) | (men << 7))
        if not (targets | (kings >> 6) | (kings >> 7) | (kings << 6) | (kings << 7)) & empty:
            return -(MATE - ply)
        if allow_threat_ext and ply < 48 and _has_capture(wm, wk, bm, bk, not white):
            return self._negamax(wm, wk, bm, bk, white, 1, alpha, beta, ply, hm_clock, endgame)
        # Static scores are independent of draw/repetition history and search
        # windows. Reuse them across iterative-deepening visits, but never cache
        # a quiescence-search bound as a static score.
        eval_key = (wm, wk, bm, bk)
        score = self._eval_cache.get(eval_key)
        if score is None:
            score = _evaluate(wm, wk, bm, bk, True)
            if len(self._eval_cache) < EVAL_CACHE_MAX:
                self._eval_cache[eval_key] = score
        return score if white else -score

    # -- board conversion ---------------------------------------------------

    @staticmethod
    def _convert(board: BaseBoard) -> tuple[int, int, int, int]:
        conv = CORE_STANDARD.to_ghost

        return (
            conv(board.white_men),
            conv(board.white_kings),
            conv(board.black_men),
            conv(board.black_kings),
        )

    @staticmethod
    def _match_move(mv: tuple[int, int, int], legal: list[Move]) -> Move:
        frm_sq = B2S[mv[0].bit_length() - 1]
        to_sq = B2S[mv[1].bit_length() - 1]
        caps = set()
        c = mv[2]
        while c:
            lsb = c & -c
            caps.add(B2S[lsb.bit_length() - 1])
            c ^= lsb
        for m in legal:
            if (
                m.square_list[0] == frm_sq
                and m.square_list[-1] == to_sq
                and set(m.captured_list) == caps
            ):
                return m
        raise ValueError(
            f"Internal move {frm_sq + 1}->{to_sq + 1} (caps {sorted(caps)}) "
            f"not found among legal moves"
        )


# ---------------------------------------------------------------------------
# Perft (used by tests to validate the internal move generator)
# ---------------------------------------------------------------------------


def perft(wm: int, wk: int, bm: int, bk: int, white: bool, depth: int) -> int:
    if depth == 0:
        return 1
    moves = _gen_captures(wm, wk, bm, bk, white) or _gen_quiets(wm, wk, bm, bk, white)
    if depth == 1:
        return len(moves)
    total = 0
    for mv in moves:
        nwm, nwk, nbm, nbk, _ = _apply(wm, wk, bm, bk, white, mv)
        total += perft(nwm, nwk, nbm, nbk, not white, depth - 1)
    return total


def perft_from_board(board: BaseBoard, depth: int) -> int:
    wm, wk, bm, bk = TurboEngine._convert(board)
    return perft(wm, wk, bm, bk, board.turn == Color.WHITE, depth)
