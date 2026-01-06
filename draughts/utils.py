import numpy as np
from collections import defaultdict
from typing import NamedTuple


class AttackEntry(NamedTuple):
    """Pre-computed attack info for a square in a direction."""
    target: int       # Move target (adjacent empty square)
    jump_over: int    # Square to jump over for capture
    land_on: int      # Landing square after capture


def generate_man_attack_tables(position_length: int) -> tuple[dict, dict]:
    """
    Generate pre-computed attack tables for men pieces.
    
    Returns:
        white_attacks: dict[square, list[AttackEntry]] - for white men (moving up)
        black_attacks: dict[square, list[AttackEntry]] - for black men (moving down)
    """
    diagonal_moves = get_short_diagonal_moves(position_length)
    
    white_attacks: dict[int, list[AttackEntry]] = {}
    black_attacks: dict[int, list[AttackEntry]] = {}
    
    for square in range(position_length):
        directions = diagonal_moves[square]
        # directions: [up-right, up-left, down-right, down-left]
        
        white_attacks[square] = []
        black_attacks[square] = []
        
        # White moves up (directions 0, 1)
        for dir_idx in [0, 1]:  # up-right, up-left
            d = directions[dir_idx]
            if len(d) >= 1:
                target = d[0]
                jump_over = d[0] if len(d) >= 2 else -1
                land_on = d[1] if len(d) >= 2 else -1
                white_attacks[square].append(AttackEntry(target, jump_over, land_on))
        
        # Black moves down (directions 2, 3)
        for dir_idx in [2, 3]:  # down-right, down-left
            d = directions[dir_idx]
            if len(d) >= 1:
                target = d[0]
                jump_over = d[0] if len(d) >= 2 else -1
                land_on = d[1] if len(d) >= 2 else -1
                black_attacks[square].append(AttackEntry(target, jump_over, land_on))
        
        # Both colors can capture in all 4 directions
        for dir_idx in range(4):
            d = directions[dir_idx]
            if len(d) >= 2:
                # Add capture-only entries for backward captures
                if dir_idx in [2, 3]:  # backward for white
                    jump_over = d[0]
                    land_on = d[1]
                    white_attacks[square].append(AttackEntry(-1, jump_over, land_on))
                if dir_idx in [0, 1]:  # backward for black
                    jump_over = d[0]
                    land_on = d[1]
                    black_attacks[square].append(AttackEntry(-1, jump_over, land_on))
    
    return white_attacks, black_attacks


def generate_king_attack_tables(position_length: int) -> dict[int, list[list[int]]]:
    """
    Generate pre-computed diagonal lines for kings.
    Kings can move along entire diagonals, so we store the full diagonal for each direction.
    
    Returns:
        dict[square, list[list[int]]] - for each square, 4 lists of squares in each diagonal direction
    """
    return get_diagonal_moves(position_length)


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
