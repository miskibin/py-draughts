"""Alpha-Beta search engine with advanced optimizations."""
import time
import random
from typing import List
from loguru import logger
import numpy as np

from draughts.boards.base import BaseBoard
from draughts.boards.standard import Move
from draughts.engines.engine import Engine
from draughts.models import Color


# Constants
INF = 10000.0
CHECKMATE = 1000.0
TT_MAX_SIZE = 500000  # Maximum transposition table entries
IID_DEPTH = 3  # Internal Iterative Deepening threshold
QS_MAX_DEPTH = 8  # Quiescence search depth limit

# Piece values
MAN_VALUE = 1.0
KING_VALUE = 2.5  # Kings are very powerful in draughts


def _create_pst_man(num_squares: int, rows: int) -> np.ndarray:
    """Create piece-square table for men (rewards advancement)."""
    squares_per_row = num_squares // rows
    pst = np.zeros(num_squares)
    for i in range(num_squares):
        row = i // squares_per_row
        # Higher value for squares closer to promotion (row 0)
        advancement_bonus = (rows - 1 - row) / (rows - 1) * 0.3
        # Small center bonus
        col = i % squares_per_row
        center_bonus = (1 - abs(col - squares_per_row / 2) / (squares_per_row / 2)) * 0.05
        pst[i] = advancement_bonus + center_bonus
    return pst


def _create_pst_king(num_squares: int, rows: int) -> np.ndarray:
    """Create piece-square table for kings (prefers center)."""
    squares_per_row = num_squares // rows
    pst = np.zeros(num_squares)
    center_row = rows / 2
    center_col = squares_per_row / 2
    for i in range(num_squares):
        row = i // squares_per_row
        col = i % squares_per_row
        # Distance from center (normalized)
        row_dist = abs(row - center_row) / center_row
        col_dist = abs(col - center_col) / center_col
        # Higher value for center squares
        pst[i] = (1 - (row_dist + col_dist) / 2) * 0.25
    return pst


class AlphaBetaEngine(Engine):
    """
    AI engine using Negamax search with alpha-beta pruning.

    This engine implements a strong draughts AI with several optimizations
    for efficient tree search. Works with any board variant (Standard, American, etc.).

    **Algorithm:**

    - **Negamax**: Simplified minimax using ``max(a,b) = -min(-a,-b)``
    - **Iterative Deepening**: Progressively deeper searches for time control
    - **Transposition Table**: Zobrist hashing to cache evaluated positions
    - **Quiescence Search**: Extends captures to avoid horizon effects
    - **Move Ordering**: PV moves, captures, killers, history heuristic
    - **PVS/LMR**: Principal Variation Search with Late Move Reductions

    **Evaluation:**

    - Material balance (men=1.0, kings=2.5)
    - Piece-Square Tables rewarding advancement and center control

    Attributes:
        depth_limit: Maximum search depth.
        time_limit: Optional time limit in seconds.
        nodes: Number of nodes searched in last call.

    Example:
        >>> from draughts import Board, AlphaBetaEngine
        >>> board = Board()
        >>> engine = AlphaBetaEngine(depth_limit=5)
        >>> move = engine.get_best_move(board)
        >>> board.push(move)

    Example with American Draughts:
        >>> from draughts.boards.american import Board
        >>> board = Board()
        >>> engine = AlphaBetaEngine(depth_limit=6)
        >>> move = engine.get_best_move(board)

    Example with evaluation:
        >>> move, score = engine.get_best_move(board, with_evaluation=True)
        >>> print(f"Best: {move}, Score: {score:.2f}")
    """

    def __init__(self, depth_limit: int = 6, time_limit: float | None = None, name: str | None = None):
        """
        Initialize the engine.

        Args:
            depth_limit: Maximum search depth. Higher = stronger but slower.
                Recommended: 5-6 for play, 7-8 for analysis.
            time_limit: Optional time limit in seconds. If set, search uses
                iterative deepening and stops when time expires.
            name: Custom engine name. Defaults to class name.

        Example:
            >>> engine = AlphaBetaEngine(depth_limit=6)
            >>> engine = AlphaBetaEngine(depth_limit=20, time_limit=1.0)
        """
        self.depth_limit = depth_limit
        self.time_limit = time_limit
        self.name = name or self.__class__.__name__
        self.nodes: int = 0
        self.tt: dict[int, tuple[int, int, float, Move | None]] = {}
        self.history: dict[tuple[int, int], int] = {}
        self.killers: dict[int, list[Move]] = {}

        # Zobrist Hashing - initialized lazily per board size
        self._zobrist_rng = random.Random(0)
        self._zobrist_tables: dict[int, list[list[int]]] = {}  # num_squares -> table
        self._zobrist_turn = self._zobrist_rng.getrandbits(64)
        
        # PST tables - cached per board configuration
        self._pst_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        
        # Current search state (set at start of search, used during eval)
        # Initialize with standard 50-square defaults so evaluate() works standalone
        self._current_zobrist: list[list[int]] = self._get_zobrist_table(50)
        self._current_pst: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] = self._get_pst_tables(50, 10)

        self.start_time: float = 0.0
        self.stop_search: bool = False

    @property
    def inspected_nodes(self) -> int:
        """Number of nodes searched in the last ``get_best_move`` call."""
        return self.nodes

    @inspected_nodes.setter
    def inspected_nodes(self, value: int) -> None:
        self.nodes = value

    def _get_zobrist_table(self, num_squares: int) -> list[list[int]]:
        """Get or create Zobrist table for given board size."""
        if num_squares not in self._zobrist_tables:
            # Create new table with deterministic RNG
            rng = random.Random(num_squares)  # Seed based on size for consistency
            table = [[rng.getrandbits(64) for _ in range(5)] for _ in range(num_squares)]
            self._zobrist_tables[num_squares] = table
        return self._zobrist_tables[num_squares]

    def _get_pst_tables(self, num_squares: int, rows: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get or create PST tables for given board configuration."""
        key = (num_squares, rows)
        if key not in self._pst_cache:
            pst_man_black = _create_pst_man(num_squares, rows)
            pst_man_white = pst_man_black[::-1].copy()
            pst_king_black = _create_pst_king(num_squares, rows)
            pst_king_white = pst_king_black[::-1].copy()
            self._pst_cache[key] = (pst_man_black, pst_man_white, pst_king_black, pst_king_white)
        return self._pst_cache[key]

    def _get_piece_index(self, piece):
        return piece + 2

    def _compute_hash_fast(self, board: BaseBoard) -> int:
        """Compute hash using cached zobrist table."""
        h = 0
        for i, piece in enumerate(board._pos):
            if piece != 0:
                h ^= self._current_zobrist[i][self._get_piece_index(piece)]
        if board.turn == Color.BLACK:
            h ^= self._zobrist_turn
        return h

    def compute_hash(self, board: BaseBoard) -> int:
        """Compute Zobrist hash for a board position (standalone, slower)."""
        num_squares = len(board._pos)
        zobrist_table = self._get_zobrist_table(num_squares)
        
        h = 0
        for i, piece in enumerate(board._pos):
            if piece != 0:
                h ^= zobrist_table[i][self._get_piece_index(piece)]
        if board.turn == Color.BLACK:
            h ^= self._zobrist_turn
        return h

    def evaluate(self, board: BaseBoard) -> float:
        """
        Evaluate the board position.

        Uses material count and piece-square tables.
        Works with any board variant.

        Args:
            board: The board to evaluate.

        Returns:
            Score from the perspective of the side to move.
            Positive = good for current player.
        """
        pos = board._pos
        pst = self._current_pst  # Cached at init or start of search

        # Piece masks
        white_men = (pos == -1)
        white_kings = (pos == -2)
        black_men = (pos == 1)
        black_kings = (pos == 2)

        # Material
        n_white_men = white_men.sum()
        n_white_kings = white_kings.sum()
        n_black_men = black_men.sum()
        n_black_kings = black_kings.sum()

        score = (n_black_men - n_white_men) * MAN_VALUE
        score += (n_black_kings - n_white_kings) * KING_VALUE

        # PST - Piece Square Tables
        score += pst[0][black_men].sum()   # pst_man_black
        score -= pst[1][white_men].sum()   # pst_man_white
        score += pst[2][black_kings].sum() # pst_king_black
        score -= pst[3][white_kings].sum() # pst_king_white

        # Return score relative to side to move
        return -score if board.turn == Color.WHITE else score

    def get_best_move(self, board: BaseBoard, with_evaluation: bool = False) -> Move | tuple[Move, float]:
        """
        Find the best move for the current position.

        Args:
            board: The board to analyze.
            with_evaluation: If True, return ``(move, score)`` tuple.

        Returns:
            Best :class:`Move`, or ``(Move, float)`` if ``with_evaluation=True``.

        Raises:
            ValueError: If no legal moves are available.

        Example:
            >>> move = engine.get_best_move(board)
            >>> move, score = engine.get_best_move(board, with_evaluation=True)
        """
        self.start_time = time.time()
        self.nodes = 0
        self.stop_search = False

        # Cache board-specific data for this search (avoids repeated lookups)
        num_squares = len(board._pos)
        self._current_zobrist = self._get_zobrist_table(num_squares)
        rows = 10 if num_squares == 50 else (8 if num_squares == 32 else int(np.sqrt(num_squares * 2)))
        self._current_pst = self._get_pst_tables(num_squares, rows)

        # Age history table (decay old values)
        for key in self.history:
            self.history[key] //= 2

        # Initial Hash
        current_hash = self._compute_hash_fast(board)

        best_move: Move | None = None
        best_score = -INF

        # Iterative Deepening
        max_depth = self.depth_limit or 6

        for d in range(1, max_depth + 1):
            try:
                score = self.negamax(board, d, -INF, INF, current_hash)

                # Retrieve PV from TT
                entry = self.tt.get(current_hash)
                if entry:
                    best_move = entry[3]
                    best_score = score

                logger.debug(f"Depth {d}: Score {score:.3f}, Move {best_move}, Nodes {self.nodes}")

                # Time check
                if self.time_limit and (time.time() - self.start_time > self.time_limit):
                    break

            except TimeoutError:
                break

        # Limit TT size
        if len(self.tt) > TT_MAX_SIZE:
            keys_to_remove = list(self.tt.keys())[:len(self.tt) - TT_MAX_SIZE // 2]
            for k in keys_to_remove:
                del self.tt[k]

        logger.info(f"Best move: {best_move}, Score: {best_score:.2f}, Nodes: {self.nodes}")

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("No legal moves available")

        if best_move is None:
            best_move = legal_moves[0]
            best_score = -INF

        if with_evaluation:
            return best_move, float(best_score)
        return best_move

    def negamax(self, board: BaseBoard, depth: int, alpha: float, beta: float, h: int) -> float:
        """Negamax search with alpha-beta pruning."""
        self.nodes += 1

        # Check time
        if self.nodes % 2048 == 0:
            if self.time_limit and (time.time() - self.start_time > self.time_limit):
                self.stop_search = True

        if self.stop_search:
            return alpha

        # Transposition Table Lookup
        tt_entry = self.tt.get(h)
        if tt_entry:
            tt_depth, tt_flag, tt_score, tt_move = tt_entry
            if tt_depth >= depth:
                if tt_flag == 0:  # Exact
                    return tt_score
                elif tt_flag == 1:  # Lowerbound (Alpha)
                    alpha = max(alpha, tt_score)
                elif tt_flag == 2:  # Upperbound (Beta)
                    beta = min(beta, tt_score)

                if alpha >= beta:
                    return tt_score

        # Base case: Leaf or Game Over
        if depth <= 0:
            return self.quiescence_search(board, alpha, beta, h)

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return -CHECKMATE + ((self.depth_limit or 6) - depth)

        # Check for draw
        if board.is_draw:
            return 0.0

        # Internal Iterative Deepening
        tt_entry = self.tt.get(h)
        if depth >= IID_DEPTH and (not tt_entry or tt_entry[3] is None):
            self.negamax(board, depth - 2, alpha, beta, h)

        # Move Ordering
        legal_moves = self._order_moves(legal_moves, board, h, depth)

        best_value = -INF
        best_move = None
        tt_flag = 1  # Alpha (Lowerbound)

        for i, move in enumerate(legal_moves):
            # Incremental Hash Update
            new_hash = self._update_hash(h, board, move)

            board.push(move)

            # PVS (Principal Variation Search)
            if i == 0:
                val = -self.negamax(board, depth - 1, -beta, -alpha, new_hash)
            else:
                # LMR (Late Move Reductions)
                reduction = 0
                if depth >= 3 and i >= 3 and not move.captured_list:
                    reduction = 1

                # Null Window Search with possible reduction
                val = -self.negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, new_hash)

                # Re-search if needed
                if val > alpha and (reduction > 0 or val < beta):
                    val = -self.negamax(board, depth - 1, -beta, -alpha, new_hash)

            board.pop()

            if self.stop_search:
                return alpha

            if val > best_value:
                best_value = val
                best_move = move

            alpha = max(alpha, val)
            if alpha >= beta:
                tt_flag = 2  # Beta (Upperbound)
                if not move.captured_list:
                    self._update_killers(move, depth)
                self._update_history(move, depth)
                break

        # Store in TT
        self.tt[h] = (depth, tt_flag, best_value, best_move)

        return best_value

    def quiescence_search(self, board: BaseBoard, alpha: float, beta: float, h: int, qs_depth: int = 0) -> float:
        """Search captures until position is quiet."""
        self.nodes += 1

        # Stand-pat (static evaluation)
        stand_pat = self.evaluate(board)

        if stand_pat >= beta:
            return beta

        if alpha < stand_pat:
            alpha = stand_pat

        # Depth limit to prevent explosion
        if qs_depth >= QS_MAX_DEPTH:
            return stand_pat

        # Generate only captures
        legal_moves = list(board.legal_moves)
        captures = [m for m in legal_moves if m.captured_list]

        if not captures:
            return stand_pat

        # Order captures (MVV-LVA)
        captures = self._order_captures(captures, board)

        for move in captures:
            new_hash = self._update_hash(h, board, move)
            board.push(move)
            score = -self.quiescence_search(board, -beta, -alpha, new_hash, qs_depth + 1)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def _update_hash(self, current_hash: int, board: BaseBoard, move: Move) -> int:
        zt = self._current_zobrist  # Cached zobrist table
        
        # XOR out source
        start_sq = move.square_list[0]
        piece = board._pos[start_sq]
        current_hash ^= zt[start_sq][piece + 2]

        # XOR in dest
        end_sq = move.square_list[-1]
        new_piece = piece
        if move.is_promotion:
            new_piece = 2 if piece == 1 else -2

        current_hash ^= zt[end_sq][new_piece + 2]

        # XOR out captures
        for cap_sq in move.captured_list:
            cap_piece = board._pos[cap_sq]
            current_hash ^= zt[cap_sq][cap_piece + 2]

        # Switch turn
        current_hash ^= self._zobrist_turn

        return current_hash

    def _order_moves(self, moves: List[Move], board: BaseBoard | None = None, h: int = 0, depth: int = 0) -> List[Move]:
        tt_entry = self.tt.get(h)
        pv_move = tt_entry[3] if tt_entry else None

        def score_move(move):
            if move == pv_move:
                return 1000000

            if move.captured_list:
                return 100000 + len(move.captured_list) * 1000

            killers = self.killers.get(depth, [])
            if move in killers:
                return 90000

            start = move.square_list[0]
            end = move.square_list[-1]
            return self.history.get((start, end), 0)

        moves.sort(key=score_move, reverse=True)
        return moves

    def _order_captures(self, moves: List[Move], board: BaseBoard) -> List[Move]:
        moves.sort(key=lambda m: len(m.captured_list), reverse=True)
        return moves

    def _update_killers(self, move: Move, depth: int):
        if depth not in self.killers:
            self.killers[depth] = []
        if move not in self.killers[depth]:
            self.killers[depth].insert(0, move)
            self.killers[depth] = self.killers[depth][:2]

    def _update_history(self, move: Move, depth: int):
        start = move.square_list[0]
        end = move.square_list[-1]
        self.history[(start, end)] = self.history.get((start, end), 0) + depth * depth
