"""
Standard (International) Draughts - 10x10 board, flying kings, mandatory max captures.
"""
from __future__ import annotations

import numpy as np

from draughts.boards.base import BaseBoard
from draughts.models import Color, Figure
from draughts.move import Move

# fmt: off
SQUARES = [B10, D10, F10, H10, J10, 
A9, C9, E9, G9, I9, B8, D8, F8, H8, J8,
           A7, C7, E7, G7, I7, B6, D6, F6, H6, J6, A5, C5, E5, G5, I5,
           B4, D4, F4, H4, J4, A3, C3, E3, G3, I3, B2, D2, F2, H2, J2,
           A1, C1, E1, G1, I1] = range(50)
# fmt: on

MASK_50 = (1 << 50) - 1
ROW = [((1 << 5) - 1) << (i * 5) for i in range(10)]
EVEN_ROWS = ROW[0] | ROW[2] | ROW[4] | ROW[6] | ROW[8]
ODD_ROWS = ROW[1] | ROW[3] | ROW[5] | ROW[7] | ROW[9]
EVEN_RIGHT = sum(1 << (i * 10 + 4) for i in range(5))
ODD_LEFT = sum(1 << (i * 10 + 5) for i in range(5))


def _build_tables():
    EVEN_SHIFTS, ODD_SHIFTS = (-4, -5, 6, 5), (-5, -6, 5, 4)
    move_tgt = []
    for sq in range(50):
        row, col = sq // 5, sq % 5
        is_even = row % 2 == 0
        shifts = EVEN_SHIFTS if is_even else ODD_SHIFTS
        blocks = [col == 4, False, col == 4, False] if is_even else [False, col == 0, False, col == 0]
        targets = [-1, -1, -1, -1]
        for d in range(4):
            if not blocks[d]:
                t = sq + shifts[d]
                if 0 <= t < 50 and (t // 5 - row) == (-1 if d < 2 else 1):
                    targets[d] = t
        move_tgt.append(tuple(targets))
    
    jump_tgt = [tuple(move_tgt[move_tgt[sq][d]][d] if move_tgt[sq][d] != -1 and move_tgt[move_tgt[sq][d]][d] != -1 else -1 for d in range(4)) for sq in range(50)]
    
    rays = []
    for sq in range(50):
        sq_rays = [[], [], [], []]
        for d in range(4):
            cur = sq
            while (nxt := move_tgt[cur][d]) != -1:
                sq_rays[d].append(nxt)
                cur = nxt
        rays.append(tuple(tuple(r) for r in sq_rays))
    
    return tuple(move_tgt), tuple(jump_tgt), tuple(rays)

MOVE_TGT, JUMP_TGT, KING_RAYS = _build_tables()


class Board(BaseBoard):
    """
    Standard (International) Draughts.
    
    - 10×10 board, 50 squares
    - Flying kings (move any distance)
    - All pieces capture forwards and backwards
    - Captures mandatory, must take maximum
    """
    
    GAME_TYPE = 20
    VARIANT_NAME = "Standard (international) checkers"
    STARTING_COLOR = Color.WHITE
    SQUARES_COUNT = 50
    PROMO_WHITE = ROW[0]
    PROMO_BLACK = ROW[9]
    STARTING_POSITION = np.array([1] * 20 + [0] * 10 + [-1] * 20, dtype=np.int8)
    ROW_IDX = {v: v // 5 for v in range(50)}
    COL_IDX = {v: v % 10 for v in range(50)}
    
    def _init_default_position(self) -> None:
        self.black_men = (1 << 20) - 1
        self.black_kings = 0
        self.white_men = ((1 << 20) - 1) << 30
        self.white_kings = 0
    
    @property
    def legal_moves(self) -> list[Move]:
        captures = self._gen_captures()
        if captures:
            max_len = max(m._len for m in captures)
            return [m for m in captures if m._len == max_len]
        return self._gen_simple()
    
    def _gen_simple(self) -> list[Move]:
        moves = []
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        empty = ~(wm | wk | bm | bk) & MASK_50
        
        if self.turn == Color.WHITE:
            men, even, odd = wm & ~ROW[0], wm & EVEN_ROWS & ~ROW[0], wm & ODD_ROWS
            for bb, shift in [((even & ~EVEN_RIGHT) >> 4, 4), (odd >> 5, 5), (even >> 5, 5), ((odd & ~ODD_LEFT) >> 6, 6)]:
                bb &= empty
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            bb = wk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for ray in KING_RAYS[sq]:
                    for t in ray:
                        if empty & (1 << t): moves.append(Move([sq, t]))
                        else: break
        else:
            men, even, odd = bm & ~ROW[9], bm & EVEN_ROWS, bm & ODD_ROWS & ~ROW[9]
            for bb, shift in [((even & ~EVEN_RIGHT) << 6, -6), (odd << 5, -5), (even << 5, -5), ((odd & ~ODD_LEFT) << 4, -4)]:
                bb = bb & empty & MASK_50
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            bb = bk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for ray in KING_RAYS[sq]:
                    for t in ray:
                        if empty & (1 << t): moves.append(Move([sq, t]))
                        else: break
        return moves
    
    def _gen_captures(self) -> list[Move]:
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        is_white = self.turn == Color.WHITE
        enemy = (bm | bk) if is_white else (wm | wk)
        if not enemy: return []
        
        captures: list[Move] = []
        empty_set: set[int] = set()
        for bb, fn in [((wm if is_white else bm), self._man_captures), ((wk if is_white else bk), lambda sq, e, c, o: self._king_captures(sq, e, c, set(), o))]:
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                fn(sq, enemy, empty_set, captures)
        return captures
    
    def _man_captures(self, sq: int, enemy: int, captured: set[int], out: list[Move]) -> None:
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        
        for d in range(4):
            mid, land = MOVE_TGT[sq][d], JUMP_TGT[sq][d]
            if mid == -1 or land == -1 or mid in captured: continue
            mid_bit = 1 << mid
            if not (enemy & mid_bit): continue
            land_bit = 1 << land
            if (all_p & land_bit) and not (src_bit & land_bit): continue
            
            cap_piece = 1 if bm & mid_bit else (2 if bk & mid_bit else (-1 if wm & mid_bit else -2))
            
            if wm & src_bit: self.white_men = (wm & ~src_bit) | land_bit
            else: self.black_men = (bm & ~src_bit) | land_bit
            self.white_men &= ~mid_bit; self.white_kings &= ~mid_bit
            self.black_men &= ~mid_bit; self.black_kings &= ~mid_bit
            
            sub: list[Move] = []
            captured.add(mid)
            self._man_captures(land, enemy, captured, sub)
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
            
            base = Move([sq, land], [mid], [cap_piece])
            out.extend([base + s for s in sub] if sub else [base])
    
    def _king_captures(self, sq: int, enemy: int, captured: set[int], forbidden: set[int], out: list[Move]) -> None:
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        local_best, max_len = [], 0
        
        for ray in KING_RAYS[sq]:
            for i, t in enumerate(ray):
                if t in forbidden: break
                t_bit = 1 << t
                if all_p & t_bit:
                    if t in captured: break
                    if enemy & t_bit:
                        cap_piece = 1 if bm & t_bit else (2 if bk & t_bit else (-1 if wm & t_bit else -2))
                        for land in ray[i + 1:]:
                            land_bit = 1 << land
                            if land in forbidden or (all_p & land_bit): break
                            
                            if wk & src_bit: self.white_kings = (wk & ~src_bit) | land_bit
                            else: self.black_kings = (bk & ~src_bit) | land_bit
                            self.white_men &= ~t_bit; self.white_kings &= ~t_bit
                            self.black_men &= ~t_bit; self.black_kings &= ~t_bit
                            
                            sub: list[Move] = []
                            captured.add(t); forbidden.add(t)
                            self._king_captures(land, enemy, captured, forbidden, sub)
                            captured.discard(t); forbidden.discard(t)
                            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
                            
                            base = Move([sq, land], [t], [cap_piece])
                            for m in ([base + s for s in sub] if sub else [base]):
                                if m._len > max_len: max_len, local_best = m._len, [m]
                                elif m._len == max_len: local_best.append(m)
                        break
                    else: break
        out.extend(local_best)
    
    @property
    def is_draw(self) -> bool:
        return self.is_25_moves_rule or self.is_threefold_repetition or self.is_5_moves_rule or self.is_16_moves_rule
    
    @property
    def is_25_moves_rule(self) -> bool:
        """Draw after 25 king moves (50 half-moves) without capture."""
        return self.halfmove_clock >= 50
    
    @property
    def is_16_moves_rule(self) -> bool:
        """Draw after 16 moves in specific endgames (≤4 pieces, ≥3 kings)."""
        if self.halfmove_clock < 32 or self._popcount(self._all()) > 4: return False
        return self._popcount(self.white_kings | self.black_kings) * 2 + self._popcount(self.white_men | self.black_men) >= 6
    
    @property
    def is_5_moves_rule(self) -> bool:
        """Draw after 5 moves in specific endgames (≤3 pieces, ≥2 kings)."""
        if self._popcount(self._all()) > 3: return False
        return self._popcount(self.white_kings | self.black_kings) * 2 + self._popcount(self.white_men | self.black_men) >= 5 and self.halfmove_clock >= 10
