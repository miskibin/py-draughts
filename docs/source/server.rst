Server
======

Web interface for playing draughts games interactively.

.. autoclass:: draughts.Server
    :members: __init__, run

Quick Start
-----------

.. code-block:: python

    from draughts import Board, Server, AlphaBetaEngine

    board = Board()
    server = Server(
        board=board,
        white_engine=AlphaBetaEngine(depth_limit=6),
        black_engine=AlphaBetaEngine(depth_limit=4)
    )
    server.run()  # Open http://localhost:8000

Command Line
~~~~~~~~~~~~

Start directly from terminal::

    python -m draughts.server.server

Engine Matches
--------------

Pit engines against each other::

    from draughts import Board, Server, AlphaBetaEngine, Engine
    import random

    class RandomEngine(Engine):
        def get_best_move(self, board, with_evaluation=False):
            move = random.choice(list(board.legal_moves))
            return (move, 0.0) if with_evaluation else move

    server = Server(
        board=Board(),
        white_engine=AlphaBetaEngine(depth_limit=6),
        black_engine=RandomEngine()
    )
    server.run()

Click "Auto Play" in the UI to watch the match.

Web UI Controls
---------------

- **Engine Move**: Play best move for current side
- **Auto Play**: Start/stop automatic engine play
- **Undo**: Take back the last move
- **Copy/Load FEN**: Import/export positions
- **Copy/Load PDN**: Import/export game notation

API Endpoints
-------------

======================= ======= =======================================
Endpoint                Method  Description
======================= ======= =======================================
``/position``           GET     Current board position
``/legal_moves``        GET     Legal moves for current player
``/fen``                GET     FEN string
``/pdn``                GET     PDN string
``/move/{src}/{tgt}``   POST    Make a move
``/best_move``          GET     Play engine's best move
``/pop``                GET     Undo last move
``/load_fen``           POST    Load position from FEN
``/load_pdn``           POST    Load game from PDN
======================= ======= =======================================
