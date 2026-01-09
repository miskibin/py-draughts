"""Base class for draughts engines."""
from abc import ABC, abstractmethod
from typing import Optional

from draughts.boards.base import BaseBoard
from draughts.move import Move


class Engine(ABC):
    """
    Abstract base class for draughts engines.

    Implement this interface to create custom engines compatible with
    the :class:`~draughts.Server` for interactive play and testing.

    Attributes:
        depth_limit: Maximum search depth (if applicable).
        time_limit: Maximum time per move in seconds (if applicable).
        name: Engine name (defaults to class name).

    Example:
        >>> from draughts import Engine
        >>> import random
        >>>
        >>> class RandomEngine(Engine):
        ...     def get_best_move(self, board, with_evaluation=False):
        ...         move = random.choice(list(board.legal_moves))
        ...         return (move, 0.0) if with_evaluation else move
    """

    depth_limit: Optional[int]
    time_limit: Optional[float]

    def __init__(
        self,
        depth_limit: Optional[int] = 6,
        time_limit: Optional[float] = None,
    ):
        """
        Initialize the engine.

        Args:
            depth_limit: Maximum search depth. Interpretation depends on engine.
            time_limit: Maximum time in seconds per move.
        """
        self.depth_limit = depth_limit
        self.time_limit = time_limit
        self.name = self.__class__.__name__

    @abstractmethod
    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool = False
    ) -> Move | tuple[Move, float]:
        """
        Find the best move for the current position.

        Args:
            board: The current board state.
            with_evaluation: If True, return ``(move, score)`` tuple.

        Returns:
            Best :class:`Move`, or ``(Move, float)`` if ``with_evaluation=True``.
            Positive scores favor the current player.

        Example:
            >>> move = engine.get_best_move(board)
            >>> move, score = engine.get_best_move(board, with_evaluation=True)
        """
        ...
