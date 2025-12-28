Engine
==========================================

The engine module provides AI opponents for playing draughts. The main implementation
is the ``AlphaBetaEngine``, which uses minimax search with alpha-beta pruning.

Engine Interface
----------------

.. autoclass:: draughts.engine.Engine
    :members:

AlphaBetaEngine
---------------

.. autoclass:: draughts.engine.AlphaBetaEngine
    :members: __init__, evaluate, get_best_move

Algorithm Overview
------------------

The ``AlphaBetaEngine`` implements a minimax search with several optimizations:

**Alpha-Beta Pruning**
    Eliminates branches that cannot affect the final decision, significantly reducing 
    the number of positions evaluated.

**Move Ordering**
    Evaluates capture moves first, which improves pruning efficiency since captures
    are often the strongest moves in draughts.

**Transposition Table**
    Caches previously evaluated positions to avoid redundant calculations when the
    same position is reached through different move orders.

**Enhanced Evaluation**
    The evaluation function considers:
    
    - Material balance (pieces and kings)
    - Piece positioning and advancement
    - King promotion potential

Performance Characteristics
---------------------------

The engine's strength and speed depend on the search depth:

- **Depth 3-4**: Fast response, suitable for casual play
- **Depth 5-6**: Strong play with reasonable response time
- **Depth 7+**: Very strong but slower, best for analysis

Example Usage
-------------

Basic usage::

    from draughts import get_board
    from draughts.engine import AlphaBetaEngine
    
    board = get_board('standard')
    engine = AlphaBetaEngine(depth=5)
    
    # Get best move
    best_move = engine.get_best_move(board)
    board.push(best_move)
    
    # Get move with evaluation
    move, score = engine.get_best_move(board, with_evaluation=True)
    print(f"Best move: {move}, Score: {score}")

Custom Engine Implementation
-----------------------------

To create your own engine, inherit from the ``Engine`` class and implement
the ``get_best_move`` method::

    from draughts.engine import Engine
    import random
    
    class RandomEngine(Engine):
        def get_best_move(self, board, with_evaluation=False):
            move = random.choice(list(board.legal_moves))
            if with_evaluation:
                return move, 0.0
            return move