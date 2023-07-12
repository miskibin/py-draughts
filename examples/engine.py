from draughts.standard import Board, Color


class AlphaBetaEngine:
    def __init__(self, depth):
        self.depth = depth

    def evaluate(self, board: Board):
        pos = board.position
        return -pos.sum()

    def get_move(self, board: Board):
        return self._alpha_beta(board, self.depth)[1]

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
    while not board.is_game_over:
        if board.turn == Color.WHITE:
            move = engine.get_move(board)
            board.push(move)
        else:
            move = input("Enter your move: ")
            try:
                board.push_from_str(move)
            except ValueError as e:
                print(e)
                move = input("Enter your move: ")
                board.push_from_str(move)

        print(board)
