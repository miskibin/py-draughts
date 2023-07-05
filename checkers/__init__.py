# This file is part of the fast-checkers library.
# Copyright (C) 2023-2023 Michał Skibiński
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
A checkers library for Python, with move generation and validation,
PDN parsing and writing. Supprots multiple variants of game.
"""
# fmt: off

SQUARES = [
    _, B10, D10, F10, H10, J10,
    A9, C9, E9, G9, I9,
    B8, D8, F8, H8, J8,
    A7, C7, E7, G7, I7,
    B6, D6, F6, H6, J6,
    A5, C5, E5, G5, I5,
    B4, D4, F4, H4, J4,
    A3, C3, E3, G3, I3,
    B2, D2, F2, H2, J2,
    A1, C1, E1, G1, I1
    ] = range(51)


""" 8x8 Board"""
T8X8 = [_, B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1] = range(33)

# fmt: on
"""10x10 Board """
T10X10 = {val: idx for idx, val in enumerate(SQUARES)}

from checkers.american_board import AmericanBoard
from checkers.models import Move