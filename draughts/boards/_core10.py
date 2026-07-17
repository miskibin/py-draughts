"""
Fast move generation core for 10x10 international draughts.

Uses Scan's 63-bit "ghost square" layout: squares 1..50 are packed into bits
0..62 with unused padding bits so that the four diagonal steps become uniform
shifts of 6 and 7 (``+6``/``+7`` down, ``-6``/``-7`` up). Whole-board integer
operations then replace the per-square recursion of the naive generator, and a
single vectorized test rules out captures in quiet positions without touching a
piece.

The generator here is the same one validated by ``test/test_turbo.py`` (perft
anchors + cross-check against the board), extended to record the full square
path of each capture so the public :class:`~draughts.move.Move` objects keep
their exact intermediate squares (issue #29).

Everything is expressed in board square indices (0..49) at the boundary so the
public board never sees the internal layout.
"""

from __future__ import annotations


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

# bit position -> square index, as a flat tuple for fast lookup off bit_length.
_MAXBIT = max(S2B) + 1
BIT_TO_SQ = tuple(B2S.get(b, -1) for b in range(_MAXBIT))


def _build_convert_tables() -> tuple[tuple[tuple[int, ...], ...], int]:
    """Chunked 50-bit -> ghost conversion: 5 windows of 10 bits, each mapped
    through a 1024-entry table. Converting a board is 5 lookups + ORs instead
    of a per-bit loop."""
    chunk, n_chunks = 10, 5
    tables = []
    for c in range(n_chunks):
        base = c * chunk
        tbl = [0] * (1 << chunk)
        for v in range(1 << chunk):
            out = 0
            bits = v
            while bits:
                lsb = bits & -bits
                sq = base + lsb.bit_length() - 1
                if sq < 50:
                    out |= 1 << S2B[sq]
                bits ^= lsb
            tbl[v] = out
        tables.append(tuple(tbl))
    return tuple(tables), chunk


_CONV_T, _CHUNK = _build_convert_tables()
_T0, _T1, _T2, _T3, _T4 = _CONV_T


def to_ghost(bb: int) -> int:
    """Map a 50-bit board bitboard into the ghost layout."""
    return (
        _T0[bb & 1023]
        | _T1[(bb >> 10) & 1023]
        | _T2[(bb >> 20) & 1023]
        | _T3[(bb >> 30) & 1023]
        | _T4[(bb >> 40) & 1023]
    )


# ---------------------------------------------------------------------------
# Capture generation (path-tracking). ``path``/``caps`` are shared mutable
# lists used as a backtracking stack, so no per-branch allocation happens until
# a completed chain is emitted.
# ---------------------------------------------------------------------------


def _man_capture_dfs(
    cur: int,
    enemy_rem: int,
    occ: int,
    path: list[int],
    caps: list[int],
    out: list[tuple[tuple[int, ...], tuple[int, ...]]],
) -> bool:
    """Extend a man capture chain from the bit ``cur``. Captured pieces stay in
    ``occ`` (they block until the move completes) but leave ``enemy_rem`` so
    they cannot be jumped twice."""
    extended = False
    for sh in (6, 7, -6, -7):
        mid = (cur << sh) if sh > 0 else (cur >> -sh)
        if mid & enemy_rem:
            land = (cur << (2 * sh)) if sh > 0 else (cur >> (-2 * sh))
            if land & SQ_MASK and not land & occ:
                extended = True
                path.append(BIT_TO_SQ[land.bit_length() - 1])
                caps.append(BIT_TO_SQ[mid.bit_length() - 1])
                if not _man_capture_dfs(land, enemy_rem ^ mid, occ, path, caps, out):
                    out.append((tuple(path), tuple(caps)))
                path.pop()
                caps.pop()
    return extended


def _king_capture_dfs(
    cur: int,
    enemy_rem: int,
    occ: int,
    path: list[int],
    caps: list[int],
    out: list[tuple[tuple[int, ...], tuple[int, ...]]],
) -> bool:
    """Flying-king capture chains. ``occ`` excludes the moving king itself but
    keeps captured pieces as blockers, so the king can neither jump the same
    piece twice nor cross an already-captured square."""
    extended = False
    for sh in (6, 7, -6, -7):
        pos = sh > 0
        step = sh if pos else -sh
        sq = (cur << step) if pos else (cur >> step)
        while sq & SQ_MASK and not sq & occ:
            sq = (sq << step) if pos else (sq >> step)
        if not (sq & SQ_MASK and sq & enemy_rem):
            continue
        victim = sq
        new_enemy = enemy_rem ^ victim
        caps.append(BIT_TO_SQ[victim.bit_length() - 1])
        land = (victim << step) if pos else (victim >> step)
        while land & SQ_MASK and not land & occ:
            extended = True
            path.append(BIT_TO_SQ[land.bit_length() - 1])
            if not _king_capture_dfs(land, new_enemy, occ, path, caps, out):
                out.append((tuple(path), tuple(caps)))
            path.pop()
            land = (land << step) if pos else (land >> step)
        caps.pop()
    return extended


def gen_captures(
    wm: int, wk: int, bm: int, bk: int, white: bool
) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """All capture chains for the side to move, each as ``(path, captured)``
    tuples of square indices. No maximum-capture filtering is applied here."""
    if white:
        men, kings, enemy = wm, wk, bm | bk
    else:
        men, kings, enemy = bm, bk, wm | wk
    if not enemy:
        return []
    all_p = wm | wk | bm | bk
    empty = SQ_MASK ^ all_p

    out: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    cand = men & (
        ((enemy >> 6) & (empty >> 12))
        | ((enemy >> 7) & (empty >> 14))
        | ((enemy << 6) & (empty << 12))
        | ((enemy << 7) & (empty << 14))
    )
    while cand:
        frm = cand & -cand
        cand ^= frm
        frm_sq = BIT_TO_SQ[frm.bit_length() - 1]
        _man_capture_dfs(frm, enemy, all_p ^ frm, [frm_sq], [], out)
    kb = kings
    while kb:
        frm = kb & -kb
        kb ^= frm
        frm_sq = BIT_TO_SQ[frm.bit_length() - 1]
        _king_capture_dfs(frm, enemy, all_p ^ frm, [frm_sq], [], out)
    return out


def gen_quiets(wm: int, wk: int, bm: int, bk: int, white: bool) -> list[tuple[int, int]]:
    """All non-capturing moves for the side to move, as ``(from, to)`` square
    index pairs."""
    all_p = wm | wk | bm | bk
    empty = SQ_MASK ^ all_p
    b2s = BIT_TO_SQ
    moves: list[tuple[int, int]] = []
    if white:
        t = (wm >> 6) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((b2s[(lsb << 6).bit_length() - 1], b2s[lsb.bit_length() - 1]))
        t = (wm >> 7) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((b2s[(lsb << 7).bit_length() - 1], b2s[lsb.bit_length() - 1]))
        kings = wk
    else:
        t = (bm << 6) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((b2s[(lsb >> 6).bit_length() - 1], b2s[lsb.bit_length() - 1]))
        t = (bm << 7) & empty
        while t:
            lsb = t & -t
            t ^= lsb
            moves.append((b2s[(lsb >> 7).bit_length() - 1], b2s[lsb.bit_length() - 1]))
        kings = bk
    while kings:
        frm = kings & -kings
        kings ^= frm
        frm_sq = b2s[frm.bit_length() - 1]
        for sh in (6, 7, -6, -7):
            pos = sh > 0
            step = sh if pos else -sh
            sq = (frm << step) if pos else (frm >> step)
            while sq & empty:
                moves.append((frm_sq, b2s[sq.bit_length() - 1]))
                sq = (sq << step) if pos else (sq >> step)
    return moves
