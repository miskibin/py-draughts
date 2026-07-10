"""
Train a neural-network draughts player with py-draughts — in ~120 lines.

The idea (learn an evaluation function, then look one move ahead):

1. Let the built-in ``AlphaBetaEngine`` play games and, at every position,
   record how good the engine thinks that position is (its search score).
   That gives a pile of ``(board, score)`` examples.
2. Train a small network to copy that judgement: given a board, predict the
   score.  This *distils* the engine's hand-written evaluation into a net.
3. To play, the agent runs a small look-ahead search (negamax + alpha-beta)
   but scores the leaf positions with the network instead of a hand-written
   evaluation.  Learned evaluation + classic search = a strong, tiny player.

Everything runs on CPU in a couple of minutes.  We use American checkers
(8x8, 32 squares) because the smaller board trains fastest; swap the import
for ``draughts.boards.standard`` to train an International (10x10) net.

Run:  python examples/train_value_net.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger

from draughts import AlphaBetaEngine, BaseAgent, Benchmark
from draughts.boards.american import Board

logger.remove()  # silence the library's per-move info logging for a clean run

# --- knobs (kept small so it finishes fast on a laptop CPU) ------------------
SQUARES = Board.SQUARES_COUNT          # 32 for American checkers
TEACHER_DEPTH = 4                      # strength of the AlphaBeta teacher
GAMES = 150                            # self-play games to collect data from
EPOCHS = 20
EXPLORE = 0.25                         # chance to play a random move (for variety)
SCALE = 100.0                          # divides raw scores into a ~[-1, 1] range
SEED = 0

rng = np.random.default_rng(SEED)
torch.manual_seed(SEED)


class ValueNet(nn.Sequential):
    """A tiny MLP: board tensor in, one number out — how good is this position?"""

    def __init__(self, squares: int = SQUARES, hidden: int = 256):
        super().__init__(
            nn.Flatten(),                       # (4, squares) -> (4*squares,)
            nn.Linear(4 * squares, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, 1), nn.Tanh(),    # squashed to (-1, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return super().forward(x).squeeze(-1)


def collect_games() -> tuple[np.ndarray, np.ndarray]:
    """Play teacher games and record (board_tensor, engine_score) pairs.

    The score is from the side-to-move's point of view (positive = winning).
    """
    engine = AlphaBetaEngine(depth_limit=TEACHER_DEPTH)
    states, values = [], []
    for g in range(GAMES):
        board = Board()
        while not board.game_over:
            move, score = engine.get_best_move(board, with_evaluation=True)
            states.append(board.to_tensor())
            values.append(np.clip(score / SCALE, -1.0, 1.0))
            # Usually follow the engine, but sometimes wander off so the games
            # diverge and the net sees many different positions, not one line.
            moves = board.legal_moves
            board.push(moves[rng.integers(len(moves))] if rng.random() < EXPLORE else move)
        print(f"\r  self-play {g + 1}/{GAMES} games, {len(states)} positions", end="")
    print()
    return np.stack(states), np.array(values, dtype=np.float32)


def train(net: ValueNet, states: np.ndarray, values: np.ndarray) -> None:
    """Standard supervised regression: predict the engine's score (MSE loss)."""
    X, y = torch.from_numpy(states), torch.from_numpy(values)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for epoch in range(1, EPOCHS + 1):
        perm = torch.randperm(len(X))
        total = 0.0
        for i in range(0, len(X), 256):
            idx = perm[i : i + 256]
            loss = F.mse_loss(net(X[idx]), y[idx])
            opt.zero_grad(); loss.backward(); opt.step()
            total += loss.item() * len(idx)
        print(f"  epoch {epoch:2d}/{EPOCHS} | mse {total / len(X):.4f}")


class ValueAgent(BaseAgent):
    """Looks ``depth`` moves ahead, using the network to score leaf positions.

    ``depth=1`` is the simplest case — just score every immediate reply and
    take the best.  Larger depths run a normal negamax search (with alpha-beta
    pruning) but replace the usual hand-written evaluation with the network.
    More depth = stronger play, at the cost of more network calls per move.
    """

    def __init__(self, net: ValueNet, depth: int = 3):
        super().__init__(name=f"NeuralNet-{depth}ply")
        self.net = net.eval()
        self.depth = depth

    @torch.no_grad()
    def _value(self, board) -> float:
        """Network's score for ``board``, from the side-to-move's perspective."""
        return float(self.net(torch.from_numpy(board.to_tensor()).unsqueeze(0)))

    @torch.no_grad()
    def _search(self, board, depth: int, alpha: float, beta: float) -> float:
        if not board.legal_moves:
            return -1.0                        # side to move is stuck -> lost
        if depth == 0 or board.is_draw:
            return self._value(board)
        best = -2.0
        for move in board.legal_moves:
            nxt = board.copy()
            nxt.push(move)
            best = max(best, -self._search(nxt, depth - 1, -beta, -alpha))
            alpha = max(alpha, best)
            if alpha >= beta:                  # opponent won't allow this line
                break
        return best

    @torch.no_grad()
    def select_move(self, board):
        best_move, best_value = None, float("-inf")
        for move in board.legal_moves:
            nxt = board.copy()
            nxt.push(move)
            value = -self._search(nxt, self.depth - 1, float("-inf"), float("inf"))
            if value > best_value:
                best_move, best_value = move, value
        return best_move


class RandomAgent(BaseAgent):
    """Baseline: plays a uniformly random legal move."""

    def __init__(self):
        super().__init__(name="Random")

    def select_move(self, board):
        moves = board.legal_moves
        return moves[rng.integers(len(moves))]


if __name__ == "__main__":
    print("1. Collecting teacher games...")
    states, values = collect_games()

    print("2. Training the network...")
    net = ValueNet()
    train(net, states, values)

    model_path = Path(__file__).resolve().parent / "value_net_american.pt"
    torch.save(net.state_dict(), model_path)
    print(f"   saved -> {model_path}")

    print("3. How strong is it? (win rate, higher is better)")
    agent = ValueAgent(net, depth=3)
    vs_random = Benchmark(agent.as_engine(), RandomAgent().as_engine(),
                          board_class=Board, games=100).run()
    print(f"   vs Random:            {vs_random}")
    for depth in (2, 3):
        vs_ab = Benchmark(agent.as_engine(), AlphaBetaEngine(depth_limit=depth),
                          board_class=Board, games=50).run()
        print(f"   vs AlphaBeta(depth={depth}): {vs_ab}")
