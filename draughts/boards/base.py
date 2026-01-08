"""Abstract base class for draughts boards using bitboard representation."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Generator, Literal, Optional

import numpy as np
from loguru import logger

from draughts.models import Color, Figure, FIGURE_REPR
from draughts.move import Move


class BaseBoard(ABC):
    """
    Abstract base for bitboard-based draughts boards.
    
    State stored as 4 ints: ``white_men``, ``white_kings``, ``black_men``, ``black_kings``.
    
    Subclasses must define: ``legal_moves``, ``is_draw``, ``_init_default_position``,
    ``GAME_TYPE``, ``VARIANT_NAME``, ``SQUARES_COUNT``, ``PROMO_WHITE``, ``PROMO_BLACK``.
    
    Optionally define ``SQUARE_NAMES`` for algebraic notation support (e.g., ['b8', 'd8', ...]).
    """
    
    GAME_TYPE: int = -1
    VARIANT_NAME: str = "Abstract"
    STARTING_COLOR: Color = Color.WHITE
    SQUARES_COUNT: int = 50
    PROMO_WHITE: int = 0
    PROMO_BLACK: int = 0
    
    ROW_IDX: dict = {}
    COL_IDX: dict = {}
    STARTING_POSITION: np.ndarray = np.array([], dtype=np.int8)
    
    # Algebraic square names for PDN parsing (e.g., ['b8', 'd8', ...] for 8x8)
    # Override in subclasses that use algebraic notation
    SQUARE_NAMES: list[str] = []
    
    __slots__ = ('white_men', 'white_kings', 'black_men', 'black_kings',
                 'turn', 'halfmove_clock', '_moves_stack', 'shape')
    
    def __init__(self, starting_position: Optional[np.ndarray] = None, turn: Optional[Color] = None) -> None:
        size = int(np.sqrt(self.SQUARES_COUNT * 2))
        self.shape = (size, size)
        self.turn = turn if turn is not None else self.STARTING_COLOR
        self.halfmove_clock = 0
        self._moves_stack: list[Move] = []
        
        if starting_position is not None:
            self._from_array(starting_position)
        else:
            self._init_default_position()
        logger.info(f"Board initialized with shape {self.shape}.")
    
    @abstractmethod
    def _init_default_position(self) -> None:
        """Set bitboards to starting position."""
        pass
    
    def _from_array(self, arr: np.ndarray) -> None:
        """Load position from numpy array (1=BM, 2=BK, -1=WM, -2=WK)."""
        self.white_men = self.white_kings = self.black_men = self.black_kings = 0
        for sq, val in enumerate(arr):
            bit = 1 << sq
            if val == 1: self.black_men |= bit
            elif val == 2: self.black_kings |= bit
            elif val == -1: self.white_men |= bit
            elif val == -2: self.white_kings |= bit
    
    def _all(self) -> int:
        return self.white_men | self.white_kings | self.black_men | self.black_kings
    
    def _empty(self) -> int:
        return ~self._all() & ((1 << self.SQUARES_COUNT) - 1)
    
    def _enemy(self) -> int:
        return (self.black_men | self.black_kings) if self.turn == Color.WHITE else (self.white_men | self.white_kings)
    
    def _get(self, sq: int) -> int:
        """Get piece at square: -2=WK, -1=WM, 0=empty, 1=BM, 2=BK."""
        bit = 1 << sq
        if self.white_men & bit: return -1
        if self.white_kings & bit: return -2
        if self.black_men & bit: return 1
        if self.black_kings & bit: return 2
        return 0
    
    def _set(self, sq: int, piece: int) -> None:
        """Set piece at square."""
        bit, inv = 1 << sq, ~(1 << sq)
        self.white_men &= inv; self.white_kings &= inv
        self.black_men &= inv; self.black_kings &= inv
        if piece == -1: self.white_men |= bit
        elif piece == -2: self.white_kings |= bit
        elif piece == 1: self.black_men |= bit
        elif piece == 2: self.black_kings |= bit
    
    @staticmethod
    def _popcount(bb: int) -> int:
        return bin(bb).count('1')
    
    @property
    @abstractmethod
    def legal_moves(self) -> list[Move]:
        """Return all legal moves for current player."""
        pass
    
    @property
    @abstractmethod
    def is_draw(self) -> bool:
        """Check if position is drawn."""
        pass
    
    def push(self, move: Move, is_finished: bool = True) -> None:
        """Apply move. Set ``is_finished=False`` during move generation."""
        move.halfmove_clock = self.halfmove_clock
        src, tgt = move.square_list[0], move.square_list[-1]
        piece = self._get(src)
        src_bit, tgt_bit = 1 << src, 1 << tgt
        
        # Move piece
        if piece == -1: self.white_men = (self.white_men & ~src_bit) | tgt_bit
        elif piece == -2: self.white_kings = (self.white_kings & ~src_bit) | tgt_bit
        elif piece == 1: self.black_men = (self.black_men & ~src_bit) | tgt_bit
        else: self.black_kings = (self.black_kings & ~src_bit) | tgt_bit
        
        if is_finished:
            # Promotion
            if piece == -1 and (self.PROMO_WHITE & tgt_bit):
                self.white_men &= ~tgt_bit; self.white_kings |= tgt_bit; move.is_promotion = True
            elif piece == 1 and (self.PROMO_BLACK & tgt_bit):
                self.black_men &= ~tgt_bit; self.black_kings |= tgt_bit; move.is_promotion = True
            # Halfmove clock
            elif abs(piece) == 2 and not move.captured_list: self.halfmove_clock += 1
            else: self.halfmove_clock = 0
        
        # Remove captures
        for cap_sq in move.captured_list:
            if cap_sq != tgt:
                bit = ~(1 << cap_sq)
                self.white_men &= bit; self.white_kings &= bit
                self.black_men &= bit; self.black_kings &= bit
        
        self._moves_stack.append(move)
        if is_finished:
            self.turn = Color.BLACK if self.turn == Color.WHITE else Color.WHITE
    
    def pop(self, is_finished: bool = True) -> Move:
        """Undo last move."""
        move = self._moves_stack.pop()
        src, tgt = move.square_list[0], move.square_list[-1]
        piece = self._get(tgt)
        if move.is_promotion: piece //= 2
        
        self._set(tgt, 0)
        self._set(src, piece)
        for cap_sq, cap_piece in zip(move.captured_list, move.captured_entities):
            self._set(cap_sq, cap_piece)
        
        self.halfmove_clock = move.halfmove_clock
        if is_finished:
            self.turn = Color.BLACK if self.turn == Color.WHITE else Color.WHITE
        return move
    
    def push_uci(self, str_move: str) -> None:
        """Push move from UCI string (e.g. ``'31-27'`` or ``'26x17'``)."""
        try:
            move = Move.from_uci(str_move, self.legal_moves)
        except ValueError as e:
            logger.error(f"{e}\n{self}")
            raise
        self.push(move)
    
    @property
    def is_threefold_repetition(self) -> bool:
        if len(self._moves_stack) >= 9:
            s = self._moves_stack
            if s[-1].square_list == s[-5].square_list == s[-9].square_list:
                return True
        return False
    
    @property
    def game_over(self) -> bool:
        return self.is_draw or not self.legal_moves
    
    @property
    def result(self) -> Literal["1/2-1/2", "1-0", "0-1", "-"]:
        """Get result: ``'1-0'``, ``'0-1'``, ``'1/2-1/2'``, or ``'-'`` if ongoing."""
        if self.is_draw: return "1/2-1/2"
        if self.game_over: return "0-1" if self.turn == Color.WHITE else "1-0"
        return "-"
    
    @staticmethod
    def is_capture(move: Move) -> bool:
        return bool(move.captured_list)
    
    @property
    def fen(self) -> str:
        """FEN string, e.g. ``[FEN "W:W:W31,32:B1,2"]``."""
        turn_s = "W" if self.turn == Color.WHITE else "B"
        white_sq, black_sq = [], []
        for sq in range(self.SQUARES_COUNT):
            bit = 1 << sq
            if self.white_men & bit: white_sq.append(str(sq + 1))
            elif self.white_kings & bit: white_sq.append(f"K{sq + 1}")
            if self.black_men & bit: black_sq.append(str(sq + 1))
            elif self.black_kings & bit: black_sq.append(f"K{sq + 1}")
        return f'[FEN "W:{turn_s}:W{",".join(white_sq)}:B{",".join(black_sq)}"]'
    
    @classmethod
    def from_fen(cls, fen: str) -> BaseBoard:
        """Create board from FEN string."""
        logger.debug(f"Initializing from FEN: {fen}")
        fen = fen.upper()
        fen = re.sub(r"(G[0-9]+|P[0-9]+)(,|)", "", fen)
        prefix = re.search(r"[WB]:[WB]:[WB]", fen)
        if prefix: fen = fen.replace(prefix.group(0), prefix.group(0)[2:])
        
        turn_m, white_m, black_m = re.search(r"[WB]:", fen), re.search(r"W[0-9K,]+", fen), re.search(r"B[0-9K,]+", fen)
        if not turn_m or not white_m or not black_m:
            raise ValueError(f"Invalid FEN: {fen}")
        
        position = np.zeros(cls.SQUARES_COUNT, dtype=np.int8)
        for sq_str in white_m.group(0)[1:].split(","):
            if sq_str.isdigit(): position[int(sq_str) - 1] = -1
            elif sq_str.startswith("K"): position[int(sq_str[1:]) - 1] = -2
        for sq_str in black_m.group(0)[1:].split(","):
            if sq_str.isdigit(): position[int(sq_str) - 1] = 1
            elif sq_str.startswith("K"): position[int(sq_str[1:]) - 1] = 2
        
        return cls(position, Color.WHITE if turn_m.group(0)[0] == "W" else Color.BLACK)
    
    @property
    def pdn(self) -> str:
        """PDN game record string."""
        header = f'[GameType "{self.GAME_TYPE}"]\n[Variant "{self.VARIANT_NAME}"]\n[Result "{self.result}"]\n'
        moves: list[list[str]] = []
        for i, m in enumerate(self._moves_stack):
            if i % 2 == 0: moves.append([str(i // 2 + 1), str(m)])
            else: moves[-1].append(str(m))
        moves_str = " ".join(f"{m[0]}. {' '.join(m[1:])}" for m in moves)
        return header + moves_str + ("" if self.result == "-" else f" {self.result}")
    
    @classmethod
    def from_pdn(cls, pdn: str) -> BaseBoard:
        """
        Create board from PDN string.
        
        Supports both numeric (e.g., '33-28') and algebraic (e.g., 'c3-d4') notation.
        Handles multi-captures split across entries (e.g., 'e5xc3' then 'c3xa1').
        """
        board = cls()
        alg_to_idx = {name: idx for idx, name in enumerate(cls.SQUARE_NAMES)} if cls.SQUARE_NAMES else {}
        
        # Extract moves - try algebraic first, fall back to numeric
        alg_moves = re.findall(r'\b([a-h]\d[-x][a-h]\d)\b', pdn)
        if alg_moves and alg_to_idx:
            moves = [board._alg_to_uci(m, alg_to_idx) for m in alg_moves]
        else:
            results = {"2-0", "0-2", "1-1", "1-0", "0-1", "1/2-1/2"}
            moves = [m for m in re.findall(r'\b(\d+[-x]\d+(?:[-x]\d+)*)\b', pdn) if m not in results]
        
        # Parse moves, handling split multi-captures
        i, chain_start = 0, None
        while i < len(moves):
            move, is_cap = moves[i], 'x' in moves[i]
            start, end = int(move.split('x' if is_cap else '-')[0]), int(move.split('x' if is_cap else '-')[-1])
            
            if not is_cap:
                board.push_uci(move)
                chain_start = None
            else:
                src = chain_start or start
                cap = next((m for m in board.legal_moves if m.captured_list and m.square_list[0] == src - 1 and (end - 1) in m.square_list), None)
                if not cap:
                    raise ValueError(f"No legal capture for {move}")
                
                # Check if next move continues this capture chain
                if i + 1 < len(moves) and 'x' in moves[i + 1]:
                    nxt = moves[i + 1]
                    nxt_start = int(nxt.split('x')[0])
                    if nxt_start == end and (end - 1) in cap.square_list[1:-1]:
                        chain_start = src
                        i += 1
                        continue
                
                board.push(cap)
                chain_start = None
            i += 1
        
        return board
    
    @staticmethod
    def _alg_to_uci(move: str, mapping: dict[str, int]) -> str:
        """Convert algebraic notation (c3-d4) to UCI (22-18)."""
        sep = 'x' if 'x' in move else '-'
        parts = move.lower().split(sep)
        return f"{mapping[parts[0]] + 1}{sep}{mapping[parts[1]] + 1}"
    
    @property
    def position(self) -> np.ndarray:
        """Board as numpy array (1=BM, 2=BK, -1=WM, -2=WK, 0=empty)."""
        arr = np.zeros(self.SQUARES_COUNT, dtype=np.int8)
        for sq in range(self.SQUARES_COUNT): arr[sq] = self._get(sq)
        return arr
    
    @property
    def _pos(self) -> np.ndarray:
        return self.position
    
    @property
    def friendly_form(self) -> np.ndarray:
        """Board as n×n array (includes non-playable squares as 0)."""
        pos, n = self.position, self.shape[0] // 2
        new_pos = [0]
        for idx, sq in enumerate(pos):
            new_pos.extend([0] * (idx % n != 0))
            new_pos.extend([0, 0] * (idx % self.shape[0] == 0 and idx != 0))
            new_pos.append(sq)
        new_pos.append(0)
        return np.array(new_pos)
    
    def __repr__(self) -> str:
        pos, n = self.friendly_form, self.shape[0]
        return "".join(f" {FIGURE_REPR[pos[i * n + j]]}" + ("\n" if j == n - 1 else "") for i in range(n) for j in range(n))
    
    def __str__(self) -> str:
        n = self.shape[0]
        lines = []
        for i, line in enumerate(repr(self).strip().split('\n')):
            sq = iter(range(i * n // 2 + 1, (i + 1) * n // 2 + 1))
            nums = ' '.join(f"{next(sq):2d}" if (i + j) % 2 else "." for j in range(n))
            lines.append(f"{line}     {nums}")
        return '\n'.join(lines)
    
    def __iter__(self) -> Generator[int, None, None]:
        for sq in range(self.SQUARES_COUNT): yield self._get(sq)
    
    def __getitem__(self, key: int) -> int:
        return self._get(key)
