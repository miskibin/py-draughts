from abc import ABC, abstractmethod
from typing import Optional
from draughts.boards.standard import Board, Move, Figure
from draughts.models import Color
from draughts.utils import logger
import numpy as np


class Engine(ABC):
    """
    Interface for engine compatible with Server class.
    
    This abstract class defines the interface that all engines must implement
    to be compatible with the Server class for playing games.
    """

    @abstractmethod
    def get_best_move(
        self, board: Board, with_evaluation: bool
    ) -> Move | tuple[Move, float]:
        """
        Returns best move for given board.
        
        Args:
            board: The current board state
            with_evaluation: If True, return tuple of (move, evaluation score)
        
        Returns:
            Either a Move object, or tuple of (Move, float) if with_evaluation=True
        
        Example:
            >>> engine = AlphaBetaEngine(depth=3)
            >>> move = engine.get_best_move(board)
            >>> move, score = engine.get_best_move(board, with_evaluation=True)
        
        Note:
            To get list of legal moves use ``board.legal_moves``
        """
        ...



class AlphaBetaEngine(Engine):
    """
    Engine using alpha-beta pruning algorithm.
    
    Alpha-beta pruning is a minimax algorithm with optimization that prunes
    branches of the game tree that cannot possibly influence the final decision.
    The algorithm will not inspect nodes that are worse than already inspected nodes.
    
    Additionally, this engine prioritizes capture moves first, as they are usually
    better than non-capture moves in draughts.
    
    Features:
        - Move ordering: Captures are evaluated first for better pruning
        - Transposition table: Caches evaluated positions to avoid redundant calculations
        - Enhanced evaluation: Considers piece positioning and king promotion
        
    Performance Tips:
        - Depth 3-4: Good for interactive play (fast response)
        - Depth 5-6: Strong play (slower but better moves)
        - Depth 7+: Very strong but can be slow
    
    Example:
        >>> from draughts import get_board
        >>> from draughts.engine import AlphaBetaEngine
        >>> board = get_board('standard')
        >>> engine = AlphaBetaEngine(depth=5)
        >>> best_move = engine.get_best_move(board)
        >>> best_move, score = engine.get_best_move(board, with_evaluation=True)
    """

    WHITE_WIN = -100 * Color.WHITE.value
    BLACK_WIN = -100 * Color.BLACK.value
    LOSE = -100
    
    # Evaluation constants
    BOARD_WIDTH = 5  # Width of the draughts board in playable squares
    MAX_ROW = 9      # Maximum row index for positional evaluation
    POSITION_BONUS = 0.1  # Bonus multiplier for advanced piece positioning

    def __init__(self, depth):
        """
        Initialize the Alpha-Beta engine.
        
        Args:
            depth: Search depth in half-moves (plies). Higher depth means stronger
                   play but longer calculation time. Typical values are 3-6.
        """
        self.depth = depth
        self.inspected_nodes = 0
        # Transposition table: stores {board_hash: (depth, score)}
        self._transposition_table = {}

    def evaluate(self, board: Board):
        """
        Evaluation function for the current board position.
        
        The evaluation considers:
        - Material balance: Each piece has a value (man=1, king=2)
        - Piece positioning: Center control and advancement are valued
        - King promotion potential
        
        Returns:
            float: Positive score favors Black, negative favors White
            
        Note:
            This is a relatively simple evaluation. For stronger play,
            consider factors like piece mobility, pawn structure, and
            endgame patterns.
        """
        # Material count (basic evaluation)
        score = -board._pos.sum()
        
        # Positional bonus: favor advanced pieces and center control
        position = board.position
        size = len(position)
        for idx in range(size):
            piece = position[idx]
            if piece != 0:
                # Award bonus for piece advancement (based on board position)
                row_bonus = (idx // self.BOARD_WIDTH) * self.POSITION_BONUS if piece > 0 \
                           else ((self.MAX_ROW - idx // self.BOARD_WIDTH) * self.POSITION_BONUS)
                score += row_bonus * abs(piece)
        
        return score

    def get_best_move(self, board: Board, with_evaluation: bool = False):
        """
        Find and return the best move for the current position.
        
        Args:
            board: Current board state
            with_evaluation: If True, return (move, evaluation) tuple
            
        Returns:
            Move or tuple[Move, float]: Best move, optionally with its evaluation
        """
        self.inspected_nodes = 0
        # Note: Transposition table is preserved between moves for better performance
        move, evaluation = self.__get_engine_move(board)
        logger.debug(f"\ninspected  {self.inspected_nodes} nodes\n")
        logger.info(f"best move: {move}, evaluation: {evaluation:.2f}")
        if with_evaluation:
            return move, evaluation
        return move

    def __get_engine_move(self, board: Board) -> tuple:
        depth = self.depth
        legal_moves = list(board.legal_moves)
        
        # Move ordering: prioritize captures for better pruning
        legal_moves = self._order_moves(legal_moves, board)
        
        evals = []
        alpha, beta = self.BLACK_WIN, self.WHITE_WIN

        for move in legal_moves:
            board.push(move)
            evals.append(
                self.__alpha_beta_pruning(
                    board,
                    depth - 1,
                    alpha,
                    beta,
                )
            )
            board.pop()

            # Update alpha-beta window
            if board.turn == Color.WHITE:
                alpha = max(alpha, evals[-1])  # type: ignore[assignment]
            else:
                beta = min(beta, evals[-1])  # type: ignore[assignment]
                
        # Select best move based on current player
        index = (
            evals.index(max(evals))
            if board.turn == Color.WHITE
            else evals.index(min(evals))
        )
        return legal_moves[index], evals[index]
    
    def _order_moves(self, moves: list[Move], board: Board) -> list[Move]:
        captures = [m for m in moves if m.captured_list]
        non_captures = [m for m in moves if not m.captured_list]
        return captures + non_captures

    def __alpha_beta_pruning(
        self, board: Board, depth: int, alpha: float, beta: float
    ) -> float:
        # Terminal node: game is over
        if board.game_over:
            if not board.is_draw:
                return self.LOSE * board.turn.value
            return -0.2 * board.turn.value
            
        # Terminal node: reached maximum depth
        if depth == 0:
            self.inspected_nodes += 1
            return self.evaluate(board)
        
        # Check transposition table for cached position
        board_hash = hash(board.fen)
        if board_hash in self._transposition_table:
            cached_depth, cached_score = self._transposition_table[board_hash]
            if cached_depth >= depth:
                return cached_score
        
        # Generate legal moves with ordering for better pruning
        legal_moves = list(board.legal_moves)
        legal_moves = self._order_moves(legal_moves, board)

        # Evaluate each move
        for move in legal_moves:
            board.push(move)
            evaluation = self.__alpha_beta_pruning(board, depth - 1, alpha, beta)
            
            # Small penalty for not promoting to king (encourages king promotion)
            evaluation -= np.abs(board.position[move.square_list[-1]]) == Figure.KING
            board.pop()
            
            # Update alpha-beta window
            if board.turn == Color.WHITE:
                alpha = max(alpha, evaluation)
            else:
                beta = min(beta, evaluation)
                
            # Prune: this branch cannot improve the result
            if beta <= alpha:
                break
        
        # Cache the result for this position
        result = alpha if board.turn == Color.WHITE else beta
        self._transposition_table[board_hash] = (depth, result)
        
        return result
