from draughts.standard import Board, Color
from draughts.server import Server


class AlphaBetaEngine:
    def __init__(self, depth):
        self.depth = depth

    def evaluate(self, board: Board):
        pos = board.position
        return -pos.sum()

    def get_move(self, board: Board):
        (evaluation, move) = self._alpha_beta(board, self.depth)
        print(evaluation, move)
        return move

    def _alpha_beta(self, board: Board, depth, alpha=-100, beta=100, color=Color.WHITE):
        if depth == 0 or board.is_game_over:
            return self.evaluate(board), None

        best_move = None
        if color == Color.WHITE:
            for move in board.legal_moves:
                board.push(move)
                score = self._alpha_beta(board, depth - 1, alpha, beta, Color.BLACK)[0]
                board.pop()
                if score > alpha:
                    alpha = score
                    best_move = move
                if alpha >= beta:
                    break
            return alpha, best_move
        else:
            for move in board.legal_moves:
                board.push(move)
                score = self._alpha_beta(board, depth - 1, alpha, beta, Color.WHITE)[0]
                board.pop()
                if score < beta:
                    beta = score
                    best_move = move
                if alpha >= beta:
                    break
            return beta, best_move


if __name__ == "__main__":
    board = Board()
    engine = AlphaBetaEngine(5)
    server = Server(board=board, get_best_move_method=engine.get_move)
    server.run()
