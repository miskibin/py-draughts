"""Generic PDN parsing tests for all draughts variants."""

import copy
import json
from pathlib import Path

import pytest

from draughts import AmericanBoard, Board, BrazilianBoard
from test._test_helpers import get_board

# Discover all variants that have random_pdns.json
GAMES_DIR = Path(__file__).parent / "games"
REGRESSIONS = json.loads((GAMES_DIR / "pdn_regressions.json").read_text())


@pytest.mark.parametrize("case", REGRESSIONS, ids=lambda case: case["name"])
def test_pdn_regression_fixtures(case):
    board_class = type(get_board(case["variant"]))
    if "error" in case:
        with pytest.raises(ValueError, match=case["error"]):
            board_class.from_pdn(case["pdn"])
        return

    board = board_class.from_pdn(case["pdn"])
    expected = board_class.from_fen(case["start_fen"]) if "start_fen" in case else board_class()
    for move in case["moves"]:
        expected.push_uci(move)

    assert board.fen == expected.fen
    assert len(board._moves_stack) == len(case["moves"])
    if not case.get("equivalent_route"):
        assert [str(move) for move in board._moves_stack] == [
            str(move) for move in expected._moves_stack
        ]


def test_draw_result_is_not_parsed_as_a_move():
    pdn = """[Event "Match om het wereldkampioenschap"]
[Result "1/2-1/2"]

1. 32-28 20-25 2. 37-32 15-20 3. 41-37 10-15 4. 46-41 5-10 5. 34-30 25x34 6.
39x30 20-25 7. 44-39 25x34 8. 40x29 18-23 9. 29x18 12x23 10. 35-30 7-12 11.
30-25 15-20 12. 31-27 17-21 13. 36-31 21-26 14. 41-36 12-18 15. 39-34 20-24
16. 49-44 1-7 17. 27-22 18x27 18. 31x22 24-29 19. 33x24 19x39 20. 44x33 14-19
21. 45-40 7-12 22. 50-45 2-7 23. 33-29 23x34 24. 40x29 12-18 25. 37-31 18x27
26. 31x22 7-12 27. 29-23 10-14 28. 43-39 11-17 29. 22x11 6x17 30. 42-37 17-22
31. 28x17 19x28 32. 32x23 12x21 33. 45-40 8-12 34. 40-34 12-17 35. 47-42 17-22
36. 37-31 26x37 37. 42x31 13-19 38. 23-18 22x13 39. 31-26 21-27 40. 26-21
19-23 41. 21x32 13-19 42. 34-30 14-20 43. 25x14 9x20 44. 30-25 20-24 45. 48-43
23-29 46. 39-33 29-34 47. 43-39 34x43 48. 38x49 19-23 49. 36-31 3-8 50. 31-27
23-29 1/2-1/2
"""

    board = Board.from_pdn(pdn)
    assert len(board._moves_stack) == 100


@pytest.mark.parametrize("result", ["0-0", "1.01-0.99", "1/2-1/2"])
def test_result_tags_and_trailers_are_not_moves(result):
    pdn = f'[Result "{result}"]\n1. 32-28 20-25 {result}'

    board = Board.from_pdn(pdn)
    assert [str(move) for move in board._moves_stack] == ["32-28", "20-25"]


def test_tags_comments_and_variations_do_not_supply_moves():
    pdn = '[Event "31-27"]\n1. 32-28 {31-27} (1. 31-27) 20-25'

    board = Board.from_pdn(pdn)
    assert [str(move) for move in board._moves_stack] == ["32-28", "20-25"]


def test_algebraic_tag_does_not_override_numeric_movetext():
    board = AmericanBoard.from_pdn('[Event "a3-b4"]\n1. 21-17')
    assert [str(move) for move in board._moves_stack] == ["21-17"]


def test_fen_tag_sets_initial_position():
    board = Board.from_pdn('[FEN "W:W31:B20"]\n1. 31-27')
    assert board.fen == '[FEN "B:W27:B20"]'


def test_algebraic_fen_from_lidraughts():
    # From the Brazilian PDNs in test/games/brazilian/random_pdns.json.
    fen = "W:Wa3,c3,e3,g3,b2,d2,f2,h2,a1,c1,e1,g1:Bb8,d8,f8,h8,a7,c7,e7,g7,b6,d6,f6,h6"
    board = BrazilianBoard.from_pdn(f'[FEN "{fen}"]\n1. c3-b4 b6-a5')
    expected = BrazilianBoard()
    expected.push_uci("22-17")
    expected.push_uci("9-13")
    assert board.fen == expected.fen


def test_spaced_captures_from_pdn_standard_example():
    # https://wiegerw.github.io/pdn/introduction.html (opening excerpt).
    pdn = "1.32-28 17-22 2.28 x17 11 x22 3.37-32 6-11"
    board = Board.from_pdn(pdn)
    assert len(board._moves_stack) == 6


def test_pdn_export_uses_international_results_and_fen():
    board = Board.from_fen("B:W31:B20")
    board.push_uci("20-25")
    pdn = board.pdn

    assert '[Result "*"]' in pdn
    assert '[FEN "B:W31:B20"]' in pdn
    assert "1... 20-25 *" in pdn
    assert Board.from_pdn(pdn).fen == board.fen


def test_pdn_export_maps_international_win():
    board = Board.from_fen("W:W:B20")
    assert board.result == "0-1"
    assert '[Result "0-2"]' in board.pdn


def test_pdn_export_after_copy():
    board = Board()
    board.push_uci("32-28")
    cloned = copy.deepcopy(board)
    assert Board.from_pdn(cloned.pdn).fen == board.fen

    current_position = board.copy()
    assert Board.from_pdn(current_position.pdn).fen == board.fen


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

    with open(pdn_file) as f:
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
            assert board_class.from_pdn(board.pdn).fen == board.fen
        except Exception as e:
            pytest.fail(f"Game {i} failed to parse: {e}\nPDN: {pdn[:300]}...")
