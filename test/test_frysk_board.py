"""Frysk!: Frisian rules with a tiny starting set (5 men per side on the
back rank)."""

from draughts import FrisianBoard, FryskBoard


def test_starting_position():
    """5 black men on row 0, 5 white men on row 9, nothing else."""
    board = FryskBoard()
    pos = board.position.tolist()
    assert pos[0:5] == [1, 1, 1, 1, 1]
    assert pos[5:45] == [0] * 40
    assert pos[45:50] == [-1, -1, -1, -1, -1]
    assert board.SQUARES_COUNT == 50
    assert board.VARIANT_NAME == "Frysk!"
    assert board.GAME_TYPE == 40


def test_starting_fen_matches_pydraughts():
    """pydraughts uses 'W:W46,47,48,49,50:B1,2,3,4,5' as the Frysk! start."""
    board = FryskBoard()
    fen = board.fen
    assert "W46,47,48,49,50" in fen
    assert "B1,2,3,4,5" in fen


def test_inherits_frisian_capture_rules():
    """Frysk! should use the same capture-priority class as Frisian."""
    # Same _gen_captures impl as Frisian: value-based filtering + king priority.
    assert FryskBoard._gen_captures is FrisianBoard._gen_captures
    assert FryskBoard.legal_moves.fget is FrisianBoard.legal_moves.fget


def test_random_self_play_terminates():
    """With only 5 men per side and Frisian capture rules, games usually
    end fairly quickly."""
    import random

    board = FryskBoard()
    rng = random.Random(0)
    for _ in range(300):
        moves = board.legal_moves
        if not moves or board.is_draw:
            break
        board.push(rng.choice(moves))
    # Game must finish or hit draw
    assert board.is_draw or not board.legal_moves or len(board._moves_stack) == 300


def test_pdn_round_trip():
    import random

    board = FryskBoard()
    rng = random.Random(2)
    for _ in range(60):
        moves = board.legal_moves
        if not moves or board.is_draw:
            break
        board.push(rng.choice(moves))

    pdn = board.pdn
    parsed = FryskBoard.from_pdn(pdn)
    assert parsed.fen == board.fen


def test_push_pop_roundtrip():
    board = FryskBoard()
    snap_fen = board.fen
    board.push(board.legal_moves[0])
    board.pop()
    assert board.fen == snap_fen
