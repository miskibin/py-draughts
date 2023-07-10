from easy_logs import get_logger
import numpy as np

logger = get_logger(lvl=10)


def _get_all_squares_at_the_diagonal(square: int, position_length: int) -> list[int]:
    """
    [[up-right], [down-right], [up-left], [down-left]]
    It was hard to write, so it should be hard to read.
    No comment for you.
    """
    size = int(np.sqrt(position_length * 2))
    row_idx = {val: val // (size // 2) for val in range(position_length + 1)}
    result = []
    squares, sq = [], square

    while (sq) % 10 != 4 and sq >= (size // 2):  # up right
        sq = (sq - 5) + (row_idx[sq] + 1) % 2
        squares.append(sq)
    result.append(list(squares))
    squares, sq = [], square
    while (sq) % 10 != 4 and sq < 45:  # down right
        sq = sq + 6 - (row_idx[sq]) % 2
        squares.append(sq)
    result.append(list(squares))
    squares, sq = [], square
    while (sq) % 10 != 5 and sq >= (size // 2):  # up left
        sq = (sq - 6) + (row_idx[sq] + 1) % 2
        squares.append(sq)
    result.append(list(squares))
    squares, sq = [], square
    while (sq) % 10 != 5 and sq < 45:  # down left
        sq = sq + 5 - (row_idx[sq]) % 2
        squares.append(sq)
    result.append(list(squares))
    return result


def get_king_pseudo_legal_moves(position_length: int) -> dict[list]:
    squares = {}
    for sq in range(position_length):
        squares[sq] = _get_all_squares_at_the_diagonal(sq, position_length)
    return squares


def get_man_pseudo_legal_moves(position_length: int) -> dict[list]:
    squares = {}
    for sq in range(position_length):
        squares[sq] = [
            moves[:2] for moves in _get_all_squares_at_the_diagonal(sq, position_length)
        ]
    return squares
