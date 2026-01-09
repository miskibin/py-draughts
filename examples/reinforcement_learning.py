"""
Reinforcement Learning Example for py-draughts.
A2C with improvements: bigger network, LR schedule, reward shaping.
"""
import random
from dataclasses import dataclass
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
except ImportError:
    print("pip install torch")
    exit(1)

from draughts import Color, BaseAgent
from draughts.boards.american import Board


class ActorCritic(nn.Module):
    def __init__(self, num_sq=32, hidden=256):  # Bigger network
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(), 
            nn.Linear(4*num_sq, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden // 2), nn.ReLU(),  # Extra layer
        )
        self.policy = nn.Linear(hidden // 2, num_sq * num_sq)
        self.value = nn.Linear(hidden // 2, 1)
    
    def forward(self, x):
        f = self.net(x)
        return self.policy(f), self.value(f).squeeze(-1)


@dataclass
class Step:
    state: np.ndarray
    action: int
    reward: float = 0.0


def count_pieces(board):
    """Count pieces for each side."""
    tensor = board.to_tensor()
    white = tensor[0].sum() + tensor[1].sum() * 2  # men + kings*2
    black = tensor[2].sum() + tensor[3].sum() * 2
    return white, black


@torch.no_grad()
def play_game(net, temp=1.0):
    """Play game with reward shaping for captures."""
    board = Board()
    white, black = [], []
    prev_w_pieces, prev_b_pieces = count_pieces(board)
    
    while not board.game_over:
        state = board.to_tensor()
        x = torch.from_numpy(state).unsqueeze(0)
        logits, _ = net(x)
        logits = logits.squeeze(0)
        
        mask = torch.from_numpy(board.legal_moves_mask())
        logits[~mask] = -1e9
        
        probs = F.softmax(logits / temp, dim=0)
        action = torch.multinomial(probs, 1).item()
        
        current_turn = board.turn
        step = Step(state, action)
        (white if current_turn == Color.WHITE else black).append(step)
        
        board.push(board.index_to_move(action))
        
        # Reward shaping: small reward for capturing pieces
        w_pieces, b_pieces = count_pieces(board)
        if current_turn == Color.WHITE:
            capture_reward = (prev_b_pieces - b_pieces) * 0.1  # Reward for capturing
            if white: white[-1].reward += capture_reward
        else:
            capture_reward = (prev_w_pieces - w_pieces) * 0.1
            if black: black[-1].reward += capture_reward
        prev_w_pieces, prev_b_pieces = w_pieces, b_pieces
    
    # Final rewards
    if board.result == "1-0":
        if white: white[-1].reward += 1.0
        if black: black[-1].reward -= 1.0
    elif board.result == "0-1":
        if white: white[-1].reward -= 1.0
        if black: black[-1].reward += 1.0
    
    return white + black, board.result


def compute_returns(steps, gamma=0.99):
    returns = []
    G = 0.0
    for s in reversed(steps):
        G = s.reward + gamma * G
        returns.insert(0, G)
    return torch.tensor(returns, dtype=torch.float32)


def train_batch(net, opt, steps, ent_coef=0.02):  # Higher entropy
    if not steps:
        return 0.0
    
    states = torch.from_numpy(np.stack([s.state for s in steps]))
    actions = torch.tensor([s.action for s in steps])
    returns = compute_returns(steps)
    
    logits, values = net(states)
    
    log_probs = F.log_softmax(logits, dim=1)
    action_log_probs = log_probs.gather(1, actions.unsqueeze(1)).squeeze(1)
    
    probs = F.softmax(logits, dim=1)
    entropy = -(probs * log_probs).sum(dim=1).mean()
    
    adv = returns - values.detach()
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)
    
    policy_loss = -(action_log_probs * adv).mean()
    value_loss = F.mse_loss(values, returns)
    loss = policy_loss + 0.5 * value_loss - ent_coef * entropy
    
    opt.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
    opt.step()
    
    return loss.item()


@torch.no_grad()
def evaluate(net, n=30):
    wins = 0
    for i in range(n):
        board = Board()
        is_white = i % 2 == 0
        while not board.game_over:
            if (board.turn == Color.WHITE) == is_white:
                x = torch.from_numpy(board.to_tensor()).unsqueeze(0)
                logits, _ = net(x)
                mask = torch.from_numpy(board.legal_moves_mask())
                logits[0][~mask] = -1e9
                move = board.index_to_move(logits[0].argmax().item())
            else:
                move = random.choice(board.legal_moves)
            board.push(move)
        if (board.result == "1-0" and is_white) or (board.result == "0-1" and not is_white):
            wins += 1
    return wins / n * 100


def train(episodes=300, games=20, lr_start=3e-3, lr_end=1e-4):
    print("A2C Training (improved)")
    print("-" * 40)
    
    net = ActorCritic()
    opt = optim.Adam(net.parameters(), lr=lr_start)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(opt, episodes, eta_min=lr_end)
    
    w, l, d = 0, 0, 0
    best = 0
    
    for ep in range(1, episodes + 1):
        temp = max(0.3, 1.0 - 0.8 * (ep / episodes))  # 1.0 -> 0.3
        
        all_steps = []
        for _ in range(games):
            steps, result = play_game(net, temp)
            all_steps.extend(steps)
            if result == "1-0": w += 1
            elif result == "0-1": l += 1
            else: d += 1
        
        loss = train_batch(net, opt, all_steps)
        scheduler.step()
        
        lr = scheduler.get_last_lr()[0]
        print(f"Ep {ep:3d} | L: {loss:+.3f} | T: {temp:.2f} | LR: {lr:.1e} | {w}/{l}/{d}", flush=True)
        
        if ep % 30 == 0:
            wr = evaluate(net)
            if wr > best:
                best = wr
                print(f"      ** Eval: {wr:.0f}% (best!)", flush=True)
            else:
                print(f"      Eval: {wr:.0f}%", flush=True)
    
    print(f"\nBest: {best:.0f}%")
    return net


if __name__ == "__main__":
    net = train(episodes=150, games=15)
    
    print("\nDemo game:")
    board = Board()
    n = 0
    while not board.game_over and n < 100:
        n += 1
        if board.turn == Color.WHITE:
            with torch.no_grad():
                x = torch.from_numpy(board.to_tensor()).unsqueeze(0)
                logits, _ = net(x)
                mask = torch.from_numpy(board.legal_moves_mask())
                logits[0][~mask] = -1e9
                move = board.index_to_move(logits[0].argmax().item())
        else:
            move = random.choice(board.legal_moves)
        print(f"{n}. {move}")
        board.push(move)
    print(f"Result: {board.result}")
