# This file is part of the py-draughts library.
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
A draughts library with advenced (customizable) WEB UI move generation and validation,
PDN parsing and writing. Supports multiple variants of game.
"""

from typing import Literal
from draughts.standard import Board as StandardBoard
from draughts.american import Board as AmericanBoard
from draughts.base import BaseBoard

__version__ = "1.0.3"
__author__ = "Michał Skibiński"


def get_board(variant: Literal["standard", "american"]) -> BaseBoard:
    """
    Board factory method.
    - ``standard`` - standard draughts board
    - ``american`` - american checkers board
    """
    BOARDS = {
        "standard": StandardBoard,
        "american": AmericanBoard,
    }
    return BOARDS[variant]
