from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Generator, Literal, Optional
from typing import Type
import numpy as np

from draughts.models import FIGURE_REPR, Color, Figure, SquareT
from draughts.move import Move
from draughts.utils import (
    logger,
    get_diagonal_moves,
    get_short_diagonal_moves,
)

# fmt: off
SQUARES = [_, B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1] = range(33)
# fmt: on


class BaseBoard(ABC):
    """
    Abstact class for all draughts variants.

    .. important::
        All boards contain all methods from this class.

    Class is designed to support draughts boards of any size.
    By specifying the starting position, the user can create a board of any size.



    To create new variants of draughts, inherit from this class and:

    - override the ``legal_moves`` property
    - (optional) override the ``SQUARES`` list to match the new board size if you want to use UCI notation: ``[A1, B1, C1, ...]``
    - override the ``STARTING_POSITION`` to specify the starting position
    - override the ``STARTING_COLOR`` to specify the starting color

    Constraints:
    - There are only two colors:
        - ``Color.WHITE``
        - ``Color.BLACK``

    - There are only two types of pieces:
        - ``PieceType.MAN``
        - ``PieceType.KING``
    - **Board should always be square.**
    .. note::
        For generating legal moves use
    """

    halfmove_clock: int = 0
    """The number of half-moves since the last capture or pawn move."""

    GAME_TYPE = -1
    """
    PDN game type. See `PDN specification <https://en.wikipedia.org/wiki/Portable_Draughts_Notation>`_.
    """
    VARIANT_NAME = "Abstract variant"
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    ROW_IDX = ...
    """ 
    Dictionary of row indexes for every square. Generated only on module import. 
    Used to calculate legal moves.
    """

    COL_IDX = ...
    """
    Same as ``ROW_IDX`` but for columns.
    """

    STARTING_COLOR = Color.WHITE
    """
    Starting color. ``Color.WHITE`` or ``Color.BLACK``.
    """

    DIAGONAL_LONG_MOVES = ...
    """
    Dictionary of pseudo-legal moves for man pieces. Generated only on module import.
    Despite the name, this contains SHORT moves (first 2 squares) sufficient for men.
    
    **Structure:**
    ``[(right-up moves), (left-up moves), (right-down moves), (left-down moves)]``
    """
    DIAGONAL_SHORT_MOVES = ...
    """ 
    Dictionary of pseudo-legal moves for king pieces. Generated only on module import.
    Despite the name, this contains LONG moves (all squares on diagonal) for kings.
    (one for move and one for capture)
    """

    def __init_subclass__(cls, **kwargs):
        parent_class = cls.__bases__[0]
        parent_class_vars = vars(parent_class)
        child_class_vars = vars(cls)
        for var_name, var_value in child_class_vars.items():
            if var_name in parent_class_vars and not var_name.startswith("_"):
                setattr(parent_class, var_name, var_value)
        # Note: Names are intentionally swapped - DIAGONAL_SHORT_MOVES holds long moves (all squares)
        # because kings need to traverse entire diagonals, while DIAGONAL_LONG_MOVES holds short moves
        # (first 2 squares) which is sufficient for men who only move/capture one square at a time
        cls.DIAGONAL_SHORT_MOVES = get_diagonal_moves(len(cls.STARTING_POSITION))
        cls.DIAGONAL_LONG_MOVES = get_short_diagonal_moves(len(cls.STARTING_POSITION))

    def __init__(
        self,
        starting_position: Optional[np.ndarray] = None,
        turn: Optional[Color] = None,
    ) -> None:
        """
        Initializes the board with a starting position.
        The starting position must be a numpy array of length n * n/2,
        where n is the size of the board.

        """
        super().__init__()
        self._pos = (
            starting_position
            if starting_position is not None
            else self.STARTING_POSITION.copy()
        )
        self.turn = turn if turn is not None else self.STARTING_COLOR
        size = int(np.sqrt(len(self._pos) * 2))
        if size**2 != len(self._pos) * 2:
            msg = f"Invalid board with shape {self._pos.shape} provided.\
                Please use an array with lenght = (n * n/2). \
                Where n is an size of the board."
            logger.error(msg)
            raise ValueError(msg)
        self.shape = (size, size)
        self._moves_stack: list[Move] = []

        logger.info(f"Board initialized with shape {self.shape}.")

    @property
    @abstractmethod
    def legal_moves(self) -> Generator[Move, None, None]:
        """
        Return list legal moves for the current position.
        *For every concrete variant of draughts this method should be overriden.*

        .. warning::
            Depending of implementation method can return generator or list.


        """
        pass

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self._pos

    @property
    def is_threefold_repetition(self) -> bool:
        if len(self._moves_stack) >= 9:
            if (
                self._moves_stack[-1].square_list
                == self._moves_stack[-5].square_list
                == self._moves_stack[-9].square_list
            ):
                return True
        return False

    @property
    @abstractmethod
    def is_draw(self) -> bool:
        ...

    @property
    def game_over(self) -> bool:
        """Returns ``True`` if the game is over."""
        # check if threefold repetition

        return self.is_draw or not bool(list(self.legal_moves))

    def push(self, move: Move, is_finished: bool = True) -> None:
        """Pushes a move to the board.
        Automatically promotes a piece if it reaches the last row.

        If ``is_finished`` is set to ``True``, the turn is switched. This parameter is used only
        for generating legal moves.
        """
        move.halfmove_clock = self.halfmove_clock  # Before move occurs
        src, tg = (
            move.square_list[0],
            move.square_list[-1],
        )
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        # is promotion
        if (
            (tg // (self.shape[0] // 2)) == 0
            and self._pos[tg] == Figure.WHITE_MAN.value
            and is_finished
        ) or (
            (tg // (self.shape[0] // 2)) == (self.shape[0] - 1)
            and self._pos[tg] == Figure.BLACK_MAN.value
            and is_finished
        ):
            self._pos[tg] *= Figure.KING.value
            move.is_promotion = True
        elif (
            abs(self._pos[tg]) == Figure.KING.value
            and not move.captured_list
            and is_finished
        ):
            self.halfmove_clock += 1
        elif is_finished:
            self.halfmove_clock = 0
        if move.captured_list:
            self._pos[
                np.array([sq for sq in move.captured_list if sq != tg])
            ] = Figure.EMPTY
        self._moves_stack.append(move)
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK

    def pop(self, is_finished=True) -> Move:
        """Pops a move from the board.

        If ``is_finished`` is set to ``True``, the turn is switched. This parameter is used only
        for generating legal moves.
        """
        move = self._moves_stack.pop()
        src, tg = (
            move.square_list[0],
            move.square_list[-1],
        )
        if move.is_promotion:
            self._pos[tg] //= Figure.KING.value
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        self.halfmove_clock = move.halfmove_clock
        for sq, entity in zip(move.captured_list, move.captured_entities):
            self._pos[sq] = entity  # Dangerous line
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK
        return move

    def push_uci(self, str_move: str) -> None:
        """
        Allows to push a move from a string.

        * Converts string to ``Move`` object
        * calls ``BaseBoard.push`` method
        """
        try:
            move = Move.from_uci(str_move, self.legal_moves)
        except ValueError as e:
            logger.error(f"{e} \n {str(self)}")
            raise e
        self.push(move)

    @property
    def fen(self):
        """
        Returns a FEN string of the board position.

        ``[FEN "[Turn]:[Color 1][K][Square number][,]...]:[Color 2][K][Square number][,]...]"]``

        Fen examples:

        - ``[FEN "B:W18,24,27,28,K10,K15:B12,16,20,K22,K25,K29"]``
        - ``[FEN "B:W18,19,21,23,24,26,29,30,31,32:B1,2,3,4,6,7,9,10,11,12"]``
        """
        COLORS_REPR = {Color.WHITE: "W", Color.BLACK: "B"}
        fen_components = [
            f'[FEN "W:{COLORS_REPR[self.turn]}:W',
            ",".join(
                "K" * bool(self._pos[sq] < -1) + str(sq + 1)
                for sq in np.where(self.position < 0)[0]
            ),
            ":B",
            ",".join(
                "K" * bool(self._pos[sq] > 1) + str(sq + 1)
                for sq in np.where(self.position > 0)[0]
            ),
            '"]',
        ]
        return "".join(fen_components)

    @classmethod
    def from_fen(cls, fen: str) -> BaseBoard:
        """
        Creates a board from a FEN string by using regular expressions.
        """
        logger.debug(f"Initializing board from FEN: {fen}")
        fen = fen.upper()
        re_turn = re.compile(r"[WB]:")
        re_premove = re.compile(r"(G[0-9]+|P[0-9]+)(,|)")
        re_prefix = re.compile(r"[WB]:[WB]:[WB]")
        re_white = re.compile(r"W[0-9K,]+")
        re_black = re.compile(r"B[0-9K,]+")
        # remove premoves from fen
        # remove first 2 letters from prefix
        fen = re_premove.sub("", fen)
        prefix_match = re_prefix.search(fen)
        if prefix_match:
            prefix = prefix_match.group(0)
            fen = fen.replace(prefix, prefix[2:])
        try:
            turn_match = re_turn.search(fen)
            white_match = re_white.search(fen)
            black_match = re_black.search(fen)
            if not turn_match or not white_match or not black_match:
                raise AttributeError(f"Invalid FEN: {fen}")
            turn = turn_match.group(0)[0]
            white = white_match.group(0).replace("W", "")
            black = black_match.group(0).replace("B", "")
        except AttributeError as e:
            raise AttributeError(f"Invalid FEN: {fen} \n {e}")
        logger.debug(f"turn: {turn}, white: {white}, black: {black}")
        position = np.zeros(cls.STARTING_POSITION.shape, dtype=np.int8)
        if len(turn) != 1 or (len(white) == 0 and len(black) == 0):
            raise ValueError(f"Invalid FEN: {fen}")
        try:
            cls.__populate_from_list(white.split(","), Color.WHITE, position)
            cls.__populate_from_list(black.split(","), Color.BLACK, position)
        except ValueError as e:
            logger.error(f"Invalid FEN: {fen} \n {e}")
        turn_color = Color.WHITE if turn == "W" else Color.BLACK
        return cls(position, turn_color)

    @classmethod
    def __populate_from_list(cls, fen_list: list[str], color: Color, position: np.ndarray) -> None:
        board_range = range(1, position.shape[0] + 1)
        for sq in fen_list:
            if sq.isdigit() and int(sq) in board_range:
                position[int(sq) - 1] = color.value
            elif sq.startswith("K") and sq[1:].isdigit() and int(sq[1:]) in board_range:
                position[int(sq[1:]) - 1] = color.value * Figure.KING.value
            else:
                raise ValueError(
                    f"invalid square value: {sq} for board with length\
                        {position.shape[0]}"
                )

    @property
    def result(self) -> Literal["1/2-1/2", "1-0", "0-1", "-"]:
        """
        Returns a result of the game.
        """
        if self.is_draw:
            return "1/2-1/2"
        if self.turn == Color.WHITE and self.game_over:
            return "0-1"
        if self.turn == Color.BLACK and self.game_over:
            return "1-0"
        return "-"

    @property
    def friendly_form(self) -> np.ndarray:
        """
        Returns a board position in a friendly form.
        *Makes board with size n x n from a board with size n x n/2*
        """
        new_pos = [0]
        for idx, sq in enumerate(self.position):
            new_pos.extend([0] * (idx % (self.shape[0] // 2) != 0))
            new_pos.extend([0, 0] * (idx % self.shape[0] == 0 and idx != 0))
            new_pos.append(sq)
        new_pos.append(0)
        return np.array(new_pos)

    @property
    def pdn(self) -> str:
        """
        Returns a PDN string that represents the game.
        pdn - Portable Draughts Notation
        Example:
            ```
            [GameType "20"]
            [Variant "Standard (international) checkers"]
            [Result "-"]
            1. 34-29 17-21 2. 33-28 12-17 3. 38-33 21-26
            4. 29-24 20x27 5. 31x22 18x27
            ```
        """
        data = (
            f'[GameType "{self.GAME_TYPE}"]\n'
            f'[Variant "{self.VARIANT_NAME}"]\n'
            f'[Result "{self.result}"]\n'
        )
        history = []  # (number, white, black)
        for idx, move in enumerate(self._moves_stack):
            if idx % 2 == 0:
                history.append([(idx // 2) + 1, str(move)])
            else:
                history[-1].append(str(move))
        return (
            data
            + " ".join(f"{h[0]}. {' '.join(str(x) for x in h[1:])}" for h in history)
            + self.result * (len(self.result) - 1)
        )

    @staticmethod
    def is_capture(move: Move) -> bool:
        """
        Checks if a move is a capture.
        """
        return len(move.captured_list) > 0

    def __repr__(self) -> str:
        board = ""
        position = self.friendly_form
        for i in range(self.shape[0]):
            # board += f"{'-' * (self.shape[0]*4 + 1) }\n|"
            for j in range(self.shape[0]):
                board += f" {FIGURE_REPR[position[i*self.shape[0] + j]]}"
            board += "\n"
        return board

    def __iter__(self) -> Generator[Figure, None, None]:
        for sq in self.position:
            yield sq

    def __getitem__(self, key: SquareT) -> Figure:
        return self.position[key]
