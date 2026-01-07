import time
import random
from abc import ABC, abstractmethod
from typing import Optional, List
from loguru import logger
import numpy as np

from draughts.boards.base import BaseBoard
from draughts.boards.standard import Board, Move, Figure
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

# PST Tables for men - rewards advancement (simple linear)
PST_MAN_BLACK = np.array([
    0.25, 0.30, 0.30, 0.30, 0.25,   # 0-4: Near promotion
    0.20, 0.22, 0.25, 0.22, 0.20,   # 5-9
    0.15, 0.18, 0.20, 0.18, 0.15,   # 10-14
    0.12, 0.15, 0.18, 0.15, 0.12,   # 15-19
    0.08, 0.12, 0.15, 0.12, 0.08,   # 20-24
    0.06, 0.10, 0.12, 0.10, 0.06,   # 25-29
    0.04, 0.08, 0.10, 0.08, 0.04,   # 30-34
    0.02, 0.05, 0.08, 0.05, 0.02,   # 35-39
    0.01, 0.02, 0.04, 0.02, 0.01,   # 40-44
    0.00, 0.00, 0.00, 0.00, 0.00    # 45-49: Starting rank
])

PST_MAN_WHITE = PST_MAN_BLACK[::-1]

# King PST - strongly prefers center, avoids edges
PST_KING_BLACK = np.array([
    0.00, 0.05, 0.05, 0.05, 0.00,
    0.05, 0.10, 0.12, 0.10, 0.05,
    0.05, 0.12, 0.15, 0.12, 0.05,
    0.08, 0.15, 0.20, 0.15, 0.08,
    0.10, 0.18, 0.25, 0.18, 0.10,
    0.10, 0.18, 0.25, 0.18, 0.10,
    0.08, 0.15, 0.20, 0.15, 0.08,
    0.05, 0.12, 0.15, 0.12, 0.05,
    0.05, 0.10, 0.12, 0.10, 0.05,
    0.00, 0.05, 0.05, 0.05, 0.00
])

PST_KING_WHITE = PST_KING_BLACK[::-1]



class AlphaBetaEngine(Engine):
    """
    Advanced Alpha-Beta engine with Negamax, Iterative Deepening, and Transposition Tables.
    
    Optimizations:
    - Negamax architecture
    - Iterative Deepening
    - Transposition Table with Zobrist Hashing
    - Quiescence Search
    - Move Ordering (PV, Killer, History, MVV-LVA)
    - Advanced Evaluation (PST)
    """

    def __init__(self, depth_limit: int = 6, time_limit: float | None = None):
        self.depth_limit = depth_limit
        self.time_limit = time_limit
        self.nodes: int = 0
        self.tt: dict[int, tuple[int, int, float, Move | None]] = {}  # {hash: (depth, flag, score, best_move)}
        self.history: dict[tuple[int, int], int] = {}  # {(from, to): score}
        self.killers: dict[int, list[Move]] = {}  # {depth: [move1, move2]}
        
        # Zobrist Hashing (deterministic per-engine; does not perturb global RNG)
        self._zobrist_rng = random.Random(0)
        self.zobrist_table = self._init_zobrist()
        self.zobrist_turn = self._zobrist_rng.getrandbits(64)  # XOR when it's black's turn
        
        self.start_time: float = 0.0
        self.stop_search: bool = False

    @property
    def inspected_nodes(self) -> int:
        return self.nodes

    @inspected_nodes.setter
    def inspected_nodes(self, value: int) -> None:
        self.nodes = value

    def _init_zobrist(self):
        # 50 squares, 5 piece types (Empty, B_Man, W_Man, B_King, W_King)
        # We map piece values to indices: 
        # -2 (W_King) -> 0
        # -1 (W_Man) -> 1
        # 0 (Empty) -> 2
        # 1 (B_Man) -> 3
        # 2 (B_King) -> 4
        table = [[self._zobrist_rng.getrandbits(64) for _ in range(5)] for _ in range(50)]
        return table

    def _get_piece_index(self, piece):
        # Map piece value to 0-4 index
        return piece + 2

    def compute_hash(self, board: BaseBoard) -> int:
        h = 0
        for i, piece in enumerate(board._pos):
            if piece != 0:
                h ^= self.zobrist_table[i][self._get_piece_index(piece)]
        if board.turn == Color.BLACK:
            h ^= self.zobrist_turn
        return h

    def evaluate(self, board: BaseBoard) -> float:
        """
        Evaluation function with material and PST.
        Returns score from the perspective of the side to move.
        """
        pos = board._pos
        
        # Piece masks
        white_men = (pos == -1)
        white_kings = (pos == -2)
        black_men = (pos == 1)
        black_kings = (pos == 2)
        
        # Count pieces
        n_white_men = np.sum(white_men)
        n_white_kings = np.sum(white_kings)
        n_black_men = np.sum(black_men)
        n_black_kings = np.sum(black_kings)
        
        # Material
        score = (n_black_men - n_white_men) * MAN_VALUE
        score += (n_black_kings - n_white_kings) * KING_VALUE
        
        # PST - Piece Square Tables
        score += np.sum(PST_MAN_BLACK[black_men])
        score -= np.sum(PST_MAN_WHITE[white_men])
        score += np.sum(PST_KING_BLACK[black_kings])
        score -= np.sum(PST_KING_WHITE[white_kings])
        
        # Return score relative to side to move
        if board.turn == Color.WHITE:
            return -score
        return score

    def get_best_move(self, board: BaseBoard, with_evaluation: bool = False) -> Move | tuple[Move, float]:
        self.start_time = time.time()
        self.nodes = 0
        self.stop_search = False
        
        # Age history table (decay old values)
        for key in self.history:
            self.history[key] //= 2
        
        # Initial Hash
        current_hash = self.compute_hash(board)
        
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
            # Remove oldest entries (simple approach)
            keys_to_remove = list(self.tt.keys())[:len(self.tt) - TT_MAX_SIZE // 2]
            for k in keys_to_remove:
                del self.tt[k]
        
        logger.info(f"Best move: {best_move}, Score: {best_score:.2f}, Nodes: {self.nodes}")

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("No legal moves available")

        if best_move is None:
            # Fallback if search failed to find a move.
            best_move = legal_moves[0]
            best_score = -INF

        if with_evaluation:
            return best_move, float(best_score)
        return best_move

    def negamax(self, board: BaseBoard, depth: int, alpha: float, beta: float, h: int) -> float:
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
                if tt_flag == 0: # Exact
                    return tt_score
                elif tt_flag == 1: # Lowerbound (Alpha)
                    alpha = max(alpha, tt_score)
                elif tt_flag == 2: # Upperbound (Beta)
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
        
        # Internal Iterative Deepening - if no TT move, do a shallow search first
        tt_entry = self.tt.get(h)
        if depth >= IID_DEPTH and (not tt_entry or tt_entry[3] is None):
            self.negamax(board, depth - 2, alpha, beta, h)

        # Move Ordering
        legal_moves = self._order_moves(legal_moves, board, h, depth)
        
        best_value = -INF
        best_move = None
        tt_flag = 1 # Alpha (Lowerbound)
        
        for i, move in enumerate(legal_moves):
            # Incremental Hash Update
            new_hash = self._update_hash(h, board, move)
            
            board.push(move)
            
            # PVS (Principal Variation Search)
            if i == 0:
                val = -self.negamax(board, depth - 1, -beta, -alpha, new_hash)
            else:
                # LMR (Late Move Reductions) - only for quiet moves at depth >= 3
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
                # Beta Cutoff
                tt_flag = 2 # Beta (Upperbound)
                # Update Killers
                if not move.captured_list:
                    self._update_killers(move, depth)
                # Update History
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
        # XOR out source
        start_sq = move.square_list[0]
        piece = board._pos[start_sq]
        current_hash ^= self.zobrist_table[start_sq][self._get_piece_index(piece)]
        
        # XOR in dest
        end_sq = move.square_list[-1]
        # Determine new piece type (check promotion)
        new_piece = piece
        if move.is_promotion:
            # If it was Man, becomes King.
            # We need to know color.
            if piece == 1: new_piece = 2
            elif piece == -1: new_piece = -2
        
        current_hash ^= self.zobrist_table[end_sq][self._get_piece_index(new_piece)]
        
        # XOR out captures
        for cap_sq in move.captured_list:
            cap_piece = board._pos[cap_sq]
            current_hash ^= self.zobrist_table[cap_sq][self._get_piece_index(cap_piece)]
            
        # Switch turn
        current_hash ^= self.zobrist_turn
        
        return current_hash

    def _order_moves(self, moves: List[Move], board: BaseBoard | None = None, h: int = 0, depth: int = 0) -> List[Move]:
        # 1. PV Move from TT
        tt_entry = self.tt.get(h)
        pv_move = tt_entry[3] if tt_entry else None
        
        # 2. Captures (MVV-LVA)
        # 3. Killer Moves
        # 4. History Heuristic
        
        def score_move(move):
            if move == pv_move:
                return 1000000
            
            if move.captured_list:
                # MVV-LVA: Victim Value - Attacker Value
                # We want to capture high value piece with low value piece
                # But in draughts, captures are mandatory and often chains.
                # Length of capture is good proxy.
                return 100000 + len(move.captured_list) * 1000
            
            # Killer
            killers = self.killers.get(depth, [])
            if move in killers:
                return 90000
                
            # History
            start = move.square_list[0]
            end = move.square_list[-1]
            return self.history.get((start, end), 0)

        moves.sort(key=score_move, reverse=True)
        return moves

    def _order_captures(self, moves: List[Move], board: BaseBoard) -> List[Move]:
        # Sort by number of captures
        moves.sort(key=lambda m: len(m.captured_list), reverse=True)
        return moves

    def _update_killers(self, move: Move, depth: int):
        if depth not in self.killers:
            self.killers[depth] = []
        if move not in self.killers[depth]:
            self.killers[depth].insert(0, move)
            self.killers[depth] = self.killers[depth][:2] # Keep top 2

    def _update_history(self, move: Move, depth: int):
        start = move.square_list[0]
        end = move.square_list[-1]
        self.history[(start, end)] = self.history.get((start, end), 0) + depth * depth
