"""FMJD international endgame clocks (Annex 1, articles 6.3 and 6.4).

Unlike the 25-move rule, these clocks survive man moves and captures.
Values count remaining plies; -1 means that the material condition has not
occurred yet. A win on the last allowed move takes precedence over a draw.
"""


def endgame_limits(wm: int, wk: int, bm: int, bk: int) -> tuple[int, int]:
    """Initial limits from piece *counts*, not bitboards."""
    if wm == 0 and wk == 1 and bk >= 1 and 1 <= bm + bk <= 3:
        other = bm + bk
    elif bm == 0 and bk == 1 and wk >= 1 and 1 <= wm + wk <= 3:
        other = wm + wk
    else:
        return -1, -1
    return (32 if other == 3 else -1), (10 if other <= 2 else -1)


def advance_clock(
    wm: int, wk: int, bm: int, bk: int, remaining: tuple[int, int]
) -> tuple[int, int]:
    """Advance one ply and start newly applicable endgame clocks."""
    a, b = remaining
    a = max(0, a - 1) if a >= 0 else -1
    b = max(0, b - 1) if b >= 0 else -1
    if wk and bk and (wm | wk | bm | bk).bit_count() <= 4:
        new_a, new_b = endgame_limits(
            wm.bit_count(), wk.bit_count(), bm.bit_count(), bk.bit_count()
        )
        if a < 0:
            a = new_a
        if b < 0:
            b = new_b
    return a, b
