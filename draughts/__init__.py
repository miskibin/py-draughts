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
A draughts library with advanced (customizable) WEB UI move generation and validation,
PDN parsing and writing. Supports multiple variants of game.
"""
from typing import Literal, Optional, Type
import sys
from loguru import logger

__version__ = "1.5.8"

# Remove default stderr handler (id=0) - users can add their own with logger.add(sys.stderr)
try:
    logger.remove(0)
except ValueError:
    pass  # Already removed

# create board type
from draughts.boards.base import BaseBoard
from draughts.boards.standard import Board as StandardBoard
from draughts.boards.frisian import Board as FrisianBoard
from draughts.boards.american import Board as AmericanBoard
from draughts.server.server import Server
from draughts import svg
from draughts.models import Color, Figure
from draughts.move import Move
from draughts.engines.hub import HubEngine


def get_board(
    variant: Literal["standard", "american", "frisian"], fen: Optional[str] = None
) -> BaseBoard:
    """
    Board factory method.
    - ``standard`` - standard draughts board
    - ``american`` - american checkers board
    - ``frisian`` - frisian draughts board
    """

    BOARDS: dict[str, Type[BaseBoard]] = {
        "standard": StandardBoard,
        "frisian": FrisianBoard,  # type: ignore[type-abstract]
        "american": AmericanBoard,
    }
    board_cls = BOARDS[variant]
    if fen:
        return board_cls.from_fen(fen)
    return board_cls()
