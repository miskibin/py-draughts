from draughts.standard import Board, Color, Move
from draughts.server import Server
from abc import ABC, abstractmethod
from draughts.utils import logger
from tqdm import tqdm


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
    def __init__(self, depth):
        self.depth = depth
        self.inspected_nodes = 0

    def evaluate(self, board: Board):
        pos = board.position
        return -pos.sum()

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
        if depth == 0:
            self.inspected_nodes += 1
            return self.evaluate(board)
        legal_moves = list(board.legal_moves)
        legal_moves.sort(key=lambda move: board.is_capture(move), reverse=True)
        for move in legal_moves:
            board.push(move)
            evaluation = self.__alpha_beta_puring(board, depth - 1, alpha, beta)
            board.pop()
            if board.turn:
                alpha = max(alpha, evaluation)
            else:
                beta = min(beta, evaluation)
            if beta <= alpha:
                break
        return alpha if board.turn else beta


if __name__ == "__main__":
    board = Board()
    engine = AlphaBetaEngine(2)
    server = Server(board=board, get_best_move_method=engine.get_best_move)
    server.run()
