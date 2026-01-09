"""
Reinforcement Learning Example - Eval-Based Training.
Uses AlphaBetaEngine.get_eval() for dense reward signal.
"""
import random
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
except ImportError:
    print("pip install torch")
    exit(1)

from draughts import Color, AlphaBetaEngine
from draughts.boards.american import Board
from draughts.benchmark import Benchmark


class PolicyNet(nn.Module):
    """Larger network: 4 hidden layers, 512 units each."""
    def __init__(self, sq=32, h=512):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(4*sq, h), nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(h, h), nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(h, h), nn.ReLU(),
            nn.Linear(h, h), nn.ReLU(),
        )
        self.pi = nn.Linear(h, sq*sq)
    
    def forward(self, x):
        return self.pi(self.net(x))


class NNEngine:
    """Wrap neural net as Engine for benchmarking."""
    name = "NeuralNet"
    depth_limit = time_limit = None
    
    def __init__(self, net): self.net = net
    
    def get_best_move(self, board):
        with torch.no_grad():
            logits = self.net(torch.from_numpy(board.to_tensor()).unsqueeze(0))
            logits[0][~torch.from_numpy(board.legal_moves_mask())] = -1e9
            return board.index_to_move(logits[0].argmax().item())


def collect_eval_data(engine: AlphaBetaEngine, n_games=200):
    """Collect (state, action, eval) from engine self-play."""
    data = []
    for _ in range(n_games):
        board = Board()
        while not board.game_over:
            state = board.to_tensor()
            move, eval = engine.get_best_move(board, with_evaluation=True)
            if isinstance(move, tuple): move = move[0]
            action = board.move_to_index(move)
            # Get engine eval for this position (from current player's perspective)
            data.append((state, action, -eval))
            board.push(move)
    return data


def train_epoch(net, opt, data, batch_size=128):
    """Train with cross-entropy + eval-weighted loss."""
    random.shuffle(data)
    total_loss, correct, total = 0, 0, 0
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        states = torch.from_numpy(np.stack([d[0] for d in batch]))
        actions = torch.tensor([d[1] for d in batch])
        evals = torch.tensor([d[2] for d in batch], dtype=torch.float32)
        
        # Weight by absolute eval - focus on important positions
        weights = (evals.abs() / 100).clamp(0.5, 2.0)
        
        logits = net(states)
        loss = (F.cross_entropy(logits, actions, reduction='none') * weights).mean()
        
        opt.zero_grad(); loss.backward(); opt.step()
        
        total_loss += loss.item() * len(batch)
        correct += (logits.argmax(1) == actions).sum().item()
        total += len(batch)
    
    return total_loss / total, correct / total * 100


def rl_train_step(net, opt, engine, n_games=20, temp=0.5):
    """RL training using engine eval as reward."""
    all_data = []
    
    for _ in range(n_games):
        board = Board()
        game_steps = []
        while not board.game_over:
            state = board.to_tensor()
            logits = net(torch.from_numpy(state).unsqueeze(0))[0]
            mask = torch.from_numpy(board.legal_moves_mask())
            logits[~mask] = -1e9
            probs = F.softmax(logits / temp, dim=0)
            action = torch.multinomial(probs, 1).item()
            
            # Get eval BEFORE making move (from current player's view)
            ev_before = engine.evaluate(board)
            board.push(board.index_to_move(action))
            # Get eval AFTER making move (flip sign for opponent's view)
            ev_after = -engine.evaluate(board) if not board.game_over else 0
            
            # Reward = improvement in position
            reward = (ev_after - ev_before) / 100.0  # Normalize
            game_steps.append((state, action, reward))
        
        all_data.extend(game_steps)
    
    if not all_data:
        return 0.0
    
    states = torch.from_numpy(np.stack([d[0] for d in all_data]))
    actions = torch.tensor([d[1] for d in all_data])
    rewards = torch.tensor([d[2] for d in all_data])
    rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
    
    logits = net(states)
    log_p = F.log_softmax(logits, dim=1).gather(1, actions.unsqueeze(1)).squeeze(1)
    entropy = -(F.softmax(logits, dim=1) * F.log_softmax(logits, dim=1)).sum(1).mean()
    loss = -(log_p * rewards).mean() - 0.01 * entropy
    
    opt.zero_grad(); loss.backward()
    torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
    return loss.item()


@torch.no_grad()
def eval_vs(net, opponent, n=100):
    """Evaluate net vs opponent."""
    w, l, d = 0, 0, 0
    for i in range(n):
        board = Board()
        as_white = i % 2 == 0
        while not board.game_over:
            if (board.turn == Color.WHITE) == as_white:
                logits = net(torch.from_numpy(board.to_tensor()).unsqueeze(0))[0]
                logits[~torch.from_numpy(board.legal_moves_mask())] = -1e9
                board.push(board.index_to_move(logits.argmax().item()))
            else:
                move = opponent.get_best_move(board)
                if isinstance(move, tuple): move = move[0]
                board.push(move)
        won = (board.result == "1-0") == as_white
        lost = (board.result == "0-1") == as_white
        if won: w += 1
        elif lost: l += 1
        else: d += 1
    return w, l, d


def train():
    engine = AlphaBetaEngine(depth_limit=4)
    net = PolicyNet()
    best_wr, best_state = 0, None
    
    # Phase 1: Supervised Learning from engine moves + evals
    print("Phase 1: Learning from AlphaBeta(depth=4) moves + evals")
    print("=" * 65)
    print("Collecting training data with evaluations...")
    data = collect_eval_data(engine, n_games=300)
    print(f"Collected {len(data)} (state, action, eval) tuples")
    
    opt = optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-5)
    sched = optim.lr_scheduler.StepLR(opt, 20, 0.5)
    
    print(f"\n{'Ep':>4} | {'Loss':>8} | {'Acc':>6} | {'Eval W/L/D':>12} | {'WR%':>5}")
    print("-" * 55)
    
    for ep in range(1, 61):
        loss, acc = train_epoch(net, opt, data)
        sched.step()
        if ep % 5 == 0:
            ew, el, ed = eval_vs(net, engine, n=100)
            wr = ew
            if wr > best_wr:
                best_wr = wr
                best_state = {k: v.clone() for k, v in net.state_dict().items()}
            marker = " *" if wr == best_wr else ""
            print(f"{ep:4d} | {loss:8.4f} | {acc:5.1f}% | {ew:3d}/{el:3d}/{ed:3d} | {wr:4d}%{marker}")
    
    # Phase 2: RL Fine-tuning with eval-based rewards
    print("\nPhase 2: RL Fine-tuning (eval-based rewards)")
    print("=" * 65)
    opt = optim.Adam(net.parameters(), lr=3e-5, weight_decay=1e-5)
    print(f"{'Ep':>4} | {'Loss':>8} | {'Eval W/L/D':>12} | {'WR%':>5}")
    print("-" * 45)
    
    for ep in range(1, 81):
        temp = max(0.3, 0.8 - ep / 100)
        loss = rl_train_step(net, opt, engine, n_games=30, temp=temp)
        if ep % 10 == 0:
            ew, el, ed = eval_vs(net, engine, n=100)
            wr = ew
            if wr > best_wr:
                best_wr = wr
                best_state = {k: v.clone() for k, v in net.state_dict().items()}
            marker = " *" if wr == best_wr else ""
            print(f"{ep:4d} | {loss:+8.4f} | {ew:3d}/{el:3d}/{ed:3d} | {wr:4d}%{marker}")
    
    print(f"\nBest win rate vs engine: {best_wr}%")
    
    if best_state:
        net.load_state_dict(best_state)
        torch.save(best_state, "best_draughts_model.pt")
        print("Saved best model to best_draughts_model.pt")
    
    return net


if __name__ == "__main__":
    net = train()
    
    print("\n" + "=" * 60)
    print("Final Benchmark: NeuralNet vs AlphaBeta(depth=2)")
    print(Benchmark(NNEngine(net), AlphaBetaEngine(depth_limit=2), board_class=Board, games=20).run())