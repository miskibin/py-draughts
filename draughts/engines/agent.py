"""Agent interface for building custom AI players."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from draughts.engines.engine import Engine

if TYPE_CHECKING:
    from draughts.boards.base import BaseBoard
    from draughts.move import Move


@runtime_checkable
class Agent(Protocol):
    """
    Protocol for draughts-playing agents.

    Implement ``select_move(board) -> Move`` to create agents compatible
    with :class:`AgentEngine` and :class:`~draughts.Benchmark`.
    """

    def select_move(self, board: "BaseBoard") -> "Move":
        """Select a move to play."""
        ...


class BaseAgent(ABC):
    """
    Abstract base class for agents with optional configuration.

    Extend this class when you need:
    - Named agents for logging/display
    - Configuration that affects move selection
    - State that persists between moves

    For stateless agents, implement :class:`Agent` protocol directly.

    Attributes:
        name: Agent name for display purposes.

    Example::

        from draughts import BaseAgent, Board, Move

        class GreedyAgent(BaseAgent):
            '''Always captures the most pieces possible.'''

            def __init__(self):
                super().__init__(name="GreedyBot")

            def select_move(self, board: Board) -> Move:
                moves = board.legal_moves
                # Sort by capture count, return best
                return max(moves, key=lambda m: len(m.captured_list))
    """

    def __init__(self, name: str | None = None):
        """
        Initialize the agent.

        Args:
            name: Display name. Defaults to class name.
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def select_move(self, board: "BaseBoard") -> "Move":
        """
        Select a move to play.

        Args:
            board: Current board position.

        Returns:
            A legal :class:`Move` to play.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"

    def as_engine(self) -> "AgentEngine":
        """
        Wrap this agent as an Engine for use with Benchmark.

        Returns:
            An :class:`AgentEngine` wrapping this agent.

        Example::

            from draughts import Benchmark, BaseAgent

            class MyAgent(BaseAgent):
                def select_move(self, board):
                    return board.legal_moves[0]

            # Use with Benchmark
            stats = Benchmark(
                MyAgent().as_engine(),
                AlphaBetaEngine(depth_limit=4),
                games=10
            ).run()
        """
        return AgentEngine(self)


class AgentEngine(Engine):
    """
    Adapter that wraps any Agent as an Engine.

    This allows agents to be used with :class:`~draughts.Benchmark`
    and other Engine-based APIs.

    Attributes:
        agent: The wrapped agent.
        name: Engine name (from agent or custom).

    Example::

        from draughts import AgentEngine, Benchmark
        import random

        class RandomAgent:
            def select_move(self, board):
                return random.choice(board.legal_moves)

        # Wrap and benchmark
        engine = AgentEngine(RandomAgent(), name="Random")
        stats = Benchmark(engine, AlphaBetaEngine(depth_limit=4)).run()

    Example with BaseAgent::

        from draughts import BaseAgent

        class GreedyAgent(BaseAgent):
            def select_move(self, board):
                return max(board.legal_moves, key=lambda m: len(m.captured_list))

        # BaseAgent has as_engine() shortcut
        engine = GreedyAgent().as_engine()
    """

    def __init__(self, agent: Agent, name: str | None = None):
        """
        Wrap an agent as an engine.

        Args:
            agent: Any object implementing the Agent protocol.
            name: Custom engine name. If None, uses agent's name attribute
                or class name.
        """
        # Get name from agent if available
        if name is None:
            if hasattr(agent, "name"):
                name = agent.name
            else:
                name = agent.__class__.__name__

        super().__init__(depth_limit=None, time_limit=None, name=name)
        self.agent = agent
        # Track nodes for benchmark compatibility
        self.nodes = 0

    @property
    def inspected_nodes(self) -> int:
        """Number of nodes (always 1 for simple agents)."""
        return self.nodes

    @inspected_nodes.setter
    def inspected_nodes(self, value: int) -> None:
        self.nodes = value

    def get_best_move(
        self, board: "BaseBoard", with_evaluation: bool = False
    ) -> "Move | tuple[Move, float]":
        """
        Get best move by delegating to the wrapped agent.

        Args:
            board: Current board position.
            with_evaluation: If True, return (move, 0.0) tuple.
                Agents don't provide evaluations, so score is always 0.

        Returns:
            Move from the agent, or (Move, 0.0) if with_evaluation=True.
        """
        self.nodes = 1  # Count as 1 node for benchmarking
        move = self.agent.select_move(board)

        if with_evaluation:
            return move, 0.0
        return move

