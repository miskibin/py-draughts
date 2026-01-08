"""Generic PDN parsing tests for all draughts variants."""
import json
from pathlib import Path

import pytest

from draughts import get_board


# Discover all variants that have random_pdns.json
GAMES_DIR = Path(__file__).parent / "games"


def get_pdn_test_variants():
    """Find all variants with random_pdns.json files."""
    variants = []
    for variant_dir in GAMES_DIR.iterdir():
        if variant_dir.is_dir():
            pdn_file = variant_dir / "random_pdns.json"
            if pdn_file.exists():
                variants.append(variant_dir.name)
    return variants


@pytest.mark.parametrize("variant", get_pdn_test_variants())
def test_games_from_pdns(variant: str):
    """Test that random PDN games can be parsed and replayed for each variant."""
    pdn_file = GAMES_DIR / variant / "random_pdns.json"
    
    with open(pdn_file, "r") as f:
        data = json.load(f)
    
    # Support both "games" and "pdn_positions" keys for flexibility
    pdns = data.get("games") or data.get("pdn_positions") or []
    
    board_class = type(get_board(variant))
    
    for i, pdn in enumerate(pdns):
        try:
            board = board_class.from_pdn(pdn)
            # Verify the game produced at least some moves (unless it's just headers)
            # Some PDNs might just be headers without moves
            if "1." in pdn:
                assert len(board._moves_stack) > 0, f"Game {i}: No moves parsed from PDN with moves"
        except Exception as e:
            pytest.fail(f"Game {i} failed to parse: {e}\nPDN: {pdn[:300]}...")

