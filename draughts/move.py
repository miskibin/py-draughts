"""Move representation for draughts."""
from __future__ import annotations

from typing import Iterable


class Move:
    """
    Represents a move in draughts.

    A move consists of a sequence of squares visited, optionally with
    captured pieces. For simple moves, only start and end squares are recorded.
    For captures, all visited squares and captured piece positions are tracked.

    Attributes:
        square_list: List of 0-indexed square numbers visited during the move.
        captured_list: List of 0-indexed squares where pieces were captured.
        is_promotion: True if the move results in promotion to king.

    Example:
        >>> board = Board()
        >>> move = board.legal_moves[0]
        >>> print(move)  # "31-27"
        >>> print(move.square_list)  # [30, 26] (0-indexed)
    """

    __slots__ = ('square_list', 'captured_list', 'captured_entities', 'is_promotion',
                 'halfmove_clock', '_len', '_value', '_is_king_move')

    # Singleton empty list to avoid creating new empty lists for simple moves
    _EMPTY_LIST: list = []

    def __init__(
        self,
        visited_squares: list[int],
        captured_list: list[int] | None = None,
        captured_entities: list[int] | None = None,
        is_promotion: bool = False,
    ) -> None:
        """
        Create a move.

        Args:
            visited_squares: List of 0-indexed squares visited (start to end).
            captured_list: List of 0-indexed squares where pieces are captured.
            captured_entities: Piece types captured (for undo support).
            is_promotion: Whether the move results in promotion.
        """
        self.square_list = visited_squares
        self.captured_list = captured_list if captured_list else Move._EMPTY_LIST
        self.captured_entities = captured_entities if captured_entities else Move._EMPTY_LIST
        self.is_promotion = is_promotion
        self.halfmove_clock = 0
        self._len = len(captured_list) + 1 if captured_list else 1
        self._value = 0
        self._is_king_move = False

    def __str__(self) -> str:
        """Return UCI notation, e.g. '31-27' or '26x17'."""
        separator = "x" if self.captured_list else "-"
        return f"{self.square_list[0] + 1}{separator}{self.square_list[-1] + 1}"

    def __repr__(self) -> str:
        visited_squares = [str(s + 1) for s in self.square_list]
        return f"Move: {'->'.join(visited_squares)}"

    def __eq__(self, other: object) -> bool:
        """Check if two moves are equal (same start/end, compatible path)."""
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
        """Return number of squares visited."""
        return self._len

    def __add__(self, other: Move) -> Move:
        """Concatenate two moves (for multi-capture chains)."""
        if self.square_list[-1] != other.square_list[0]:
            raise ValueError(
                f"Cannot append moves {self} and {other}. "
                f"Last square of first move should equal first square of second move."
            )
        new_captured = self.captured_list + other.captured_list
        move = Move(
            self.square_list + other.square_list[1:],
            new_captured,
            self.captured_entities + other.captured_entities,
            self.is_promotion,
        )
        move._len = len(new_captured) + 1
        return move

    @classmethod
    def from_uci(cls, move: str, legal_moves: Iterable["Move"]) -> "Move":
        """
        Parse a move from UCI notation.

        Args:
            move: Move string in UCI format:

                - ``"24-19"`` for quiet moves
                - ``"24x19"`` for captures
                - ``"1x10x19"`` for multi-captures

            legal_moves: Iterable of legal moves to match against.

        Returns:
            The matching legal :class:`Move` object.

        Raises:
            ValueError: If the move format is invalid or move is illegal.

        Example:
            >>> move = Move.from_uci("31-27", board.legal_moves)
        """
        move = move.lower()
        if "-" in move:
            steps = move.split("-")
        elif "x" in move:
            steps = move.split("x")
        else:
            raise ValueError(f"Invalid move format: {move}")

        move_obj = Move([int(step) - 1 for step in steps])
        for legal_move in legal_moves:
            if legal_move == move_obj:
                return legal_move
        raise ValueError(
            f"{str(move_obj)} is correct format, but not legal in this position.\n"
            f"Legal moves: {list(map(str, legal_moves))}"
        )
