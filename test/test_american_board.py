import numpy as np
import pytest

import draughts.boards.american as checkers
from draughts.boards.american import Board, Color, Move
from draughts.models import Figure


class TestAmericanBoard:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.board = Board()
        yield
        del self.board

    def test_move_from_str_method(self):
        legal_moves = self.board.legal_moves
        m1 = Move.from_uci("24-20", legal_moves)
        assert m1 == Move([checkers.G3, checkers.H4])

        with pytest.raises(ValueError):
            Move.from_uci("25-20", [])

    def test_push_from_string(self):
        m1 = Move.from_uci("24-20", self.board.legal_moves)
        self.board.push_uci("24-20")
        assert self.board.turn == Color.BLACK
        assert self.board.pop() == m1
        assert np.array_equal(self.board.position, Board.STARTING_POSITION)

    def test_capture(self):
        moves = ["24-20", "11-16", "20x11", "7x16"]
        for m in moves:
            self.board.push_uci(m)
        assert self.board[checkers.F6] == Figure.EMPTY.value


class TestAmericanRules:
    """Targeted coverage for the rule flags that make American distinct:
    forward-only men, short (non-flying) kings, and optional captures."""

    def _one_piece(self, squares):
        pos = np.zeros(32, dtype=np.int8)
        for sq, val in squares.items():
            pos[sq] = val
        return Board(pos, Color.WHITE)

    def test_man_cannot_capture_backward(self):
        # White man on E5 (14) with a black man behind it on F4 (18) and an empty
        # landing on G3 (22). A man captures forward only, so there is no capture.
        board = self._one_piece({checkers.E5: -1, checkers.F4: 1})
        assert not any(m.captured_list for m in board.legal_moves)

    def test_man_captures_forward(self):
        # Black man in front of the white man on F6 (10): forward capture exists.
        board = self._one_piece({checkers.E5: -1, checkers.F6: 1})
        caps = [m for m in board.legal_moves if m.captured_list]
        assert len(caps) == 1 and str(caps[0]) == "15x8"

    def test_king_captures_backward(self):
        # A king captures in every diagonal, so the same backward pattern that a
        # man may not take is legal for a king.
        board = self._one_piece({checkers.E5: -2, checkers.F4: 1})
        caps = [m for m in board.legal_moves if m.captured_list]
        assert len(caps) == 1 and caps[0].captured_list == [checkers.F4]

    def test_king_is_short_not_flying(self):
        # A lone king in the middle reaches only its four adjacent squares
        # (short king), never sliding multiple squares like a flying king.
        board = self._one_piece({checkers.E5: -2})
        dests = {m.square_list[-1] for m in board.legal_moves}
        assert dests == {checkers.D6, checkers.F6, checkers.D4, checkers.F4}

    def test_captures_are_optional(self):
        # With a forward capture available, simple non-capturing moves are still
        # offered: American does not force a capture.
        board = self._one_piece({checkers.E5: -1, checkers.F6: 1})
        assert any(m.captured_list for m in board.legal_moves)
        assert any(not m.captured_list for m in board.legal_moves)
