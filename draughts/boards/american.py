"""
American Checkers - 8x8 board, short kings, men capture forward only.
"""
from __future__ import annotations

import numpy as np

from draughts.boards.base import BaseBoard
from draughts.models import Color
from draughts.move import Move

# fmt: off
SQUARES = [B8, D8, F8, H8, A7, C7, E7, G7, B6, D6, F6, H6, A5, C5, E5, G5,
           B4, D4, F4, H4, A3, C3, E3, G3, B2, D2, F2, H2, A1, C1, E1, G1] = range(32)
# fmt: on

MASK_32 = (1 << 32) - 1
ROW = [((1 << 4) - 1) << (i * 4) for i in range(8)]
EVEN_ROWS = ROW[0] | ROW[2] | ROW[4] | ROW[6]
ODD_ROWS = ROW[1] | ROW[3] | ROW[5] | ROW[7]
EVEN_RIGHT = sum(1 << (i * 8 + 3) for i in range(4))
ODD_LEFT = sum(1 << (i * 8 + 4) for i in range(4))


def _build_tables():
    EVEN_SHIFTS, ODD_SHIFTS = (-3, -4, 5, 4), (-4, -5, 4, 3)
    move_tgt = []
    for sq in range(32):
        row, col = sq // 4, sq % 4
        is_even = row % 2 == 0
        shifts = EVEN_SHIFTS if is_even else ODD_SHIFTS
        blocks = [col == 3, False, col == 3, False] if is_even else [False, col == 0, False, col == 0]
        targets = [-1, -1, -1, -1]
        for d in range(4):
            if not blocks[d]:
                t = sq + shifts[d]
                if 0 <= t < 32 and abs(t // 4 - row) == 1:
                    targets[d] = t
        move_tgt.append(tuple(targets))
    
    jump_tgt = [tuple(move_tgt[move_tgt[sq][d]][d] if move_tgt[sq][d] != -1 and move_tgt[move_tgt[sq][d]][d] != -1 else -1 for d in range(4)) for sq in range(32)]
    return tuple(move_tgt), tuple(jump_tgt)

MOVE_TGT, JUMP_TGT = _build_tables()


class Board(BaseBoard):
    """
    American Checkers.
    
    - 8×8 board, 32 squares
    - Short kings (move 1 square)
    - Men capture forward only
    - Captures optional
    """
    
    GAME_TYPE = 23
    VARIANT_NAME = "American checkers"
    STARTING_COLOR = Color.WHITE
    SQUARES_COUNT = 32
    PROMO_WHITE = ROW[0]
    PROMO_BLACK = ROW[7]
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    ROW_IDX = {v: v // 4 for v in range(32)}
    COL_IDX = {v: v % 8 for v in range(32)}
    
    def _init_default_position(self) -> None:
        self.black_men = (1 << 12) - 1
        self.black_kings = 0
        self.white_men = ((1 << 12) - 1) << 20
        self.white_kings = 0
    
    @property
    def legal_moves(self) -> list[Move]:
        """All legal moves. Captures are NOT mandatory in American checkers."""
        return self._gen_simple() + self._gen_captures()
    
    def _gen_simple(self) -> list[Move]:
        moves = []
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        empty = ~(wm | wk | bm | bk) & MASK_32
        
        if self.turn == Color.WHITE:
            men, even, odd = wm & ~ROW[0], wm & EVEN_ROWS & ~ROW[0], wm & ODD_ROWS
            for bb, shift in [((even & ~EVEN_RIGHT) >> 3, 3), (odd >> 4, 4), (even >> 4, 4), ((odd & ~ODD_LEFT) >> 5, 5)]:
                bb &= empty
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            bb = wk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for d in range(4):
                    t = MOVE_TGT[sq][d]
                    if t != -1 and (empty & (1 << t)): moves.append(Move([sq, t]))
        else:
            men, even, odd = bm & ~ROW[7], bm & EVEN_ROWS, bm & ODD_ROWS & ~ROW[7]
            for bb, shift in [((even & ~EVEN_RIGHT) << 5, -5), (odd << 4, -4), (even << 4, -4), ((odd & ~ODD_LEFT) << 3, -3)]:
                bb = bb & empty & MASK_32
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            bb = bk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for d in range(4):
                    t = MOVE_TGT[sq][d]
                    if t != -1 and (empty & (1 << t)): moves.append(Move([sq, t]))
        return moves
    
    def _gen_captures(self) -> list[Move]:
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        is_white = self.turn == Color.WHITE
        enemy = (bm | bk) if is_white else (wm | wk)
        if not enemy: return []
        
        captures: list[Move] = []
        bb = wm if is_white else bm
        while bb:
            lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
            self._man_captures(sq, enemy, set(), captures, is_white)
        bb = wk if is_white else bk
        while bb:
            lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
            self._king_captures(sq, enemy, set(), captures)
        return captures
    
    def _man_captures(self, sq: int, enemy: int, captured: set[int], out: list[Move], is_white: bool) -> None:
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        
        for d in ((0, 1) if is_white else (2, 3)):  # Men capture forward only
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
            self._man_captures(land, enemy, captured, sub, is_white)
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
            
            base = Move([sq, land], [mid], [cap_piece])
            out.extend([base + s for s in sub] if sub else [base])
    
    def _king_captures(self, sq: int, enemy: int, captured: set[int], out: list[Move]) -> None:
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        
        for d in range(4):  # Kings capture in all directions
            mid, land = MOVE_TGT[sq][d], JUMP_TGT[sq][d]
            if mid == -1 or land == -1 or mid in captured: continue
            mid_bit = 1 << mid
            if not (enemy & mid_bit): continue
            land_bit = 1 << land
            if (all_p & land_bit) and not (src_bit & land_bit): continue
            
            cap_piece = 1 if bm & mid_bit else (2 if bk & mid_bit else (-1 if wm & mid_bit else -2))
            
            if wk & src_bit: self.white_kings = (wk & ~src_bit) | land_bit
            else: self.black_kings = (bk & ~src_bit) | land_bit
            self.white_men &= ~mid_bit; self.white_kings &= ~mid_bit
            self.black_men &= ~mid_bit; self.black_kings &= ~mid_bit
            
            sub: list[Move] = []
            captured.add(mid)
            self._king_captures(land, enemy, captured, sub)
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
            
            base = Move([sq, land], [mid], [cap_piece])
            out.extend([base + s for s in sub] if sub else [base])
    
    @property
    def is_draw(self) -> bool:
        return self.is_threefold_repetition
