from abc import ABC, abstractmethod

import numpy as np
from tqdm import tqdm

from draughts.models import Color
from draughts.standard import Board, Figure, Move
from draughts.utils import logger


class Engine(ABC):
    """
    Interface for engine compatible with Server class.
    """

    @abstractmethod
    def get_best_move(self, board: Board) -> Move:
        """
        Returns best move for given board.
        It could be random move, or move calculated by some algorithm.

        to get list of legal moves use ``board.legal_moves``
        """
        ...


class AlphaBetaEngine(Engine):
    """
    Engine using alpha-beta puring algorithm.
    *Alpha-beta puring is a minimax algorithm with optimization. Algorithm
    will not inspect nodes that are worse than already inspected nodes.
    Additionaly, this engine will inspect capture moves first.
    Usually, those moves are better than non-capture moves.*
    """

    def __init__(self, depth):
        """
        ``depth`` - how many moves will be inspected by engine.
        Bigger depth means better moves, but also longer calculation time.
        """
        self.depth = depth
        self.inspected_nodes = 0

    def evaluate(self, board: Board):
        """
        Simple evaluation function for given board.
        """
        return -board._pos.sum()

    def get_best_move(
        self, board: Board = None, with_evaluation: bool = False
    ) -> tuple:
        self.inspected_nodes = 0
        move, evaluation = self.__get_engine_move(board)
        logger.debug(f"\ninspected  {self.inspected_nodes} nodes\n")
        logger.info(f"best move: {move}, evaluation: {evaluation:.2f}")
        if with_evaluation:
            return move, evaluation
        return move

    def __get_engine_move(self, board: Board) -> tuple:
        depth = self.depth
        legal_moves = list(board.legal_moves)
        bar = tqdm(legal_moves)
        evals = []
        alpha, beta = -100, 100

        for move in legal_moves:
            board.push(move)
            evals.append(
                self.__alpha_beta_puring(
                    board,
                    depth - 1,
                    alpha,
                    beta,
                )
            )
            board.pop()

            bar.update(1)
            if board.turn == Color.WHITE:
                alpha = max(alpha, evals[-1])
            else:
                beta = min(beta, evals[-1])
        index = (
            evals.index(max(evals))
            if board.turn == Color.WHITE
            else evals.index(min(evals))
        )
        return legal_moves[index], evals[index]

    def __alpha_beta_puring(
        self, board: Board, depth: int, alpha: float, beta: float
    ) -> float:
        if board.game_over:
            if not board.is_draw:
                return -100 if board.turn == Color.WHITE else 100
            return -0.2 if board.turn == Color.WHITE else 0.2
        if depth == 0:
            self.inspected_nodes += 1
            return self.evaluate(board)
        legal_moves = list(board.legal_moves)
        tmp = board._pos.copy().sum()

        for move in legal_moves:
            board.push(move)
            evaluation = self.__alpha_beta_puring(board, depth - 1, alpha, beta)
            evaluation -= np.abs(board.position[move.square_list[-1]]) == Figure.KING
            board.pop()
            if board._pos.sum() != tmp:
                logger.warning(str(board))
                logger.error(f"{move}")
                break
            if board.turn == Color.WHITE:
                alpha = max(alpha, evaluation)
            else:
                beta = min(beta, evaluation)
            if beta <= alpha:
                break
        return alpha if board.turn == Color.WHITE else beta
