import numpy as np
from easy_logs import get_logger
from collections import defaultdict

logger = get_logger(lvl=10)


def _get_all_squares_at_the_diagonal(square: int, position_length: int) -> list[list[int]]:
    """
    [[up-right],  [up-left],[down-right], [down-left]]
    It was hard to write, so it should be hard to read.
    No comment for you.
    """
    size = int(np.sqrt(position_length * 2))
    row_idx = {val: val // (size // 2) for val in range(position_length + 1)}
    result: list[list[int]] = []
    squares, sq = [], square

    while (sq) % size != ((size // 2) - 1) and sq >= (size // 2):  # up right
        sq = (sq - (size // 2)) + (row_idx[sq] + 1) % 2
        squares.append(sq)
    result.append(list(squares))
    squares, sq = [], square

    while (sq) % size != (size // 2) and sq >= (size // 2):  # up left
        sq = (sq - ((size // 2) + 1)) + (row_idx[sq] + 1) % 2
        squares.append(sq)
    result.append(list(squares))
    squares, sq = [], square

    while (sq) % size != ((size // 2) - 1) and sq < position_length - (
        size // 2
    ):  # down right
        sq = sq + ((size // 2) + 1) - (row_idx[sq]) % 2
        squares.append(sq)
    result.append(list(squares))
    squares, sq = [], square

    while (sq) % size != (size // 2) and sq < position_length - (
        size // 2
    ):  # down left
        sq = sq + (size // 2) - (row_idx[sq]) % 2
        squares.append(sq)
    result.append(list(squares))
    return result


def get_diagonal_moves(position_length: int) -> dict[int, list[list[int]]]:
    squares: dict[int, list[list[int]]] = {}
    for sq in range(position_length):
        squares[sq] = _get_all_squares_at_the_diagonal(sq, position_length)
    return squares


def get_short_diagonal_moves(position_length: int) -> dict[int, list[list[int]]]:
    squares = {}
    for sq in range(position_length):
        squares[sq] = [
            moves[:2] for moves in _get_all_squares_at_the_diagonal(sq, position_length)
        ]
    return squares


def get_vertical_and_horizontal_moves(position_length: int) -> dict:
    """
    [sq_number]: [up, right, down, left]
    """
    size = int(np.sqrt(position_length * 2))
    row_idx = {val: val // (size // 2) for val in range(position_length + 1)}
    squares = defaultdict(list)

    for sq in range(position_length):
        row_squares = [val for val, idx in row_idx.items() if idx == row_idx[sq]]
        idx = row_squares.index(sq)
        squares[sq] = [
            list(range(sq, -1, -size))[1:],  # Up
            row_squares[idx + 1 :],  # Right
            list(range(sq, position_length, size))[1:],  # Down
            row_squares[:idx],  # Left
        ]
    return squares


def get_short_vertical_and_horizontal_moves(position_length: int) -> dict[int, list[list[int]]]:
    return {
        sq: [moves[:4] for moves in list_of_sq]
        for sq, list_of_sq in get_vertical_and_horizontal_moves(position_length).items()
    }
