from abc import ABC, abstractmethod

import numpy as np
from tqdm import tqdm

from draughts.server import Server
from draughts.standard import Board, Move
from draughts.models import Color
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


class RandomEngine(Engine):
    def get_best_move(self, board: Board = None) -> tuple:
        return np.random.choice(list(board.legal_moves))


class MiniMaxEngine:
    """
    Simple minimax engine
    """

    def __init__(self, depth):
        self.depth = depth

    def evaluate(self, board: Board) -> int:
        return -board._pos.sum()

    def get_best_move(self, board: Board = None) -> tuple:
        best_move = None
        best_evaluation = -100 if board.turn == Color.WHITE else 100
        for move in board.legal_moves:
            board.push(move)
            evaluation = self.__minimax(board, self.depth)
            board.pop()
            if best_move is None or evaluation > best_evaluation:
                best_move = move
                best_evaluation = evaluation
        logger.info(f"best move: {move}, evaluation: {evaluation:.2f}")
        return move

    def __minimax(self, board: Board, depth: int) -> float:
        if board.game_over:
            return -100 if board.turn == Color.WHITE else 100
        if depth == 0:
            return self.evaluate(board)
        if board.turn == Color.WHITE:
            best_evaluation = -100
            for move in board.legal_moves:
                board.push(move)
                evaluation = self.__minimax(board, depth - 1)
                board.pop()
                best_evaluation = max(best_evaluation, evaluation)
            return best_evaluation
        else:
            best_evaluation = 100
            for move in board.legal_moves:
                board.push(move)
                evaluation = self.__minimax(board, depth - 1)
                board.pop()
                best_evaluation = min(best_evaluation, evaluation)
            return best_evaluation


class AlphaBetaEngine(Engine):
    def __init__(self, depth):
        self.depth = depth
        self.inspected_nodes = 0

    def evaluate(self, board: Board):
        return -board._pos.sum()

    def get_best_move(self, board: Board = None) -> tuple:
        self.inspected_nodes = 0
        move, evaluation = self.__get_engine_move(board)
        logger.debug(f"\ninspected  {self.inspected_nodes} nodes\n")
        logger.info(f"best move: {move}, evaluation: {evaluation:.2f}")
        return move

    def __get_engine_move(self, board: Board) -> tuple:
        depth = self.depth
        legal_moves = list(board.legal_moves)
        legal_moves.sort(key=lambda move: board.is_capture(move), reverse=True)
        # bar = tqdm(legal_moves)
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
            # bar.update(1)
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
            return -100 if board.turn == Color.WHITE else 100
        if depth == 0:
            self.inspected_nodes += 1
            return self.evaluate(board)
        legal_moves = list(board.legal_moves)
        legal_moves.sort(key=lambda move: board.is_capture(move), reverse=True)
        for move in legal_moves:
            board.push(move)
            evaluation = self.__alpha_beta_puring(board, depth - 1, alpha, beta)
            board.pop()
            if board.turn == Color.WHITE:
                alpha = max(alpha, evaluation)
            else:
                beta = min(beta, evaluation)
            if beta <= alpha:
                break
        return alpha if board.turn == Color.WHITE else beta


if __name__ == "__main__":
    board = Board()
    engine = AlphaBetaEngine(4)
    server = Server(board, get_best_move_method=engine.get_best_move)
    server.run()
