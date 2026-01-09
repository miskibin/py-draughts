"""
Simple Reinforcement Learning Example for py-draughts.

This example demonstrates training a neural network agent using 
REINFORCE (policy gradient) with self-play.

Requirements:
    pip install torch

Run:
    python examples/reinforcement_learning.py

The trained agent learns by:
1. Playing games against itself (self-play)
2. Collecting (state, action, reward) trajectories
3. Updating the policy to favor winning moves

This is a minimal example - for stronger agents consider:
- Larger networks, residual blocks
- Monte Carlo Tree Search (AlphaZero-style)
- Value networks for better credit assignment
- Experience replay, parallel self-play
"""
import random
from collections import deque
from dataclasses import dataclass

import numpy as np

# Check for torch
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
except ImportError:
    print("This example requires PyTorch. Install with: pip install torch")
    exit(1)

from draughts import Board, Color, Move, BaseAgent, AgentEngine, Benchmark, AlphaBetaEngine


# =============================================================================
# Neural Network Policy
# =============================================================================


class PolicyNetwork(nn.Module):
    """
    Simple policy network for draughts.
    
    Input: 4-channel board tensor (own_men, own_kings, opp_men, opp_kings)
    Output: Logits over all possible moves (from_sq * 50 + to_sq = 2500)
    """
    
    def __init__(self, num_squares: int = 50, hidden_size: int = 256):
        super().__init__()
        self.num_squares = num_squares
        num_actions = num_squares * num_squares  # 2500 for 10x10
        
        # Simple MLP (for better results, use CNN or transformer)
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(4 * num_squares, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, num_actions),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning logits."""
        return self.net(x)
    
    def get_action_probs(self, board: Board) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Get action probabilities for a board position.
        
        Returns:
            probs: Probability distribution over legal moves
            mask: Boolean tensor of legal move indices
        """
        # Convert board to tensor
        state = torch.from_numpy(board.to_tensor()).unsqueeze(0)  # (1, 4, 50)
        
        # Get logits
        logits = self.forward(state).squeeze(0)  # (2500,)
        
        # Mask illegal moves
        mask = torch.from_numpy(board.legal_moves_mask())
        logits[~mask] = float('-inf')
        
        # Softmax to get probabilities
        probs = F.softmax(logits, dim=0)
        
        return probs, mask
    
    def select_action(self, board: Board, temperature: float = 1.0) -> tuple[Move, int, float]:
        """
        Sample an action from the policy.
        
        Args:
            board: Current board state
            temperature: Higher = more exploration, lower = more exploitation
            
        Returns:
            move: The selected Move object
            action_idx: Index of the action (for training)
            log_prob: Log probability of the action (for REINFORCE)
        """
        probs, mask = self.get_action_probs(board)
        
        # Apply temperature
        if temperature != 1.0:
            logits = torch.log(probs + 1e-10) / temperature
            logits[~mask] = float('-inf')
            probs = F.softmax(logits, dim=0)
        
        # Sample action
        dist = torch.distributions.Categorical(probs)
        action_idx = dist.sample()
        log_prob = dist.log_prob(action_idx)
        
        # Convert index to move
        move = board.index_to_move(action_idx.item())
        
        return move, action_idx.item(), log_prob


# =============================================================================
# RL Agent Wrapper
# =============================================================================


class RLAgent(BaseAgent):
    """Agent that uses a trained policy network."""
    
    def __init__(self, policy: PolicyNetwork, temperature: float = 0.1):
        super().__init__(name="RLAgent")
        self.policy = policy
        self.temperature = temperature
    
    def select_move(self, board: Board) -> Move:
        with torch.no_grad():
            move, _, _ = self.policy.select_action(board, self.temperature)
        return move


# =============================================================================
# Training Data
# =============================================================================


@dataclass
class Transition:
    """Single step in a game."""
    log_prob: torch.Tensor
    reward: float = 0.0


class GameBuffer:
    """Collects transitions from self-play games."""
    
    def __init__(self):
        self.games: list[list[Transition]] = []
        self.current_game: list[Transition] = []
    
    def add_step(self, log_prob: torch.Tensor):
        """Add a step to current game."""
        self.current_game.append(Transition(log_prob=log_prob))
    
    def end_game(self, result: str, our_color: Color):
        """
        End current game and assign rewards.
        
        Rewards:
            +1 for winning
            -1 for losing  
             0 for draw
        """
        if not self.current_game:
            return
        
        # Determine reward from our perspective
        if result == "1/2-1/2":
            reward = 0.0
        elif (result == "1-0" and our_color == Color.WHITE) or \
             (result == "0-1" and our_color == Color.BLACK):
            reward = 1.0
        else:
            reward = -1.0
        
        # Assign reward to final step (sparse reward)
        # For better credit assignment, use discounted returns
        self.current_game[-1].reward = reward
        
        self.games.append(self.current_game)
        self.current_game = []
    
    def compute_returns(self, gamma: float = 0.99) -> tuple[list[torch.Tensor], list[float]]:
        """
        Compute discounted returns for all steps.
        
        Returns:
            log_probs: List of log probabilities
            returns: List of discounted returns
        """
        all_log_probs = []
        all_returns = []
        
        for game in self.games:
            # Compute returns backwards
            G = 0.0
            returns = []
            for step in reversed(game):
                G = step.reward + gamma * G
                returns.insert(0, G)
            
            for step, ret in zip(game, returns):
                all_log_probs.append(step.log_prob)
                all_returns.append(ret)
        
        return all_log_probs, all_returns
    
    def clear(self):
        self.games = []
        self.current_game = []


# =============================================================================
# Self-Play Training
# =============================================================================


def self_play_game(policy: PolicyNetwork, temperature: float = 1.0, max_moves: int = 200):
    """
    Play a game of self-play, collecting training data.
    
    Both players use the same policy network.
    """
    board = Board()
    buffer = GameBuffer()
    
    # Track which color we're collecting data for (alternate)
    collect_color = Color.WHITE
    
    for _ in range(max_moves):
        if board.game_over:
            break
        
        # Select action
        move, action_idx, log_prob = policy.select_action(board, temperature)
        
        # Only collect for one color (to avoid correlated samples)
        if board.turn == collect_color:
            buffer.add_step(log_prob)
        
        board.push(move)
    
    # End game and assign rewards
    buffer.end_game(board.result, collect_color)
    
    return buffer, board.result


def train_step(policy: PolicyNetwork, optimizer: optim.Optimizer, buffer: GameBuffer):
    """
    Perform one training step using REINFORCE.
    
    Loss = -sum(log_prob * return)
    
    This encourages actions that lead to positive returns.
    """
    log_probs, returns = buffer.compute_returns()
    
    if not log_probs:
        return 0.0
    
    # Normalize returns (variance reduction)
    returns = torch.tensor(returns)
    if len(returns) > 1:
        returns = (returns - returns.mean()) / (returns.std() + 1e-8)
    
    # REINFORCE loss
    loss = 0.0
    for log_prob, G in zip(log_probs, returns):
        loss -= log_prob * G
    
    # Backprop
    optimizer.zero_grad()
    loss.backward()
    
    # Gradient clipping (stabilizes training)
    torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
    
    optimizer.step()
    
    return loss.item()


# =============================================================================
# Main Training Loop
# =============================================================================


def train(
    num_episodes: int = 1000,
    games_per_batch: int = 10,
    lr: float = 1e-3,
    temperature_start: float = 1.0,
    temperature_end: float = 0.1,
    eval_interval: int = 100,
    eval_games: int = 10,
):
    """
    Train a policy network via self-play.
    
    Args:
        num_episodes: Total training episodes
        games_per_batch: Games to play before each update
        lr: Learning rate
        temperature_start: Initial exploration temperature
        temperature_end: Final exploitation temperature
        eval_interval: Episodes between evaluations
        eval_games: Games to play during evaluation
    """
    print("=" * 60)
    print("Reinforcement Learning Training")
    print("=" * 60)
    
    # Initialize
    policy = PolicyNetwork()
    optimizer = optim.Adam(policy.parameters(), lr=lr)
    
    # Stats
    wins, losses, draws = 0, 0, 0
    recent_results = deque(maxlen=100)
    
    for episode in range(1, num_episodes + 1):
        # Anneal temperature
        progress = episode / num_episodes
        temperature = temperature_start + (temperature_end - temperature_start) * progress
        
        # Collect batch of games
        batch_buffer = GameBuffer()
        
        for _ in range(games_per_batch):
            game_buffer, result = self_play_game(policy, temperature)
            batch_buffer.games.extend(game_buffer.games)
            
            # Track stats
            if result == "1-0":
                wins += 1
                recent_results.append(1)
            elif result == "0-1":
                losses += 1
                recent_results.append(-1)
            else:
                draws += 1
                recent_results.append(0)
        
        # Train on batch
        loss = train_step(policy, optimizer, batch_buffer)
        
        # Log progress
        if episode % 10 == 0:
            win_rate = (sum(1 for r in recent_results if r == 1) / len(recent_results) * 100) if recent_results else 0
            print(f"Episode {episode:4d} | Loss: {loss:7.3f} | "
                  f"Temp: {temperature:.2f} | Win%: {win_rate:.1f}% | "
                  f"W/L/D: {wins}/{losses}/{draws}")
        
        # Evaluate against random
        if episode % eval_interval == 0:
            evaluate(policy, eval_games)
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    
    return policy


def evaluate(policy: PolicyNetwork, num_games: int = 10):
    """Evaluate trained policy against a baseline."""
    print("\n--- Evaluation vs Random ---")
    
    # Create agents
    rl_agent = RLAgent(policy, temperature=0.1)
    
    class RandomAgent:
        def select_move(self, board):
            return random.choice(board.legal_moves)
    
    # Quick benchmark
    stats = Benchmark(
        rl_agent.as_engine(),
        AgentEngine(RandomAgent(), name="Random"),
        games=num_games,
    ).run()
    
    print(f"vs Random: {stats.e1_wins}W-{stats.e2_wins}L-{stats.draws}D "
          f"(Win rate: {stats.e1_win_rate*100:.1f}%)")
    print()


# =============================================================================
# Demo: Play Against Trained Agent
# =============================================================================


def demo_game(policy: PolicyNetwork):
    """Play a demo game showing the trained agent."""
    print("\n" + "=" * 60)
    print("Demo Game: Trained Agent (White) vs Random (Black)")
    print("=" * 60)
    
    board = Board()
    rl_agent = RLAgent(policy, temperature=0.1)
    
    move_num = 0
    while not board.game_over and move_num < 100:
        move_num += 1
        
        if board.turn == Color.WHITE:
            move = rl_agent.select_move(board)
            player = "RL"
        else:
            move = random.choice(board.legal_moves)
            player = "Random"
        
        print(f"{move_num:3d}. {player:6s}: {move}")
        board.push(move)
    
    print(f"\nResult: {board.result}")
    print(board)


# =============================================================================
# Entry Point
# =============================================================================


if __name__ == "__main__":
    # Train for a short demo (increase num_episodes for better results)
    policy = train(
        num_episodes=200,      # Increase to 1000+ for real training
        games_per_batch=5,
        lr=1e-3,
        temperature_start=1.0,
        temperature_end=0.2,
        eval_interval=50,
        eval_games=10,
    )
    
    # Play a demo game
    demo_game(policy)
    
    print("\n" + "=" * 60)
    print("Tips for Better Results:")
    print("=" * 60)
    print("""
1. Train longer (num_episodes=5000+)
2. Use a CNN instead of MLP for spatial patterns
3. Add a value network (Actor-Critic)
4. Use MCTS for action selection (AlphaZero-style)
5. Implement experience replay
6. Train against stronger opponents (curriculum)
7. Add entropy bonus for exploration
8. Use larger hidden layers (512+)
""")

