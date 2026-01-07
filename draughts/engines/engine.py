from abc import ABC, abstractmethod
from typing import Optional

from draughts.boards.base import BaseBoard
from draughts.boards.standard import Board, Move, Figure


class Engine(ABC):
    """
    Interface for engine compatible with Server class.

    This abstract class defines the interface that all engines must implement
    to be compatible with the Server class for playing games.
    """
    
    depth_limit: Optional[int]
    time_limit: Optional[float]

    def __init__(
        self,
        depth_limit: Optional[int] = 6,
        time_limit: Optional[float] = None,
    ):
        """
        Initializes the engine with optional depth and time limits.
        Args:
            depth_limit: Maximum search depth for the engine
            time_limit: Maximum time (in seconds) allowed for move calculation 
        """

        self.depth_limit = depth_limit
        self.time_limit = time_limit
        self.name = self.__class__.__name__

    @abstractmethod
    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool
    ) -> Move | tuple[Move, float]:
        """
        Returns best move for given board.

        Args:
            board: The current board state
            with_evaluation: If True, return tuple of (move, evaluation score)

        Returns:
            Either a Move object, or tuple of (Move, float) if with_evaluation=True

        Example:
            >>> engine = AlphaBetaEngine(depth_limit=3)
            >>> move = engine.get_best_move(board)
            >>> move, score = engine.get_best_move(board, with_evaluation=True)

        Note:
            To get list of legal moves use ``board.legal_moves``
        """
        ...
