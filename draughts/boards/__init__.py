"""Board implementations for various draughts variants."""

from draughts.boards.american import Board as AmericanBoard
from draughts.boards.antidraughts import Board as AntidraughtsBoard
from draughts.boards.base import BaseBoard
from draughts.boards.brazilian import Board as BrazilianBoard
from draughts.boards.breakthrough import Board as BreakthroughBoard
from draughts.boards.frisian import Board as FrisianBoard
from draughts.boards.frysk import Board as FryskBoard
from draughts.boards.russian import Board as RussianBoard
from draughts.boards.standard import Board as StandardBoard

__all__ = [
    "BaseBoard",
    "StandardBoard",
    "AmericanBoard",
    "FrisianBoard",
    "RussianBoard",
    "BrazilianBoard",
    "AntidraughtsBoard",
    "BreakthroughBoard",
    "FryskBoard",
]
