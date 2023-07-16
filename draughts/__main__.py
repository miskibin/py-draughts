if __name__ == "__main__":
    from draughts.server import Server
    from draughts.engine import AlphaBetaEngine
    from draughts import get_board

    board = get_board("standard")
    engine = AlphaBetaEngine(5)
    server = Server(board, get_best_move_method=engine.get_best_move)
    server.run()
