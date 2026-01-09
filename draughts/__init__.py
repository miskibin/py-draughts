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
py-draughts: A fast draughts library with move generation, validation, and AI.

Supports Standard (International), American, Frisian, and Russian variants.
"""
import sys
from loguru import logger

__version__ = "1.5.8"

# Remove default stderr handler (id=0) - users can add their own with logger.add(sys.stderr)
try:
    logger.remove(0)
except ValueError:
    pass  # Already removed

# Board classes
from draughts.boards.base import BaseBoard
from draughts.boards.standard import Board as StandardBoard
from draughts.boards.frisian import Board as FrisianBoard
from draughts.boards.american import Board as AmericanBoard
from draughts.boards.russian import Board as RussianBoard

# Convenience alias - Board = StandardBoard (most common variant)
Board = StandardBoard

# Server
from draughts.server.server import Server

# Core types
from draughts import svg
from draughts.models import Color, Figure
from draughts.move import Move

# Engines
from draughts.engines.hub import HubEngine
from draughts.engines.alpha_beta import AlphaBetaEngine
from draughts.engines.engine import Engine

__all__ = [
    # Boards
    'BaseBoard',
    'Board',
    'StandardBoard',
    'FrisianBoard',
    'AmericanBoard',
    'RussianBoard',
    # Engines
    'Engine',
    'AlphaBetaEngine',
    'HubEngine',
    # Core
    'Color',
    'Figure',
    'Move',
    'Server',
    'svg',
]
