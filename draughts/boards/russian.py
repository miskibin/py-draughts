"""
Russian Draughts - 8x8 board, flying kings, men capture backward, free capture choice.

Key differences from other variants:
- 8×8 board (32 squares, like American)
- Men move diagonally forward only
- Men capture both forward AND backward (unlike American)
- Flying kings (move any distance diagonally, like International)
- Free capture choice - NOT required to take maximum captures (unlike International)
- Mid-capture promotion: if a man reaches promotion rank during a capture, it
  immediately becomes a king and continues capturing as a king
- Mandatory captures (must capture if able, but can choose which sequence)
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
    """Build move tables for 8x8 board."""
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
    
    # Build rays for flying kings
    rays = []
    for sq in range(32):
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
    Russian Draughts.
    
    - 8×8 board, 32 squares
    - Flying kings (move any distance diagonally)
    - Men capture forward AND backward
    - Captures mandatory, but free choice (NOT max capture rule)
    - Mid-capture promotion (man becomes king during capture sequence)
    
    GameType 25 per PDN specification.
    """
    
    GAME_TYPE = 25
    VARIANT_NAME = "Russian draughts"
    STARTING_COLOR = Color.WHITE
    SQUARES_COUNT = 32
    PROMO_WHITE = ROW[0]
    PROMO_BLACK = ROW[7]
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    ROW_IDX = {v: v // 4 for v in range(32)}
    COL_IDX = {v: v % 8 for v in range(32)}
    
    # Algebraic notation for PDN parsing
    # fmt: off
    SQUARE_NAMES = ['b8', 'd8', 'f8', 'h8', 'a7', 'c7', 'e7', 'g7',
                    'b6', 'd6', 'f6', 'h6', 'a5', 'c5', 'e5', 'g5',
                    'b4', 'd4', 'f4', 'h4', 'a3', 'c3', 'e3', 'g3',
                    'b2', 'd2', 'f2', 'h2', 'a1', 'c1', 'e1', 'g1']
    # fmt: on
    
    def _init_default_position(self) -> None:
        self.black_men = (1 << 12) - 1
        self.black_kings = 0
        self.white_men = ((1 << 12) - 1) << 20
        self.white_kings = 0
    
    @property
    def legal_moves(self) -> list[Move]:
        """
        All legal moves for current player.
        In Russian draughts, captures are mandatory but player can choose ANY
        capture sequence (no maximum capture rule).
        """
        captures = self._gen_captures()
        if captures:
            return captures  # Must capture, but any sequence is valid
        return self._gen_simple()
    
    def _gen_simple(self) -> list[Move]:
        """Generate non-capture moves. Men move diagonally forward only."""
        moves = []
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        empty = ~(wm | wk | bm | bk) & MASK_32
        
        if self.turn == Color.WHITE:
            # White men move forward (toward row 0)
            men, even, odd = wm & ~ROW[0], wm & EVEN_ROWS & ~ROW[0], wm & ODD_ROWS
            for bb, shift in [((even & ~EVEN_RIGHT) >> 3, 3), (odd >> 4, 4), (even >> 4, 4), ((odd & ~ODD_LEFT) >> 5, 5)]:
                bb &= empty
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            # White kings - flying movement
            bb = wk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for ray in KING_RAYS[sq]:
                    for t in ray:
                        if empty & (1 << t): moves.append(Move([sq, t]))
                        else: break
        else:
            # Black men move forward (toward row 7)
            men, even, odd = bm & ~ROW[7], bm & EVEN_ROWS, bm & ODD_ROWS & ~ROW[7]
            for bb, shift in [((even & ~EVEN_RIGHT) << 5, -5), (odd << 4, -4), (even << 4, -4), ((odd & ~ODD_LEFT) << 3, -3)]:
                bb = bb & empty & MASK_32
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            # Black kings - flying movement
            bb = bk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for ray in KING_RAYS[sq]:
                    for t in ray:
                        if empty & (1 << t): moves.append(Move([sq, t]))
                        else: break
        return moves
    
    def _gen_captures(self) -> list[Move]:
        """Generate all capture sequences (no max-capture filtering in Russian)."""
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        is_white = self.turn == Color.WHITE
        enemy = (bm | bk) if is_white else (wm | wk)
        if not enemy: return []
        
        captures: list[Move] = []
        
        # Men captures (forward and backward, with mid-capture promotion)
        bb = wm if is_white else bm
        while bb:
            lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
            self._man_captures(sq, enemy, set(), captures, is_white)
        
        # King captures (flying)
        bb = wk if is_white else bk
        while bb:
            lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
            self._king_captures(sq, enemy, set(), set(), captures)
        
        return captures
    
    def _man_captures(self, sq: int, enemy: int, captured: set[int], out: list[Move], is_white: bool) -> None:
        """
        Generate man capture sequences.
        Men capture in ALL 4 diagonal directions (forward and backward).
        If man lands on promotion rank, it immediately becomes a king and
        continues capturing as a king (mid-capture promotion).
        """
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        promo_rank = self.PROMO_WHITE if is_white else self.PROMO_BLACK
        
        for d in range(4):  # Men capture in all 4 directions (unlike American)
            mid, land = MOVE_TGT[sq][d], JUMP_TGT[sq][d]
            if mid == -1 or land == -1 or mid in captured: continue
            mid_bit = 1 << mid
            if not (enemy & mid_bit): continue
            land_bit = 1 << land
            if (all_p & land_bit) and not (src_bit & land_bit): continue
            
            cap_piece = 1 if bm & mid_bit else (2 if bk & mid_bit else (-1 if wm & mid_bit else -2))
            
            # Move piece to landing square
            if wm & src_bit: self.white_men = (wm & ~src_bit) | land_bit
            else: self.black_men = (bm & ~src_bit) | land_bit
            # Remove captured piece
            self.white_men &= ~mid_bit; self.white_kings &= ~mid_bit
            self.black_men &= ~mid_bit; self.black_kings &= ~mid_bit
            
            sub: list[Move] = []
            captured.add(mid)
            
            # Check for mid-capture promotion
            if land_bit & promo_rank:
                # Man promotes to king and continues as king
                if is_white:
                    self.white_men &= ~land_bit
                    self.white_kings |= land_bit
                else:
                    self.black_men &= ~land_bit
                    self.black_kings |= land_bit
                # Continue capturing as a king (flying captures)
                self._king_captures(land, enemy, captured, set(), sub)
            else:
                # Continue as man
                self._man_captures(land, enemy, captured, sub, is_white)
            
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
            
            base = Move([sq, land], [mid], [cap_piece])
            # If promoted mid-capture, mark the move
            if land_bit & promo_rank:
                base.is_promotion = True
            out.extend([base + s for s in sub] if sub else [base])
    
    def _king_captures(self, sq: int, enemy: int, captured: set[int], forbidden: set[int], out: list[Move]) -> None:
        """
        Generate king capture sequences (flying king).
        Kings can jump any distance over an enemy piece to any empty square beyond.
        """
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        
        for ray in KING_RAYS[sq]:
            for i, t in enumerate(ray):
                if t in forbidden: break
                t_bit = 1 << t
                if all_p & t_bit:
                    if t in captured: break
                    if enemy & t_bit:
                        cap_piece = 1 if bm & t_bit else (2 if bk & t_bit else (-1 if wm & t_bit else -2))
                        
                        # Can land on any empty square beyond the captured piece
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
                            out.extend([base + s for s in sub] if sub else [base])
                        break
                    else: break
    
    @property
    def is_draw(self) -> bool:
        """
        Check if position is drawn per Russian draughts rules.
        - Threefold repetition
        - 3+ kings vs 1 king: 15 moves (30 half-moves) to win
        - 15 king-only moves without captures (30 half-moves)
        """
        return (
            self.is_threefold_repetition 
            or self.is_15_moves_rule 
            or self.is_3_kings_vs_1_rule
        )
    
    @property
    def is_15_moves_rule(self) -> bool:
        """
        Draw after 15 king moves without any captures or man moves.
        (30 half-moves of king-only non-capture moves)
        """
        return self.halfmove_clock >= 30
    
    @property
    def is_3_kings_vs_1_rule(self) -> bool:
        """
        Draw if a player has 3+ kings vs 1 king and fails to win within 15 moves.
        This checks if we're in a 3+ kings vs 1 king endgame.
        """
        white_kings = self._popcount(self.white_kings)
        black_kings = self._popcount(self.black_kings)
        white_men = self._popcount(self.white_men)
        black_men = self._popcount(self.black_men)
        
        # Only applies when there are no men left
        if white_men > 0 or black_men > 0:
            return False
        
        # Check for 3+ vs 1 king situation
        if (white_kings >= 3 and black_kings == 1) or (black_kings >= 3 and white_kings == 1):
            return self.halfmove_clock >= 30  # 15 moves = 30 half-moves
        
        return False

