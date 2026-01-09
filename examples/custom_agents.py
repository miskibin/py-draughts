"""
Example custom agents for py-draughts.

This file demonstrates how to create AI agents using different strategies.
All agents implement the Agent protocol and can be used with Benchmark.

Run this file to see the agents play against each other:
    python examples/custom_agents.py
"""
import random
from typing import Callable

from draughts import (
    AgentEngine,
    AlphaBetaEngine,
    BaseAgent,
    Benchmark,
    Board,
    Color,
    Move,
)


# =============================================================================
# Simple Agents (Protocol-style - just implement select_move)
# =============================================================================


class RandomAgent:
    """
    Selects moves uniformly at random.

    The simplest possible agent - useful as a baseline.
    """

    def select_move(self, board: Board) -> Move:
        return random.choice(board.legal_moves)


class FirstMoveAgent:
    """
    Always plays the first legal move.

    Deterministic but weak - useful for testing.
    """

    def select_move(self, board: Board) -> Move:
        return board.legal_moves[0]


# =============================================================================
# Named Agents (BaseAgent-style - with configuration)
# =============================================================================


class GreedyAgent(BaseAgent):
    """
    Captures the most pieces possible.

    Simple heuristic: always take the maximum capture.
    Breaks ties by preferring to capture kings.
    """

    def __init__(self):
        super().__init__(name="Greedy")

    def select_move(self, board: Board) -> Move:
        moves = board.legal_moves

        # Score: number of captures + 0.5 for each king captured
        def score(m: Move) -> float:
            base = len(m.captured_list)
            # captured_entities: 2 or -2 for kings
            king_bonus = sum(0.5 for e in m.captured_entities if abs(e) == 2)
            return base + king_bonus

        return max(moves, key=score)


class MaterialAgent(BaseAgent):
    """
    Evaluates moves by resulting material balance.

    Uses 1-ply lookahead: tries each move, evaluates material,
    picks the best. Simple but reasonably effective.
    """

    def __init__(self, king_value: float = 2.5):
        super().__init__(name="Material")
        self.king_value = king_value

    def select_move(self, board: Board) -> Move:
        best_move = None
        best_score = float("-inf")

        for move in board.legal_moves:
            # Clone, apply move, evaluate
            clone = board.copy()
            clone.push(move)

            score = self._evaluate(clone, board.turn)
            if score > best_score:
                best_score = score
                best_move = move

        return best_move  # type: ignore

    def _evaluate(self, board: Board, perspective: Color) -> float:
        """Evaluate material from perspective's point of view."""
        f = board.features()

        white_material = f.white_men + self.king_value * f.white_kings
        black_material = f.black_men + self.king_value * f.black_kings

        if perspective == Color.WHITE:
            return white_material - black_material
        return black_material - white_material


class PositionalAgent(BaseAgent):
    """
    Combines material with positional factors.

    Considers:
    - Material balance
    - Piece advancement (men closer to promotion)
    - Center control for kings
    - Mobility (number of legal moves)
    """

    def __init__(self):
        super().__init__(name="Positional")

    def select_move(self, board: Board) -> Move:
        best_move = None
        best_score = float("-inf")

        for move in board.legal_moves:
            clone = board.copy()
            clone.push(move)

            score = self._evaluate(clone, board.turn)
            if score > best_score:
                best_score = score
                best_move = move

        return best_move  # type: ignore

    def _evaluate(self, board: Board, perspective: Color) -> float:
        """Positional evaluation."""
        f = board.features()

        # Material (kings worth 2.5)
        white_mat = f.white_men + 2.5 * f.white_kings
        black_mat = f.black_men + 2.5 * f.black_kings
        material = white_mat - black_mat

        # Advancement bonus from position array
        pos = board.position
        advancement = 0.0
        for sq, piece in enumerate(pos):
            row = sq // 5  # 0-9 for standard board
            if piece == -1:  # White man
                advancement += (9 - row) * 0.02  # Closer to row 0 = better
            elif piece == 1:  # Black man
                advancement -= row * 0.02  # Closer to row 9 = better

        # Mobility (small bonus)
        mobility = 0.01 * f.mobility if f.turn == 1 else -0.01 * f.mobility

        score = material + advancement + mobility

        if perspective == Color.WHITE:
            return score
        return -score


class MonteCarloAgent(BaseAgent):
    """
    Monte Carlo evaluation with random rollouts.

    For each legal move:
    1. Clone the board
    2. Apply the move
    3. Play N random games to completion
    4. Track win rate
    5. Pick move with highest win rate

    This is a simplified MCTS without tree building.
    """

    def __init__(self, simulations: int = 50, max_plies: int = 100):
        super().__init__(name=f"MC-{simulations}")
        self.simulations = simulations
        self.max_plies = max_plies

    def select_move(self, board: Board) -> Move:
        moves = board.legal_moves
        if len(moves) == 1:
            return moves[0]

        best_move = moves[0]
        best_wins = -1.0

        our_color = board.turn

        for move in moves:
            wins = 0.0
            for _ in range(self.simulations):
                clone = board.copy()
                clone.push(move)

                # Random playout
                result = self._rollout(clone)

                # Score based on result
                if result == "1/2-1/2":
                    wins += 0.5
                elif (result == "1-0" and our_color == Color.WHITE) or (
                    result == "0-1" and our_color == Color.BLACK
                ):
                    wins += 1.0

            if wins > best_wins:
                best_wins = wins
                best_move = move

        return best_move

    def _rollout(self, board: Board) -> str:
        """Play random moves until game ends or max plies reached."""
        for _ in range(self.max_plies):
            if board.game_over:
                break
            moves = board.legal_moves
            if not moves:
                break
            board.push(random.choice(moves))

        return board.result


# =============================================================================
# Higher-Order Agent Factories
# =============================================================================


def epsilon_greedy(agent: BaseAgent, epsilon: float = 0.1) -> BaseAgent:
    """
    Wrap an agent with epsilon-greedy exploration.

    With probability epsilon, plays a random move instead.
    Useful for training/exploration.
    """

    class EpsilonGreedyAgent(BaseAgent):
        def __init__(self):
            super().__init__(name=f"ε-{agent.name}")
            self.inner = agent
            self.epsilon = epsilon

        def select_move(self, board: Board) -> Move:
            if random.random() < self.epsilon:
                return random.choice(board.legal_moves)
            return self.inner.select_move(board)

    return EpsilonGreedyAgent()


# =============================================================================
# Demo: Benchmark Agents Against Each Other
# =============================================================================


def main():
    """Run a small benchmark comparing agents."""
    print("=" * 60)
    print("Custom Agents Demo")
    print("=" * 60)

    # Create agents and wrap as engines for benchmarking
    agents = [
        ("Random", AgentEngine(RandomAgent())),
        ("Greedy", GreedyAgent().as_engine()),
        ("Material", MaterialAgent().as_engine()),
        ("Positional", PositionalAgent().as_engine()),
    ]

    print("\nCreated agents:")
    for name, engine in agents:
        print(f"  - {name}: {engine.name}")

    # Quick benchmark: Greedy vs Random
    print("\n" + "-" * 60)
    print("Benchmark: Greedy vs Random (10 games)")
    print("-" * 60)

    stats = Benchmark(
        agents[1][1],  # Greedy
        agents[0][1],  # Random
        games=10,
    ).run()

    print(stats)

    # Benchmark: Material vs Greedy
    print("\n" + "-" * 60)
    print("Benchmark: Material vs Greedy (10 games)")
    print("-" * 60)

    stats = Benchmark(
        agents[2][1],  # Material
        agents[1][1],  # Greedy
        games=10,
    ).run()

    print(stats)

    # Quick game demonstration
    print("\n" + "-" * 60)
    print("Demo Game: Positional vs Random")
    print("-" * 60)

    board = Board()
    positional = PositionalAgent()
    random_agent = RandomAgent()

    move_count = 0
    while not board.game_over and move_count < 100:
        if board.turn == Color.WHITE:
            move = positional.select_move(board)
        else:
            move = random_agent.select_move(board)

        board.push(move)
        move_count += 1

    print(f"Game ended after {move_count} moves")
    print(f"Result: {board.result}")
    print(board)


if __name__ == "__main__":
    main()

