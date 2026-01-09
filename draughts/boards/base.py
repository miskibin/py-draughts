"""Abstract base class for draughts boards using bitboard representation."""
from __future__ import annotations

import copy
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator, Literal, Optional

import numpy as np
from loguru import logger

from draughts.models import Color, Figure, FIGURE_REPR
from draughts.move import Move


@dataclass(frozen=True, slots=True)
class BoardFeatures:
    """
    Extracted features from a board position for AI/ML use.

    All counts and metrics are computed on-demand and returned as
    immutable data. This does not store any references to the board.

    Attributes:
        white_men: Number of white men on the board.
        white_kings: Number of white kings on the board.
        black_men: Number of black men on the board.
        black_kings: Number of black kings on the board.
        turn: 1 if white to move, -1 if black to move.
        mobility: Number of legal moves for the side to move.
        material_balance: (white_men + 2*white_kings) - (black_men + 2*black_kings).
        phase: Game phase: 'opening', 'midgame', or 'endgame'.
    """

    white_men: int
    white_kings: int
    black_men: int
    black_kings: int
    turn: int
    mobility: int
    material_balance: float
    phase: str


class BaseBoard(ABC):
    """
    Abstract base class for all draughts board variants.

    Uses bitboard representation for efficient move generation. Board state is stored
    as four integers: ``white_men``, ``white_kings``, ``black_men``, ``black_kings``.

    Attributes:
        turn: Current side to move (:class:`Color.WHITE` or :class:`Color.BLACK`).
        halfmove_clock: Moves since last capture or man move (for draw detection).
        shape: Board dimensions as tuple, e.g. ``(10, 10)`` for standard.

    Example:
        >>> from draughts import Board
        >>> board = Board()
        >>> board.push_uci("31-27")
        >>> print(board.turn)
        Color.BLACK
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
    SQUARE_NAMES: list[str] = []

    __slots__ = ('white_men', 'white_kings', 'black_men', 'black_kings',
                 'turn', 'halfmove_clock', '_moves_stack', 'shape')

    def __init__(self, starting_position: Optional[np.ndarray] = None, turn: Optional[Color] = None) -> None:
        """
        Initialize a new board.

        Args:
            starting_position: Optional numpy array with piece positions.
                Values: 1=black man, 2=black king, -1=white man, -2=white king, 0=empty.
                If None, uses the standard starting position for the variant.
            turn: Side to move first. Defaults to ``Color.WHITE``.

        Example:
            >>> board = Board()  # Standard starting position
            >>> board = Board.from_fen("W:WK10:BK35")  # Custom position
        """
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
        """
        All legal moves for the current player.

        Returns:
            List of :class:`Move` objects representing all legal moves.

        Example:
            >>> board = Board()
            >>> moves = board.legal_moves
            >>> print(len(moves))  # 9 moves in starting position
            9
        """
        pass

    @property
    @abstractmethod
    def is_draw(self) -> bool:
        """
        Check if the current position is a draw.

        Draw conditions vary by variant (e.g., 25-move rule, threefold repetition).

        Returns:
            True if the position is drawn, False otherwise.
        """
        pass

    def push(self, move: Move, is_finished: bool = True) -> None:
        """
        Apply a move to the board.

        Args:
            move: The :class:`Move` to apply.
            is_finished: If True, switches turn after the move. Set to False
                during internal move generation.

        Example:
            >>> board = Board()
            >>> move = board.legal_moves[0]
            >>> board.push(move)
        """
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
        """
        Undo the last move.

        Args:
            is_finished: If True, switches turn back. Set to False during
                internal move generation.

        Returns:
            The :class:`Move` that was undone.

        Raises:
            IndexError: If no moves have been made.

        Example:
            >>> board = Board()
            >>> board.push_uci("31-27")
            >>> board.pop()
            Move: 31->27
        """
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
        """
        Make a move using UCI notation.

        Args:
            str_move: Move in UCI format, e.g. ``"31-27"`` for quiet moves
                or ``"26x17"`` for captures.

        Raises:
            ValueError: If the move is not legal in the current position.

        Example:
            >>> board = Board()
            >>> board.push_uci("31-27")
            >>> board.push_uci("18-22")
        """
        try:
            move = Move.from_uci(str_move, self.legal_moves)
        except ValueError as e:
            logger.error(f"{e}\n{self}")
            raise
        self.push(move)

    @property
    def is_threefold_repetition(self) -> bool:
        """
        Check for threefold repetition draw.

        Returns:
            True if the same position has occurred three times.
        """
        if len(self._moves_stack) >= 9:
            s = self._moves_stack
            if s[-1].square_list == s[-5].square_list == s[-9].square_list:
                return True
        return False

    @property
    def game_over(self) -> bool:
        """
        Check if the game has ended.

        Returns:
            True if drawn or if the current player has no legal moves.
        """
        return self.is_draw or not self.legal_moves

    @property
    def result(self) -> Literal["1/2-1/2", "1-0", "0-1", "-"]:
        """
        Get the game result.

        Returns:
            - ``"1-0"``: White wins
            - ``"0-1"``: Black wins
            - ``"1/2-1/2"``: Draw
            - ``"-"``: Game ongoing
        """
        if self.is_draw: return "1/2-1/2"
        if self.game_over: return "0-1" if self.turn == Color.WHITE else "1-0"
        return "-"

    @staticmethod
    def is_capture(move: Move) -> bool:
        """
        Check if a move is a capture.

        Args:
            move: The move to check.

        Returns:
            True if the move captures at least one piece.
        """
        return bool(move.captured_list)

    @property
    def fen(self) -> str:
        """
        Get the FEN string for the current position.

        Returns:
            FEN string, e.g. ``'[FEN "W:W31,32:B1,2"]'``.
            Kings are prefixed with 'K'.

        Example:
            >>> board = Board()
            >>> print(board.fen)
        """
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
        """
        Create a board from a FEN string.

        Args:
            fen: FEN string, e.g. ``"W:W31,32:B1,2"`` or ``"W:WK10,K20:BK35,K45"``.

        Returns:
            New board instance with the specified position.

        Raises:
            ValueError: If the FEN string is invalid.

        Example:
            >>> board = Board.from_fen("W:WK10,K20:BK35,K45")
        """
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
        """
        Get the PDN string for the game so far.

        Returns:
            PDN string with headers and move list.

        Example:
            >>> board = Board()
            >>> board.push_uci("31-27")
            >>> print(board.pdn)
        """
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
        Create a board by replaying moves from a PDN string.

        Supports both numeric (e.g., '33-28') and algebraic (e.g., 'c3-d4') notation.

        Args:
            pdn: PDN string with optional headers and move list.

        Returns:
            Board with all moves from the PDN applied.

        Raises:
            ValueError: If a move in the PDN is illegal.

        Example:
            >>> pdn = '[GameType "20"]\\n1. 32-28 19-23'
            >>> board = Board.from_pdn(pdn)
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
        """
        Get the board as a numpy array.

        Returns:
            1D numpy array of length ``SQUARES_COUNT`` with piece values:
            1=black man, 2=black king, -1=white man, -2=white king, 0=empty.

        Example:
            >>> board = Board()
            >>> pos = board.position
            >>> print(pos.shape)  # (50,) for standard board
        """
        arr = np.zeros(self.SQUARES_COUNT, dtype=np.int8)
        for sq in range(self.SQUARES_COUNT): arr[sq] = self._get(sq)
        return arr

    @property
    def _pos(self) -> np.ndarray:
        return self.position

    @property
    def friendly_form(self) -> np.ndarray:
        """
        Get the board as a 2D-like array including empty (non-playable) squares.

        Returns:
            Numpy array representing the full board grid.
        """
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

    # =========================================================================
    # AI / ML Support Methods
    # =========================================================================

    def copy(self) -> "BaseBoard":
        """
        Create a fast, cheap copy of the board.

        This is optimized for tree search - it copies only the essential
        state (bitboards, turn, halfmove clock) without deep copying the
        move stack. The new board has an empty move stack.

        Returns:
            A new board instance with the same position.

        Example:
            >>> board = Board()
            >>> board.push_uci("31-27")
            >>> clone = board.copy()
            >>> clone.push_uci("18-22")  # Doesn't affect original
            >>> len(board._moves_stack)  # Original unchanged
            1
        """
        new = object.__new__(self.__class__)
        new.white_men = self.white_men
        new.white_kings = self.white_kings
        new.black_men = self.black_men
        new.black_kings = self.black_kings
        new.turn = self.turn
        new.halfmove_clock = self.halfmove_clock
        new.shape = self.shape
        new._moves_stack = []
        return new

    def __copy__(self) -> "BaseBoard":
        """Support for copy.copy()."""
        return self.copy()

    def __deepcopy__(self, memo: dict) -> "BaseBoard":
        """Support for copy.deepcopy() - includes move stack."""
        new = self.copy()
        new._moves_stack = copy.deepcopy(self._moves_stack, memo)
        return new

    def features(self) -> BoardFeatures:
        """
        Extract features from the current position for AI/ML use.

        Returns a lightweight, immutable dataclass containing piece counts,
        material balance, mobility, and game phase. Computed on-demand with
        no caching to avoid memory overhead.

        Returns:
            :class:`BoardFeatures` with extracted position information.

        Example:
            >>> board = Board()
            >>> f = board.features()
            >>> print(f.white_men, f.black_men)  # 20 20
            >>> print(f.phase)  # 'opening'
        """
        wm = self._popcount(self.white_men)
        wk = self._popcount(self.white_kings)
        bm = self._popcount(self.black_men)
        bk = self._popcount(self.black_kings)

        total = wm + wk + bm + bk
        if total >= self.SQUARES_COUNT * 0.6:
            phase = "opening"
        elif total <= 8:
            phase = "endgame"
        else:
            phase = "midgame"

        return BoardFeatures(
            white_men=wm,
            white_kings=wk,
            black_men=bm,
            black_kings=bk,
            turn=1 if self.turn == Color.WHITE else -1,
            mobility=len(self.legal_moves),
            material_balance=(wm + 2 * wk) - (bm + 2 * bk),
            phase=phase,
        )

    def to_tensor(self, perspective: Optional[Color] = None) -> np.ndarray:
        """
        Convert board to tensor representation for neural networks.

        Returns a 4-channel representation:
            - Channel 0: Own men (1 where present, 0 elsewhere)
            - Channel 1: Own kings (1 where present, 0 elsewhere)
            - Channel 2: Opponent men (1 where present, 0 elsewhere)
            - Channel 3: Opponent kings (1 where present, 0 elsewhere)

        Args:
            perspective: The player's perspective. If None, uses current turn.
                From this perspective, "own" pieces are in channels 0-1.

        Returns:
            numpy array of shape ``(4, SQUARES_COUNT)`` with float32 dtype.
            For a 10x10 board, shape is ``(4, 50)``.

        Example:
            >>> board = Board()
            >>> tensor = board.to_tensor()
            >>> print(tensor.shape)  # (4, 50)
            >>> # Channel 0 = white men, Channel 2 = black men (white's perspective)
            >>> print(tensor[0].sum())  # 20.0 (20 white men)

        Note:
            This method does NOT slow down normal board operations. It creates
            the tensor only when called.
        """
        if perspective is None:
            perspective = self.turn

        tensor = np.zeros((4, self.SQUARES_COUNT), dtype=np.float32)

        if perspective == Color.WHITE:
            own_men, own_kings = self.white_men, self.white_kings
            opp_men, opp_kings = self.black_men, self.black_kings
        else:
            own_men, own_kings = self.black_men, self.black_kings
            opp_men, opp_kings = self.white_men, self.white_kings

        for sq in range(self.SQUARES_COUNT):
            bit = 1 << sq
            if own_men & bit:
                tensor[0, sq] = 1.0
            elif own_kings & bit:
                tensor[1, sq] = 1.0
            elif opp_men & bit:
                tensor[2, sq] = 1.0
            elif opp_kings & bit:
                tensor[3, sq] = 1.0

        return tensor

    def legal_moves_mask(self) -> np.ndarray:
        """
        Get a boolean mask indicating which move indices are legal.

        This is useful for masking neural network policy outputs. The mask
        has True at indices corresponding to legal moves and False elsewhere.

        The move index is computed as: ``from_square * SQUARES_COUNT + to_square``

        Returns:
            numpy array of shape ``(SQUARES_COUNT * SQUARES_COUNT,)`` with
            dtype bool. For a 10x10 board, shape is ``(2500,)``.

        Example:
            >>> board = Board()
            >>> mask = board.legal_moves_mask()
            >>> print(mask.shape)  # (2500,) for 10x10 board
            >>> policy = model(board.to_tensor())  # Your NN output
            >>> policy[~mask] = float('-inf')  # Mask illegal moves
            >>> move_idx = policy.argmax()
            >>> move = board.index_to_move(move_idx)

        Note:
            For captures that visit multiple squares, only the start and
            final destination are used for indexing.
        """
        n = self.SQUARES_COUNT
        mask = np.zeros(n * n, dtype=bool)
        for move in self.legal_moves:
            idx = move.square_list[0] * n + move.square_list[-1]
            mask[idx] = True
        return mask

    def move_to_index(self, move: Move) -> int:
        """
        Convert a move to a policy index.

        The index encodes the move as: ``from_square * SQUARES_COUNT + to_square``

        Args:
            move: The move to convert.

        Returns:
            Integer index in range ``[0, SQUARES_COUNT^2)``.

        Example:
            >>> board = Board()
            >>> move = board.legal_moves[0]
            >>> idx = board.move_to_index(move)
            >>> recovered = board.index_to_move(idx)
            >>> move == recovered  # True
        """
        return move.square_list[0] * self.SQUARES_COUNT + move.square_list[-1]

    def index_to_move(self, index: int) -> Move:
        """
        Convert a policy index back to a move.

        Finds the legal move matching the encoded from/to squares.

        Args:
            index: Policy index from ``move_to_index`` or network output.

        Returns:
            The matching :class:`Move` object from legal moves.

        Raises:
            ValueError: If no legal move matches the index.

        Example:
            >>> board = Board()
            >>> move = board.index_to_move(1530)  # sq 30 -> sq 30 % 50 = 30
        """
        n = self.SQUARES_COUNT
        from_sq = index // n
        to_sq = index % n

        for move in self.legal_moves:
            if move.square_list[0] == from_sq and move.square_list[-1] == to_sq:
                return move

        raise ValueError(
            f"No legal move from square {from_sq + 1} to {to_sq + 1}. "
            f"Legal moves: {list(map(str, self.legal_moves))}"
        )
