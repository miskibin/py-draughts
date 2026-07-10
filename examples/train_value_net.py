"""
Train a strong draughts value network with py-draughts, taught by a real engine.

The pipeline is the one used to train chess *NNUE* networks — and the lesson of
this example is that **data quality matters far more than network size**:

1. **Data.** A strong teacher (the Scan engine, via the Hub protocol) plays games
   from randomised openings. We keep only **quiet** positions — ones with no forced
   capture pending — together with the engine's evaluation and the game's eventual
   result, and we **deduplicate** them.
2. **Target.** Blend the squashed engine eval with the game result into a single
   WDL-style label in ``[-1, 1]``.
3. **Train** a small MLP to regress that label, with early stopping.
4. **Play** with a negamax + alpha-beta search that has **quiescence**: it never
   stops on a position with a pending capture, so leaves are always quiet — exactly
   the distribution the network was trained on. This single trick is worth several
   plies of strength.

Teacher: Scan 3.1 (10x10 International draughts) by Fabien Letouzey. Download
https://hjetten.home.xs4all.nl/scan/scan_31.zip, unzip it, and set the ``SCAN_EXE``
environment variable to the extracted ``scan.exe``. Without Scan the script falls
back to the built-in :class:`AlphaBetaEngine` (a weaker teacher, but it still runs).

Note on augmentation: unlike chess, a 10x10 draughts board has **no** left-right
mirror symmetry on its playable squares (reflecting the columns flips square colour,
landing pieces on non-playable squares). The only board symmetry is a 180° rotation,
which the side-to-move-relative board tensor already captures — so there is no free
spatial data augmentation to exploit here.

Run:  python examples/train_value_net.py
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger

from draughts import AlphaBetaEngine, BaseAgent, Benchmark, Color
from draughts.boards.standard import Board  # 10x10 International draughts

logger.remove()  # silence the library's per-move info logging for a clean run

# --- knobs -------------------------------------------------------------------
SCAN_EXE = os.environ.get("SCAN_EXE", "")   # path to Scan's scan.exe (see docstring)
GAMES = 1200                                 # teacher self-play games
MAX_OPENING = 10                             # up to this many random opening plies
EVAL_SCALE = 5.0                             # squash: tanh(score / EVAL_SCALE); tuned for Scan
RESULT_WEIGHT = 0.25                         # blend weight on the game result vs the eval
HIDDEN = 512
SEED = 0

rng = np.random.default_rng(SEED)
torch.manual_seed(SEED)
MODEL_PATH = Path(__file__).resolve().parent / "value_net_standard.pt"


class ValueNet(nn.Sequential):
    """A small MLP: board tensor in, one number out (how good for the side to move)."""

    def __init__(self, hidden: int = HIDDEN):
        super().__init__(
            nn.Flatten(),                        # (4, 50) -> (200,)
            nn.Linear(4 * 50, hidden), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, 1), nn.Tanh(),     # squashed to (-1, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return super().forward(x).squeeze(-1)


def make_teacher():
    """Return a strong teacher engine: Scan if available, else built-in AlphaBeta."""
    if SCAN_EXE and Path(SCAN_EXE).exists():
        from draughts.engines.hub import HubEngine

        eng = HubEngine(SCAN_EXE, time_limit=0.01)
        eng.set_variant("normal")
        eng.start()
        print(f"  teacher: {eng.info.name} {eng.info.version}")
        return eng
    print("  teacher: AlphaBetaEngine (Scan not found; set SCAN_EXE for a stronger net)")
    return AlphaBetaEngine(depth_limit=6)


def collect_data(teacher) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Self-play from random openings; return unique (tensor, eval, result) for quiet positions."""
    seen: set[bytes] = set()
    states, scores, results = [], [], []
    for g in range(GAMES):
        if hasattr(teacher, "new_game"):
            teacher.new_game()
        board = Board()
        for _ in range(int(rng.integers(2, MAX_OPENING + 1))):   # random opening
            if board.game_over:
                break
            moves = board.legal_moves
            board.push(moves[rng.integers(len(moves))])

        rows: list[tuple[int, int]] = []                         # (index, side to move)
        while not board.game_over:
            move, score = teacher.get_best_move(board, with_evaluation=True)
            if not board.legal_moves[0].captured_list:           # quiet position only
                key = board.to_tensor().tobytes()
                if key not in seen:
                    seen.add(key)
                    states.append(board.to_tensor())
                    scores.append(float(score))
                    rows.append((len(states) - 1, 1 if board.turn == Color.WHITE else -1))
            board.push(move)

        z = {"1-0": 1, "0-1": -1, "1/2-1/2": 0}.get(board.result, 0)
        results.extend([(i, z * side) for i, side in rows])      # result from side-to-move view
        print(f"\r  {g + 1}/{GAMES} games, {len(states)} unique quiet positions", end="")
    print()
    if hasattr(teacher, "quit"):
        teacher.quit()

    states = np.stack(states).astype(np.float32)
    scores = np.array(scores, dtype=np.float32)
    result = np.zeros(len(states), dtype=np.float32)
    for i, val in results:
        result[i] = val
    return states, scores, result


def train(net: ValueNet, states: np.ndarray, scores: np.ndarray, result: np.ndarray) -> None:
    """Regress the WDL-style target with early stopping on a held-out split."""
    target = (RESULT_WEIGHT * result + (1 - RESULT_WEIGHT) * np.tanh(scores / EVAL_SCALE)).astype(
        np.float32
    )
    X, y = torch.from_numpy(states), torch.from_numpy(target)
    perm = torch.randperm(len(X))
    X, y = X[perm], y[perm]
    n_val = max(3000, len(X) // 10)
    Xtr, ytr, Xva, yva = X[:-n_val], y[:-n_val], X[-n_val:], y[-n_val:]

    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=2e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=3)
    best_val, best_state, wait, patience = 1e9, None, 0, 8
    for epoch in range(1, 101):
        net.train()
        order = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), 512):
            idx = order[i : i + 512]
            loss = F.mse_loss(net(Xtr[idx]), ytr[idx])
            opt.zero_grad(); loss.backward(); opt.step()
        net.eval()
        with torch.no_grad():
            val = F.mse_loss(net(Xva), yva).item()
        sched.step(val)
        if val < best_val - 1e-4:
            best_val, best_state, wait = val, copy.deepcopy(net.state_dict()), 0
        else:
            wait += 1
        print(f"  epoch {epoch:3d} | val_mse {val:.4f} | best {best_val:.4f}")
        if wait >= patience:
            break
    net.load_state_dict(best_state)


class ValueAgent(BaseAgent):
    """Negamax + alpha-beta search with quiescence, scoring leaves with the network.

    Quiescence: forced-capture positions do not count against the depth budget and
    are never used as leaves, so every evaluated position is quiet — matching how the
    network was trained. ``depth`` trades strength for time (3 is a good default).
    """

    def __init__(self, net: ValueNet, depth: int = 3):
        super().__init__(name=f"NeuralNet-{depth}")
        self.net = net.eval()
        self.depth = depth

    @torch.no_grad()
    def _value(self, board) -> float:
        return float(self.net(torch.from_numpy(board.to_tensor()).unsqueeze(0)))

    @torch.no_grad()
    def _search(self, board, depth: int, alpha: float, beta: float) -> float:
        moves = board.legal_moves
        if not moves:
            return -1.0                                  # side to move has lost
        if board.is_draw:
            return 0.0
        quiet = not moves[0].captured_list
        if depth <= 0 and quiet:
            return self._value(board)
        next_depth = depth - 1 if quiet else depth       # quiescence: captures are "free"
        best = -2.0
        for move in moves:
            child = board.copy()
            child.push(move)
            best = max(best, -self._search(child, next_depth, -beta, -alpha))
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best

    @torch.no_grad()
    def select_move(self, board):
        best_move, best_value = None, float("-inf")
        for move in board.legal_moves:
            child = board.copy()
            child.push(move)
            value = -self._search(child, self.depth - 1, float("-inf"), float("inf"))
            if value > best_value:
                best_move, best_value = move, value
        return best_move


if __name__ == "__main__":
    print("1. Collecting teacher games...")
    states, scores, result = collect_data(make_teacher())

    print("2. Training the network...")
    net = ValueNet()
    train(net, states, scores, result)
    torch.save(net.state_dict(), MODEL_PATH)
    print(f"   saved -> {MODEL_PATH}")

    print("3. Strength vs the built-in engine (20 games each):")
    agent = ValueAgent(net, depth=3)
    for depth in (2, 4, 6):
        stats = Benchmark(
            agent.as_engine(), AlphaBetaEngine(depth_limit=depth), board_class=Board, games=20
        ).run()
        print(f"   vs AlphaBeta(depth={depth}): {stats}")
