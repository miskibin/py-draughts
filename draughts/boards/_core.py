"""
Unified ghost-layout bitboard move-generation core for the diagonal draughts
variants (8x8 and 10x10).

All four diagonal directions are made uniform bit shifts by packing the ``half``
dark squares of each row into consecutive bits and inserting padding between
rows (one bit after even rows, two after odd rows). A down step is then a left
shift of ``half + 1`` or ``half + 2`` and an up step the mirrored right shift;
off-board steps land on padding bits that are absent from ``SQ_MASK`` and are
rejected by a single mask test. This is Scan's 63-bit layout for the 10x10 board
(``half = 5`` -> shifts 6/7) and the same construction scaled to the 8x8 board
(``half = 4`` -> shifts 5/6, a 42-bit layout).

Whole-board integer operations then replace the per-square recursion of the
naive generators, and a single vectorized test rules out captures in quiet
positions without touching a piece. Everything is expressed in board square
indices at the boundary so the public boards never see the internal layout.

The per-variant rule differences are explicit constructor flags rather than
scattered conditionals:

* ``men_forward_only`` - men capture only in their moving direction (American)
  versus all four diagonals (Russian/Brazilian/Standard).
* ``flying_kings`` - kings slide any distance (Russian/Brazilian/Standard)
  versus one square (American short kings).
* ``mid_capture_promotion`` - a man that reaches the crown row mid-chain
  immediately becomes a king and continues capturing (Russian only).

The maximum-capture rule (Standard/Brazilian) is applied by the board on the
raw chains this core returns, not here, so free-choice variants (Russian /
American) simply keep every chain.

In every variant a captured piece stays on the board as a blocker until the
whole chain ends: it may be neither jumped twice nor landed on nor (for flying
kings) flown over again (the "Turkish strike" rule; cf. issue #43).
"""

from __future__ import annotations

from typing import Callable

# ``gen_captures`` returns a list of completed capture chains, each a tuple of
# ``(path square indices, captured square indices, promoted?)``. The square
# sequences are tuples: snapshotting a finished chain as a tuple is cheaper than
# as a list, and the board materializes lists only for the moves it keeps.


class _Geometry:
    """Ghost-square layout and board<->ghost conversion for one board size."""

    __slots__ = (
        "squares",
        "s1",
        "s2",
        "BIT_TO_SQ",
        "SQ_MASK",
        "BIT",
        "PROMO_WHITE",
        "PROMO_BLACK",
        "KING_RAYS",
        "to_ghost",
    )

    def __init__(self, size: int) -> None:
        half = size // 2
        self.squares = size * half
        # Down shifts: half + 1 (even->odd rows) and half + 2 (odd->even rows).
        self.s1, self.s2 = half + 1, half + 2

        s2b: list[int] = []
        bit = 0
        for row in range(size):
            for _ in range(half):
                s2b.append(bit)
                bit += 1
            bit += 1 if row % 2 == 0 else 2
        self.BIT = tuple(1 << b for b in s2b)
        maxbit = max(s2b) + 1
        self.BIT_TO_SQ = tuple({b: i for i, b in enumerate(s2b)}.get(b, -1) for b in range(maxbit))
        mask = 0
        for b in s2b:
            mask |= 1 << b
        self.SQ_MASK = mask

        # Crown rows in board-square space: first ``half`` squares (row 0, white)
        # and last ``half`` squares (bottom row, black).
        self.PROMO_WHITE = self._sqs_to_ghost(range(half))
        self.PROMO_BLACK = self._sqs_to_ghost(range(self.squares - half, self.squares))

        self.KING_RAYS = self._build_king_rays()
        self.to_ghost = self._build_to_ghost()

    def _sqs_to_ghost(self, sqs) -> int:
        out = 0
        for sq in sqs:
            out |= self.BIT[sq]
        return out

    def _build_to_ghost(self) -> Callable[[int], int]:
        """Chunked 10-bit-window conversion, unrolled per geometry so a board is
        mapped into the ghost layout with a handful of lookups and ORs."""
        chunk = 10
        n_chunks = (self.squares + chunk - 1) // chunk
        tables: list[tuple[int, ...]] = []
        for c in range(n_chunks):
            base = c * chunk
            tbl = [0] * (1 << chunk)
            for v in range(1 << chunk):
                out = 0
                bits = v
                while bits:
                    lsb = bits & -bits
                    sq = base + lsb.bit_length() - 1
                    if sq < self.squares:
                        out |= self.BIT[sq]
                    bits ^= lsb
                tbl[v] = out
            tables.append(tuple(tbl))
        terms = " | ".join(f"_t{c}[(bb >> {c * chunk}) & 1023]" for c in range(n_chunks))
        ns: dict = {f"_t{c}": tables[c] for c in range(n_chunks)}
        src = f"def to_ghost(bb):\n    return {terms}\n"
        exec(src, ns)
        return ns["to_ghost"]

    def _build_king_rays(self) -> tuple[tuple[tuple[int, ...], ...], ...]:
        """For each board square, the four diagonal rays as tuples of square
        indices (used for capture-path verification in tests)."""
        b2s, mask = self.BIT_TO_SQ, self.SQ_MASK
        rays = []
        for sq in range(self.squares):
            frm = self.BIT[sq]
            sq_rays = []
            for sh in (self.s1, self.s2, -self.s1, -self.s2):
                r = []
                cur = frm
                while True:
                    cur = (cur << sh) if sh > 0 else (cur >> -sh)
                    if not (cur & mask):
                        break
                    r.append(b2s[cur.bit_length() - 1])
                sq_rays.append(tuple(r))
            rays.append(tuple(sq_rays))
        return tuple(rays)


class MoveGen:
    """Move generator bound to one geometry and one variant's rule flags.

    The capture/quiet generators are built as closures over the geometry and rule
    constants so the hot path uses local (cell) variables and direct recursion
    instead of attribute lookups and bound-method dispatch. This keeps the 10x10
    generator at the speed of a hand-written per-board core while a single
    parameterized definition serves every square-diagonal variant.
    """

    __slots__ = (
        "geo",
        "to_ghost",
        "KING_RAYS",
        "gen_captures",
        "gen_quiets",
        "gen_moves",
    )

    def __init__(
        self,
        size: int,
        *,
        men_forward_only: bool,
        flying_kings: bool,
        mid_capture_promotion: bool,
    ) -> None:
        self.geo = geo = _Geometry(size)
        self.to_ghost = geo.to_ghost
        self.KING_RAYS = geo.KING_RAYS
        # The rule flags and mask copies are only consumed while building the
        # closures, so they live as locals in ``_build`` rather than as slots.
        self.gen_captures, self.gen_quiets, self.gen_moves = self._build(
            men_forward_only=men_forward_only,
            flying_kings=flying_kings,
            mid_capture_promotion=mid_capture_promotion,
        )

    def _build(self, *, men_forward_only: bool, flying_kings: bool, mid_capture_promotion: bool):
        geo = self.geo
        SQ_MASK = geo.SQ_MASK
        b2s = geo.BIT_TO_SQ
        s1, s2 = geo.s1, geo.s2
        all_dirs = (s1, s2, -s1, -s2)
        flying = flying_kings
        mid_promo = mid_capture_promotion
        promo_white = geo.PROMO_WHITE
        promo_black = geo.PROMO_BLACK
        white_man_dirs = (-s1, -s2) if men_forward_only else all_dirs
        black_man_dirs = (s1, s2) if men_forward_only else all_dirs
        d1, d2 = 2 * s1, 2 * s2  # capture landing distances

        # -- capture chains (path tracking) ---------------------------------
        # ``path`` / ``caps`` are a shared backtracking stack; captured pieces
        # stay in ``occ`` (blockers until the move ends) but leave ``enemy_rem``
        # so they cannot be jumped twice (Turkish strike; cf. issue #43).

        def king_dfs(cur, enemy_rem, occ, promo, path, caps, out):
            """Flying-king capture chains. ``occ`` excludes the moving king but
            keeps captured pieces as blockers."""
            extended = False
            for sh in all_dirs:
                pos = sh > 0
                step = sh if pos else -sh
                sq = (cur << step) if pos else (cur >> step)
                while sq & SQ_MASK and not sq & occ:
                    sq = (sq << step) if pos else (sq >> step)
                if not (sq & SQ_MASK and sq & enemy_rem):
                    continue
                victim = sq
                new_enemy = enemy_rem ^ victim
                caps.append(b2s[victim.bit_length() - 1])
                land = (victim << step) if pos else (victim >> step)
                while land & SQ_MASK and not land & occ:
                    extended = True
                    path.append(b2s[land.bit_length() - 1])
                    if not king_dfs(land, new_enemy, occ, promo, path, caps, out):
                        out.append((tuple(path), tuple(caps), promo))
                    path.pop()
                    land = (land << step) if pos else (land >> step)
                caps.pop()
            return extended

        if mid_promo:

            def man_dfs(cur, enemy_rem, occ, dirs, promo, path, caps, out):
                """Man captures with mid-chain promotion (Russian): a man reaching
                the crown row becomes a king and continues capturing as one."""
                extended = False
                for sh in dirs:
                    if sh > 0:
                        mid = cur << sh
                        land = cur << (2 * sh)
                    else:
                        mid = cur >> -sh
                        land = cur >> (-2 * sh)
                    if mid & enemy_rem and land & SQ_MASK and not land & occ:
                        extended = True
                        path.append(b2s[land.bit_length() - 1])
                        caps.append(b2s[mid.bit_length() - 1])
                        if land & promo:
                            if not king_dfs(land, enemy_rem ^ mid, occ, True, path, caps, out):
                                out.append((tuple(path), tuple(caps), True))
                        elif not man_dfs(
                            land, enemy_rem ^ mid, occ, dirs, promo, path, caps, out
                        ):
                            out.append((tuple(path), tuple(caps), False))
                        path.pop()
                        caps.pop()
                return extended

        else:

            def man_dfs(cur, enemy_rem, occ, dirs, promo, path, caps, out):
                """Man captures without mid-chain promotion. A man crossing the
                crown row stays a man; the board crowns it only if the chain ends
                there (via ``BaseBoard.push``). ``promo`` is unused."""
                extended = False
                for sh in dirs:
                    if sh > 0:
                        mid = cur << sh
                        land = cur << (2 * sh)
                    else:
                        mid = cur >> -sh
                        land = cur >> (-2 * sh)
                    if mid & enemy_rem and land & SQ_MASK and not land & occ:
                        extended = True
                        path.append(b2s[land.bit_length() - 1])
                        caps.append(b2s[mid.bit_length() - 1])
                        if not man_dfs(land, enemy_rem ^ mid, occ, dirs, promo, path, caps, out):
                            out.append((tuple(path), tuple(caps), False))
                        path.pop()
                        caps.pop()
                return extended

        def _captures(wm, wk, bm, bk, white, all_p, empty):
            """Every capture chain for the side to move as ``(path, captured,
            promo)`` tuples of board-square indices. No max-capture filtering.
            ``all_p`` / ``empty`` are precomputed by the caller so a quiet node
            does not derive them twice (once here, once for the quiet fallback)."""
            if white:
                men, kings, enemy = wm, wk, bm | bk
                man_dirs, promo = white_man_dirs, promo_white
            else:
                men, kings, enemy = bm, bk, wm | wk
                man_dirs, promo = black_man_dirs, promo_black
            if not enemy:
                return []
            out = []

            # Men with an enemy one step away and an empty landing two steps away,
            # in any of the four diagonals. A superset for forward-only men (the
            # direction-restricted DFS below discards the backward hits), so the
            # quiet-position early-out stays a single whole-board expression.
            cand = men & (
                ((enemy >> s1) & (empty >> d1))
                | ((enemy >> s2) & (empty >> d2))
                | ((enemy << s1) & (empty << d1))
                | ((enemy << s2) & (empty << d2))
            )
            while cand:
                frm = cand & -cand
                cand ^= frm
                frm_sq = b2s[frm.bit_length() - 1]
                man_dfs(frm, enemy, all_p ^ frm, man_dirs, promo, [frm_sq], [], out)

            kb = kings
            if flying:
                while kb:
                    frm = kb & -kb
                    kb ^= frm
                    frm_sq = b2s[frm.bit_length() - 1]
                    king_dfs(frm, enemy, all_p ^ frm, False, [frm_sq], [], out)
            else:
                # Short kings (American): one-square jumps in all four diagonals.
                while kb:
                    frm = kb & -kb
                    kb ^= frm
                    frm_sq = b2s[frm.bit_length() - 1]
                    man_dfs(frm, enemy, all_p ^ frm, all_dirs, 0, [frm_sq], [], out)
            return out

        def _quiets(wm, wk, bm, bk, white, all_p, empty):
            """Non-capturing moves as ``[from, to]`` square-index pairs (fresh
            lists handed straight to Move). Men move forward only; kings slide
            (flying) or step one square. ``all_p`` is unused here but kept in the
            signature so the caller can compute the masks once and pass both."""
            moves = []
            if white:
                for sh in (s1, s2):
                    t = (wm >> sh) & empty
                    while t:
                        lsb = t & -t
                        t ^= lsb
                        moves.append([b2s[(lsb << sh).bit_length() - 1], b2s[lsb.bit_length() - 1]])
                kings = wk
            else:
                for sh in (s1, s2):
                    t = (bm << sh) & empty
                    while t:
                        lsb = t & -t
                        t ^= lsb
                        moves.append([b2s[(lsb >> sh).bit_length() - 1], b2s[lsb.bit_length() - 1]])
                kings = bk

            if flying:
                while kings:
                    frm = kings & -kings
                    kings ^= frm
                    frm_sq = b2s[frm.bit_length() - 1]
                    for sh in all_dirs:
                        pos = sh > 0
                        step = sh if pos else -sh
                        sq = (frm << step) if pos else (frm >> step)
                        while sq & empty:
                            moves.append([frm_sq, b2s[sq.bit_length() - 1]])
                            sq = (sq << step) if pos else (sq >> step)
            else:
                while kings:
                    frm = kings & -kings
                    kings ^= frm
                    frm_sq = b2s[frm.bit_length() - 1]
                    for sh in all_dirs:
                        to = (frm << sh) if sh > 0 else (frm >> -sh)
                        if to & empty:
                            moves.append([frm_sq, b2s[to.bit_length() - 1]])
            return moves

        # Public closures. ``gen_captures`` / ``gen_quiets`` keep their standalone
        # signatures (each derives its own masks); ``gen_moves`` is the boundary
        # the boards use -- it derives ``all_p`` / ``empty`` once and reuses them
        # for both the capture scan and the quiet fallback.
        def gen_captures(wm, wk, bm, bk, white):
            all_p = wm | wk | bm | bk
            return _captures(wm, wk, bm, bk, white, all_p, SQ_MASK ^ all_p)

        def gen_quiets(wm, wk, bm, bk, white):
            all_p = wm | wk | bm | bk
            return _quiets(wm, wk, bm, bk, white, all_p, SQ_MASK ^ all_p)

        def gen_moves(wm, wk, bm, bk, white, captures_optional):
            """Return ``(captures, quiets)`` for the side to move. ``quiets`` is
            ``None`` when captures are present and forced (they win over quiets);
            with ``captures_optional`` (American) both lists are always returned."""
            all_p = wm | wk | bm | bk
            empty = SQ_MASK ^ all_p
            caps = _captures(wm, wk, bm, bk, white, all_p, empty)
            if captures_optional or not caps:
                return caps, _quiets(wm, wk, bm, bk, white, all_p, empty)
            return caps, None

        return gen_captures, gen_quiets, gen_moves


# Per-variant generators, built once at import. Antidraughts and Breakthrough
# reuse Standard's; Frysk reuses Frisian's (untouched, orthogonal geometry).
CORE_STANDARD = MoveGen(10, men_forward_only=False, flying_kings=True, mid_capture_promotion=False)
CORE_AMERICAN = MoveGen(8, men_forward_only=True, flying_kings=False, mid_capture_promotion=False)
CORE_RUSSIAN = MoveGen(8, men_forward_only=False, flying_kings=True, mid_capture_promotion=True)
CORE_BRAZILIAN = MoveGen(8, men_forward_only=False, flying_kings=True, mid_capture_promotion=False)
