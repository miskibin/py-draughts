from __future__ import annotations

from typing import Iterable

from draughts.models import Figure


class Move:
    """Move representation.
    End user should never interact with this class directly.

    As we can read on wikipedia:

    *Multiple jumps, such as a double or triple jump,
    require you to pay attention, as the convention is
    to just show the start and end squares and not the
    in-between or intermediate squares. So the notation
    1-3 would mean a King does a double jump from 1 to 10 to 3.
    The intermediate square is only shown if there are two ways
    to jump and it would not be clear otherwise.*

    Note that always:
    n - number of visited squares (include source square)
    n - 2 - number of captured pieces
    """

    __slots__ = ('square_list', 'captured_list', 'captured_entities', 'is_promotion', 'halfmove_clock', '_len')
    
    # Singleton empty list to avoid creating new empty lists for simple moves
    _EMPTY_LIST: list = []
    
    def __init__(
        self,
        visited_squares: list[int],
        captured_list: list[int] | None = None,
        captured_entities: list[int] | None = None,
        is_promotion: bool = False,
    ) -> None:
        self.square_list = visited_squares
        # Use singleton empty list for non-captures (most common case)
        self.captured_list = captured_list if captured_list else Move._EMPTY_LIST
        self.captured_entities = captured_entities if captured_entities else Move._EMPTY_LIST
        self.is_promotion = is_promotion
        self.halfmove_clock = 0
        # Cache length - use direct len for captures, 1 for simple moves
        self._len = len(captured_list) + 1 if captured_list else 1

    def __str__(self) -> str:
        separator = "x" if self.captured_list else "-"
        return f"{self.square_list[0] + 1}{separator}{self.square_list[-1] + 1}"

    def __repr__(self) -> str:
        visited_squares = [str(s + 1) for s in self.square_list]
        return f"Move: {'->'.join(visited_squares)}"

    def __eq__(self, other: object) -> bool:
        """Check if two moves are equal. move created from string will have only visited squares definied."""
        if not isinstance(other, Move):
            return False

        if (
            self.square_list[0] == other.square_list[0]
            and self.square_list[-1] == other.square_list[-1]
        ):
            longer = (
                self.square_list
                if len(self.square_list) >= len(other.square_list)
                else other.square_list
            )
            shorter = (
                self.square_list
                if len(self.square_list) < len(other.square_list)
                else other.square_list
            )

            return all(square in longer for square in shorter)

        return False

    def __len__(self) -> int:
        return self._len

    def __add__(self, other: Move) -> Move:
        """Append moves"""
        if self.square_list[-1] != other.square_list[0]:
            raise ValueError(
                f"Cannot append moves {self} and {other}. Last square of first move should be equal to first square of second move."
            )
        new_captured = self.captured_list + other.captured_list
        move = Move(
            self.square_list + other.square_list[1:],
            new_captured,
            self.captured_entities + other.captured_entities,
            self.is_promotion,
        )
        # Directly set cached length for efficiency
        move._len = len(new_captured) + 1
        return move

    @classmethod
    def from_uci(cls, move: str, legal_moves: Iterable["Move"]) -> "Move":
        """

        Converts string representation of move to ``Move`` object.
        This is generic method, so it can be used for any board size. Therefore,
        For different context different move object will be generated.
        Also we need to pass legal moves, to understand given move and check if it is legal.


        input format:

        * ``<square_number>-<square_number>`` for simple move
        * ``<square_number>x<square_number>`` for capture

        Examples:

        * ``24-19`` - means from 24 to 19
        * ``24x19`` - means from 24 to 16 means capture of piece between 24 and 16
        * ``1x10x19`` - means capture of two pieces between 1 and 19

        """
        move = move.lower()
        if "-" in move:  # classic move
            steps = move.split("-")
        elif "x" in move:  # this means capture
            steps = move.split("x")
        else:
            raise ValueError(f"Invalid move {move}.")

        move_obj = Move([int(step) - 1 for step in steps])
        for legal_move in legal_moves:
            if legal_move == move_obj:
                return legal_move
        raise ValueError(
            f"{str(move_obj)} is correct, but not legal in given position.\n Legal moves are: {list(map(str,legal_moves))}"
        )
