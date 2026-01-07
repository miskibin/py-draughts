Server
==========================================

The server module provides a web-based UI for playing draughts games. It supports
human play, single engine play, and engine vs engine matches.

Server Class
------------

.. autoclass:: draughts.server.Server
    :members: __init__, run

Basic Usage
-----------

Starting a simple server::

    from draughts import get_board
    from draughts.server import Server
    
    board = get_board('standard')
    server = Server(board=board)
    server.run(host="127.0.0.1", port=8000)

Open http://localhost:8000 in your browser to access the web interface.

Playing with an Engine
----------------------

To enable the "Engine Move" button in the UI, pass an engine to the server::

    from draughts import get_board
    from draughts.engine import AlphaBetaEngine
    from draughts.server import Server
    
    board = get_board('standard')
    engine = AlphaBetaEngine(depth_limit=6)
    
    # Engine plays for both sides when you click "Engine Move"
    server = Server(
        board=board,
        white_engine=engine,
        black_engine=engine
    )
    server.run()

Engine vs Engine Matches
------------------------

The server supports running matches between two different engines. This is useful
for testing and comparing engine implementations::

    from draughts import get_board
    from draughts.engine import AlphaBetaEngine
    from draughts.server import Server
    
    board = get_board('standard')
    
    # Create two engines with different configurations
    white_engine = AlphaBetaEngine(depth_limit=6)
    black_engine = AlphaBetaEngine(depth_limit=4)
    
    server = Server(
        board=board,
        white_engine=white_engine,
        black_engine=black_engine
    )
    server.run()

When two engines are configured:

- The UI displays the engine names for each side
- Click "Engine Move" to make the current side's engine play
- Use "Auto Play" to watch the engines play against each other automatically
- The depth slider affects both engines

Custom Engine Integration
-------------------------

You can integrate any custom engine that implements the ``Engine`` interface::

    from draughts import get_board
    from draughts.engine import Engine
    from draughts.server import Server
    import random
    
    class RandomEngine(Engine):
        """A simple random move engine."""
        
        def get_best_move(self, board, with_evaluation=False):
            move = random.choice(list(board.legal_moves))
            return (move, 0.0) if with_evaluation else move
    
    class GreedyEngine(Engine):
        """Prefers captures over quiet moves."""
        
        def get_best_move(self, board, with_evaluation=False):
            moves = list(board.legal_moves)
            # Sort by capture length (most captures first)
            moves.sort(key=lambda m: len(m.captured_list), reverse=True)
            move = moves[0]
            return (move, 0.0) if with_evaluation else move
    
    # Pit the two engines against each other
    board = get_board('standard')
    server = Server(
        board=board,
        white_engine=GreedyEngine(),
        black_engine=RandomEngine()
    )
    server.run()

Web Interface Features
----------------------

The web UI provides the following controls:

**Board Selection**
    Switch between American (8x8) and Standard (10x10) board variants.

**Engine Settings**
    - **Depth slider**: Adjust search depth (1-10) for both engines

**Controls**
    - **Engine Move**: Make the current engine play its best move
    - **Auto Play**: Start/stop automatic engine-vs-engine play
    - **Undo**: Take back the last move

**Import/Export**
    - **Copy FEN**: Copy current position as FEN string
    - **Load FEN**: Load a position from FEN string
    - **Copy PDN**: Copy game notation as PDN
    - **Load PDN**: Load a game from PDN notation

**Info Panel**
    - Turn indicator showing whose move it is
    - Move history with clickable moves for navigation
    - Engine indicator (when engines are configured)

API Endpoints
-------------

The server exposes the following REST API endpoints:

======================= ======= ===============================================
Endpoint                Method  Description
======================= ======= ===============================================
``/``                   GET     Main game page
``/position``           GET     Get current board position
``/legal_moves``        GET     Get legal moves for current position
``/fen``                GET     Get FEN string
``/pdn``                GET     Get PDN string
``/engine_info``        GET     Get configured engine information
``/move/{src}/{tgt}``   POST    Make a move
``/best_move``          GET     Get and play engine's best move
``/pop``                GET     Undo last move
``/goto/{ply}``         GET     Jump to specific ply in history
``/load_fen``           POST    Load position from FEN
``/load_pdn``           POST    Load game from PDN
``/set_depth/{n}``      GET     Set engine search depth
``/set_board/{type}``   GET     Switch board type (standard/american)
======================= ======= ===============================================

Running from Command Line
-------------------------

Start the server directly from the command line::

    python -m draughts.server.server

This starts a server with default settings (AlphaBetaEngine at depth 6).
