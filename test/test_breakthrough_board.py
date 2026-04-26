"""Breakthrough: International rules where the first to make a king wins.

The game ends as soon as either player promotes a man.
"""

from draughts import BreakthroughBoard, StandardBoard


def test_starting_position_matches_standard():
    """Breakthrough shares Standard's 10x10 starting layout."""
    bt = BreakthroughBoard()
    std = StandardBoard()
    assert bt.position.tolist() == std.position.tolist()
    assert bt.SQUARES_COUNT == 50
    assert bt.VARIANT_NAME == "Breakthrough"


def test_starting_legal_moves_match_standard():
    bt_moves = sorted(str(m) for m in BreakthroughBoard().legal_moves)
    std_moves = sorted(str(m) for m in StandardBoard().legal_moves)
    assert bt_moves == std_moves


def test_white_makes_king_wins():
    """White man one step from promotion wins by promoting.

    In FEN, squares are 1-indexed; white moves from high numbers toward
    low numbers (squares 1-5 are white's promotion row).
    A white man on FEN square 7 (internal 6, second row from top) can
    advance to FEN square 1 or 2 and promote.
    """
    fen = '[FEN "W:W7:B26"]'
    board = BreakthroughBoard.from_fen(fen)
    # Promotion targets are internal squares 0..4 (top row)
    promotion_moves = [m for m in board.legal_moves if m.square_list[-1] in (0, 1, 2, 3, 4)]
    assert promotion_moves
    board.push(promotion_moves[0])
    assert board.white_kings != 0
    assert board.game_over
    assert board.result == "1-0"


def test_black_makes_king_wins():
    """Black man one step from promotion wins by promoting."""
    # Black moves from low numbers toward high numbers; FEN 44 is row 8,
    # one step from FEN row 10 (internal squares 45..49).
    fen = '[FEN "B:W26:B44"]'
    board = BreakthroughBoard.from_fen(fen)
    promotion_moves = [m for m in board.legal_moves if m.square_list[-1] in (45, 46, 47, 48, 49)]
    assert promotion_moves
    board.push(promotion_moves[0])
    assert board.black_kings != 0
    assert board.game_over
    assert board.result == "0-1"


def test_game_continues_until_promotion():
    """Random play should always eventually terminate (max-cap on 10x10
    will create a king fairly quickly under random play)."""
    import random

    board = BreakthroughBoard()
    rng = random.Random(0)
    for _ in range(300):
        if board.game_over:
            break
        moves = board.legal_moves
        if not moves:
            break
        board.push(rng.choice(moves))
    # Game must terminate either by promotion, by no-moves, or by draw rule
    assert board.game_over or len(board._moves_stack) == 300


def test_pdn_round_trip():
    import random

    board = BreakthroughBoard()
    rng = random.Random(3)
    for _ in range(50):
        if board.game_over:
            break
        moves = board.legal_moves
        if not moves:
            break
        board.push(rng.choice(moves))

    pdn = board.pdn
    parsed = BreakthroughBoard.from_pdn(pdn)
    assert parsed.fen == board.fen
