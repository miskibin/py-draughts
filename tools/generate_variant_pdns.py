"""
Generate self-play PDN game corpora for variants where lidraughts/PDN
archives are not directly accessible.

Each game is played by selecting random legal moves until a result is reached
or a ply limit is hit. Each PDN is round-tripped through ``BoardClass.from_pdn``
before being written, so the corpus is guaranteed to be parseable.

Usage:
    python tools/generate_variant_pdns.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from draughts import (
    AntidraughtsBoard,
    BrazilianBoard,
    BreakthroughBoard,
    FryskBoard,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = REPO_ROOT / "test" / "games"

VARIANTS = {
    "brazilian": BrazilianBoard,
    "antidraughts": AntidraughtsBoard,
    "breakthrough": BreakthroughBoard,
    "frysk": FryskBoard,
}

GAMES_PER_VARIANT = 25
MAX_PLIES = 200


def play_one_game(board_cls, seed: int) -> str:
    rng = random.Random(seed)
    board = board_cls()
    for _ in range(MAX_PLIES):
        moves = board.legal_moves
        if not moves or board.is_draw:
            break
        board.push(rng.choice(moves))
    pdn = board.pdn
    # Round-trip parse to guarantee the corpus is valid.
    parsed = board_cls.from_pdn(pdn)
    assert len(parsed._moves_stack) == len(board._moves_stack), (
        f"Round-trip mismatch for {board_cls.__name__} seed={seed}"
    )
    return pdn


def generate_for_variant(name: str, board_cls) -> None:
    out_dir = GAMES_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    games = []
    seed = 0
    while len(games) < GAMES_PER_VARIANT:
        try:
            pdn = play_one_game(board_cls, seed)
        except Exception as e:
            print(f"  seed={seed} failed: {e}")
            seed += 1
            continue
        # Skip games with no moves at all - they're not useful as test fixtures.
        if "1." not in pdn:
            seed += 1
            continue
        games.append(pdn)
        seed += 1
    out_path = out_dir / "random_pdns.json"
    out_path.write_text(json.dumps({"pdn_positions": games}, ensure_ascii=False, indent=2))
    print(f"{name}: wrote {len(games)} games -> {out_path.relative_to(REPO_ROOT)}")


def main() -> None:
    for name, board_cls in VARIANTS.items():
        generate_for_variant(name, board_cls)


if __name__ == "__main__":
    main()
