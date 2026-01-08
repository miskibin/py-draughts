"""
Frisian Draughts - 10x10 board with orthogonal captures and value-based capture priority.

Key differences from International/Standard draughts:
- Captures can be made in 8 directions (diagonal + orthogonal)
- Capture priority: must take maximum VALUE (man=100, king=199)
- When equal value, king-initiated captures take priority
- Flying kings (move diagonal any distance, capture in 8 directions)
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

# Frisian capture values
MAN_VALUE = 100
KING_VALUE = 199


def _build_diagonal_tables():
    """Build diagonal move tables (same as standard)."""
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


def _sq_to_board_pos(sq: int) -> tuple[int, int]:
    """Convert 0-indexed square number to (row, board_col) position."""
    row = sq // 5
    col_in_row = sq % 5
    if row % 2 == 0:  # Even row - playable at odd board columns (1,3,5,7,9)
        board_col = col_in_row * 2 + 1
    else:  # Odd row - playable at even board columns (0,2,4,6,8)
        board_col = col_in_row * 2
    return row, board_col


def _board_pos_to_sq(row: int, board_col: int) -> int:
    """Convert (row, board_col) to 0-indexed square number, or -1 if invalid."""
    if row < 0 or row > 9:
        return -1
    if board_col < 0 or board_col > 9:
        return -1
    # Check if this is a playable square
    if row % 2 == 0:  # Even row - playable at odd columns
        if board_col % 2 != 1:
            return -1
        col_in_row = (board_col - 1) // 2
    else:  # Odd row - playable at even columns
        if board_col % 2 != 0:
            return -1
        col_in_row = board_col // 2
    return row * 5 + col_in_row


def _build_orthogonal_tables():
    """
    Build orthogonal move/capture tables for Frisian.
    Directions: 0=up, 1=right, 2=down, 3=left
    
    Note: Orthogonal movement is only for CAPTURING, not regular movement.
    
    In Frisian, orthogonal captures mean moving vertically or horizontally on the 
    actual 10x10 board. Due to the checkerboard pattern where only dark squares
    are playable, orthogonal neighbors are TWO board squares away.
    
    For vertical (up/down): Stay in same board column, move 2 rows
    For horizontal (left/right): Stay in same row, move 2 board columns
    """
    # Build orthogonal rays (for flying kings)
    ortho_rays = []
    for sq in range(50):
        row, board_col = _sq_to_board_pos(sq)
        
        # UP: same column, decreasing row
        up_ray = []
        r = row - 2
        while r >= 0:
            target = _board_pos_to_sq(r, board_col)
            if target != -1:
                up_ray.append(target)
            r -= 2
        
        # RIGHT: same row, increasing column
        right_ray = []
        c = board_col + 2
        while c <= 9:
            target = _board_pos_to_sq(row, c)
            if target != -1:
                right_ray.append(target)
            c += 2
        
        # DOWN: same column, increasing row
        down_ray = []
        r = row + 2
        while r <= 9:
            target = _board_pos_to_sq(r, board_col)
            if target != -1:
                down_ray.append(target)
            r += 2
        
        # LEFT: same row, decreasing column
        left_ray = []
        c = board_col - 2
        while c >= 0:
            target = _board_pos_to_sq(row, c)
            if target != -1:
                left_ray.append(target)
            c -= 2
        
        ortho_rays.append((tuple(up_ray), tuple(right_ray), tuple(down_ray), tuple(left_ray)))
    
    # Build short orthogonal jump table (for captures - target 1 away, land 2 away)
    ortho_jump = []
    for sq in range(50):
        row, board_col = _sq_to_board_pos(sq)
        targets = [-1, -1, -1, -1]  # up, right, down, left
        lands = [-1, -1, -1, -1]
        
        # UP: jump over piece 2 rows up, land 4 rows up
        target_up = _board_pos_to_sq(row - 2, board_col)
        land_up = _board_pos_to_sq(row - 4, board_col)
        if target_up != -1 and land_up != -1:
            targets[0] = target_up
            lands[0] = land_up
        
        # RIGHT: jump over piece 2 cols right, land 4 cols right
        target_right = _board_pos_to_sq(row, board_col + 2)
        land_right = _board_pos_to_sq(row, board_col + 4)
        if target_right != -1 and land_right != -1:
            targets[1] = target_right
            lands[1] = land_right
        
        # DOWN: jump over piece 2 rows down, land 4 rows down
        target_down = _board_pos_to_sq(row + 2, board_col)
        land_down = _board_pos_to_sq(row + 4, board_col)
        if target_down != -1 and land_down != -1:
            targets[2] = target_down
            lands[2] = land_down
        
        # LEFT: jump over piece 2 cols left, land 4 cols left
        target_left = _board_pos_to_sq(row, board_col - 2)
        land_left = _board_pos_to_sq(row, board_col - 4)
        if target_left != -1 and land_left != -1:
            targets[3] = target_left
            lands[3] = land_left
        
        ortho_jump.append((tuple(targets), tuple(lands)))
    
    return tuple(ortho_rays), tuple(ortho_jump)


DIAG_MOVE_TGT, DIAG_JUMP_TGT, KING_DIAG_RAYS = _build_diagonal_tables()
ORTHO_RAYS, ORTHO_JUMP = _build_orthogonal_tables()


class Board(BaseBoard):
    """
    **Board for Frisian draughts.**

    Game rules:

    - Board size: 10×10

    - Besides capturing diagonally, one can also capture horizontally and vertically.
        Every piece can thus capture in eight directions.

    - If a king and a man can play a capture sequence of equal value,
        it is always forced to play with the king.

    - Capture priority: must take the maximum VALUE sequence.
        - Man = 100 points
        - King = 199 points (so two men < one king)

    - If a player has one or more kings on the board but also has one or more men left,
        it is not allowed to play more than three non-capturing moves in a row with the same king.
        (This rule is tracked but not currently enforced)

    **Winning and drawing**

    - When one player has two kings and the other player has one king,
        the game is drawn after both players made 7 moves.
    - When both players have one king left, the game is drawn after both players made 2 moves.
    """

    GAME_TYPE = 40
    VARIANT_NAME = "Frisian"
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
            # Filter by maximum value
            max_val = max(m._value for m in captures)
            max_value_captures = [m for m in captures if m._value == max_val]
            
            # Among equal value, prefer king-initiated captures
            king_captures = [m for m in max_value_captures if m._is_king_move]
            if king_captures:
                return king_captures
            return max_value_captures
        return self._gen_simple()
    
    def _gen_simple(self) -> list[Move]:
        """Generate simple (non-capture) moves. Men move diagonally forward only."""
        moves = []
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        empty = ~(wm | wk | bm | bk) & MASK_50
        
        if self.turn == Color.WHITE:
            # White men move forward (up the board = lower row numbers)
            men, even, odd = wm & ~ROW[0], wm & EVEN_ROWS & ~ROW[0], wm & ODD_ROWS
            for bb, shift in [((even & ~EVEN_RIGHT) >> 4, 4), (odd >> 5, 5), (even >> 5, 5), ((odd & ~ODD_LEFT) >> 6, 6)]:
                bb &= empty
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            # White kings move any distance diagonally
            bb = wk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for ray in KING_DIAG_RAYS[sq]:
                    for t in ray:
                        if empty & (1 << t): moves.append(Move([sq, t]))
                        else: break
        else:
            # Black men move forward (down the board = higher row numbers)
            men, even, odd = bm & ~ROW[9], bm & EVEN_ROWS, bm & ODD_ROWS & ~ROW[9]
            for bb, shift in [((even & ~EVEN_RIGHT) << 6, -6), (odd << 5, -5), (even << 5, -5), ((odd & ~ODD_LEFT) << 4, -4)]:
                bb = bb & empty & MASK_50
                while bb:
                    lsb = bb & -bb; t = lsb.bit_length() - 1; bb ^= lsb
                    moves.append(Move([t + shift, t]))
            # Black kings move any distance diagonally
            bb = bk
            while bb:
                lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
                for ray in KING_DIAG_RAYS[sq]:
                    for t in ray:
                        if empty & (1 << t): moves.append(Move([sq, t]))
                        else: break
        return moves
    
    def _gen_captures(self) -> list[Move]:
        """Generate all capture sequences with value information."""
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        is_white = self.turn == Color.WHITE
        enemy = (bm | bk) if is_white else (wm | wk)
        if not enemy: return []
        
        captures: list[Move] = []
        
        # Men captures
        bb = wm if is_white else bm
        while bb:
            lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
            self._man_captures(sq, enemy, set(), set(), captures, False)
        
        # King captures
        bb = wk if is_white else bk
        while bb:
            lsb = bb & -bb; sq = lsb.bit_length() - 1; bb ^= lsb
            self._king_captures(sq, enemy, set(), set(), captures, True)
        
        return captures
    
    def _man_captures(self, sq: int, enemy: int, captured: set[int], forbidden: set[int], out: list[Move], is_king: bool) -> None:
        """
        Generate man capture sequences (8 directions).
        Men can capture in all 8 directions but only JUMP 1 square over opponent.
        """
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        found_any = False
        
        # Diagonal captures (4 directions)
        for d in range(4):
            mid, land = DIAG_MOVE_TGT[sq][d], DIAG_JUMP_TGT[sq][d]
            if mid == -1 or land == -1 or mid in captured: continue
            mid_bit = 1 << mid
            if not (enemy & mid_bit): continue
            land_bit = 1 << land
            if (all_p & land_bit) and not (src_bit & land_bit): continue
            if land in forbidden: continue
            
            cap_piece = 1 if bm & mid_bit else (2 if bk & mid_bit else (-1 if wm & mid_bit else -2))
            cap_value = KING_VALUE if abs(cap_piece) == 2 else MAN_VALUE
            
            # Make the capture
            if wm & src_bit: self.white_men = (wm & ~src_bit) | land_bit
            else: self.black_men = (bm & ~src_bit) | land_bit
            self.white_men &= ~mid_bit; self.white_kings &= ~mid_bit
            self.black_men &= ~mid_bit; self.black_kings &= ~mid_bit
            
            sub: list[Move] = []
            captured.add(mid)
            self._man_captures(land, enemy, captured, forbidden, sub, is_king)
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
            
            base = Move([sq, land], [mid], [cap_piece])
            base._value = cap_value
            base._is_king_move = is_king
            
            if sub:
                for s in sub:
                    combined = base + s
                    combined._value = cap_value + s._value
                    combined._is_king_move = is_king
                    out.append(combined)
            else:
                out.append(base)
            found_any = True
        
        # Orthogonal captures (4 directions: up, right, down, left)
        ortho_targets, ortho_lands = ORTHO_JUMP[sq]
        for d in range(4):
            mid, land = ortho_targets[d], ortho_lands[d]
            if mid == -1 or land == -1 or mid in captured: continue
            mid_bit = 1 << mid
            if not (enemy & mid_bit): continue
            land_bit = 1 << land
            if (all_p & land_bit) and not (src_bit & land_bit): continue
            if land in forbidden: continue
            
            cap_piece = 1 if bm & mid_bit else (2 if bk & mid_bit else (-1 if wm & mid_bit else -2))
            cap_value = KING_VALUE if abs(cap_piece) == 2 else MAN_VALUE
            
            # Make the capture
            if wm & src_bit: self.white_men = (wm & ~src_bit) | land_bit
            else: self.black_men = (bm & ~src_bit) | land_bit
            self.white_men &= ~mid_bit; self.white_kings &= ~mid_bit
            self.black_men &= ~mid_bit; self.black_kings &= ~mid_bit
            
            sub: list[Move] = []
            captured.add(mid)
            self._man_captures(land, enemy, captured, forbidden, sub, is_king)
            captured.discard(mid)
            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
            
            base = Move([sq, land], [mid], [cap_piece])
            base._value = cap_value
            base._is_king_move = is_king
            
            if sub:
                for s in sub:
                    combined = base + s
                    combined._value = cap_value + s._value
                    combined._is_king_move = is_king
                    out.append(combined)
            else:
                out.append(base)
            found_any = True
    
    def _king_captures(self, sq: int, enemy: int, captured: set[int], forbidden: set[int], out: list[Move], is_king: bool) -> None:
        """
        Generate king capture sequences (8 directions).
        Kings fly diagonally but capture by jumping exactly 1 square over opponent.
        In Frisian, kings can also capture orthogonally.
        """
        wm, wk, bm, bk = self.white_men, self.white_kings, self.black_men, self.black_kings
        all_p, src_bit = wm | wk | bm | bk, 1 << sq
        local_best: list[Move] = []
        max_val = 0
        
        # Diagonal captures (flying king - can land anywhere beyond captured piece)
        for ray in KING_DIAG_RAYS[sq]:
            for i, t in enumerate(ray):
                if t in forbidden: break
                t_bit = 1 << t
                if all_p & t_bit:
                    if t in captured: break
                    if enemy & t_bit:
                        cap_piece = 1 if bm & t_bit else (2 if bk & t_bit else (-1 if wm & t_bit else -2))
                        cap_value = KING_VALUE if abs(cap_piece) == 2 else MAN_VALUE
                        
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
                            self._king_captures(land, enemy, captured, forbidden, sub, is_king)
                            captured.discard(t); forbidden.discard(t)
                            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
                            
                            base = Move([sq, land], [t], [cap_piece])
                            base._value = cap_value
                            base._is_king_move = is_king
                            
                            for m in ([self._combine_capture(base, s) for s in sub] if sub else [base]):
                                if m._value > max_val:
                                    max_val, local_best = m._value, [m]
                                elif m._value == max_val:
                                    local_best.append(m)
                        break
                    else: break
        
        # Orthogonal captures (flying king - can land anywhere beyond captured piece)
        for ray in ORTHO_RAYS[sq]:
            for i, t in enumerate(ray):
                if t in forbidden: break
                t_bit = 1 << t
                if all_p & t_bit:
                    if t in captured: break
                    if enemy & t_bit:
                        cap_piece = 1 if bm & t_bit else (2 if bk & t_bit else (-1 if wm & t_bit else -2))
                        cap_value = KING_VALUE if abs(cap_piece) == 2 else MAN_VALUE
                        
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
                            self._king_captures(land, enemy, captured, forbidden, sub, is_king)
                            captured.discard(t); forbidden.discard(t)
                            self.white_men, self.white_kings, self.black_men, self.black_kings = wm, wk, bm, bk
                            
                            base = Move([sq, land], [t], [cap_piece])
                            base._value = cap_value
                            base._is_king_move = is_king
                            
                            for m in ([self._combine_capture(base, s) for s in sub] if sub else [base]):
                                if m._value > max_val:
                                    max_val, local_best = m._value, [m]
                                elif m._value == max_val:
                                    local_best.append(m)
                        break
                    else: break
        
        out.extend(local_best)
    
    def _combine_capture(self, base: Move, sub: Move) -> Move:
        """Combine two capture moves preserving Frisian value attributes."""
        combined = base + sub
        combined._value = base._value + sub._value
        combined._is_king_move = base._is_king_move
        return combined

    @property
    def is_draw(self) -> bool:
        return (
            self.is_threefold_repetition
            or self.is_5_moves_rule
            or self.is_16_moves_rule
            or self.is_25_moves_rule
        )

    @property
    def is_25_moves_rule(self) -> bool:
        """Draw after 25 king moves (50 half-moves) without capture."""
        return self.halfmove_clock >= 50

    @property
    def is_16_moves_rule(self) -> bool:
        """
        Draw after 16 moves in specific endgames.
        Frisian: 2 kings vs 1 king = draw after 7 moves each (14 half-moves).
        """
        if self.halfmove_clock < 14:
            return False
        # Check for 2 kings vs 1 king (total 3 kings, no men)
        king_count = self._popcount(self.white_kings | self.black_kings)
        men_count = self._popcount(self.white_men | self.black_men)
        if men_count == 0 and king_count == 3:
            return self.halfmove_clock >= 14
        return False

    @property
    def is_5_moves_rule(self) -> bool:
        """
        Draw in 1 king vs 1 king endgame.
        Frisian: 1 king vs 1 king = draw after 2 moves each (4 half-moves).
        """
        king_count = self._popcount(self.white_kings | self.black_kings)
        men_count = self._popcount(self.white_men | self.black_men)
        if men_count == 0 and king_count == 2:
            # 1 king each
            if self._popcount(self.white_kings) == 1 and self._popcount(self.black_kings) == 1:
                return self.halfmove_clock >= 4
        return False
