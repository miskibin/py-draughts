"""
Brazilian Draughts - 8x8 board with International (FMJD) rules.

Subclass of RussianBoard. Differences from Russian:
- Mandatory MAX capture (must take the longest sequence available).
- No mid-capture promotion: a man passing through the king's row during a
  capture chain stays a man until the move finishes; promotion is then
  applied by ``BaseBoard.push``.
"""

from __future__ import annotations

from draughts.boards.russian import JUMP_TGT, MOVE_TGT
from draughts.boards.russian import Board as RussianBoard
from draughts.move import Move


class Board(RussianBoard):
    """
    Brazilian Draughts.

    - 8×8 board, 32 squares (inherits geometry from Russian)
    - Flying kings, men capture in all 4 diagonal directions
    - Captures mandatory and must take the maximum number of pieces
    - Promotion only at the end of a move (no mid-capture promotion)

    GameType 26 per pydraughts/lidraughts convention.
    """

    GAME_TYPE = 26
    VARIANT_NAME = "Brazilian draughts"

    @property
    def legal_moves(self) -> list[Move]:
        captures = self._gen_captures()
        if captures:
            max_len = max(m._len for m in captures)
            return [m for m in captures if m._len == max_len]
        return self._gen_simple()

    def _man_captures(
        self, sq: int, enemy: int, captured: set[int], out: list[Move], is_white: bool
    ) -> None:
        """Like Russian's, but a man crossing the promotion rank stays a man."""
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq

        for d in range(4):
            mid, land = MOVE_TGT[sq][d], JUMP_TGT[sq][d]
            if mid == -1 or land == -1 or mid in captured:
                continue
            mid_bit = 1 << mid
            if not (enemy & mid_bit):
                continue
            land_bit = 1 << land
            if (all_p & land_bit) and not (src_bit & land_bit):
                continue

            cap_piece = 1 if bm & mid_bit else (2 if bk & mid_bit else (-1 if wm & mid_bit else -2))

            if wm & src_bit:
                self.white_men = (wm & ~src_bit) | land_bit
            else:
                self.black_men = (bm & ~src_bit) | land_bit
            self.white_men &= ~mid_bit
            self.white_kings &= ~mid_bit
            self.black_men &= ~mid_bit
            self.black_kings &= ~mid_bit

            sub: list[Move] = []
            captured.add(mid)
            self._man_captures(land, enemy, captured, sub, is_white)
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk

            base = Move([sq, land], [mid], [cap_piece])
            out.extend([base + s for s in sub] if sub else [base])
