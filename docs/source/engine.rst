Engine
==========================================

The engine module provides AI opponents for playing draughts. The main implementation
is the ``AlphaBetaEngine``, which uses Negamax search with alpha-beta pruning and advanced optimizations.

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

The ``AlphaBetaEngine`` implements Negamax search with comprehensive optimizations:

**Negamax Architecture**
    Simplifies alpha-beta pruning by using the principle that ``max(a,b) = -min(-a,-b)``,
    reducing code complexity while maintaining efficiency.

**Iterative Deepening**
    Progressively deepens the search from depth 1 to the target depth, allowing the search
    to be interrupted by time limits while still returning the best move found so far.

**Zobrist Hashing**
    Computes incremental 64-bit position hashes for efficient transposition table lookups.
    Supports turn-aware hashing and handles piece promotion detection.

**Transposition Table**
    Caches previously evaluated positions with depth-aware entries (exact scores, lower bounds,
    upper bounds) to avoid redundant calculations when the same position is reached through
    different move orders. Stores the principal variation move for each position.

**Quiescence Search**
    Extends the search beyond the main depth limit to evaluate only capturing sequences,
    eliminating horizon effects that would cause poor move evaluation at depth boundaries.

**Move Ordering**
    Orders moves to maximize pruning efficiency:
    
    - Principal Variation (PV) moves from transposition table
    - Captures, scored by capture chain length
    - Killer moves (moves that caused cutoffs in sibling nodes)
    - History heuristic (rewarding moves that have caused cutoffs previously)

**Principal Variation Search (PVS)**
    Uses null-window searches to optimize the alpha-beta window, reducing the number of
    full-window re-searches required.

**Late Move Reductions (LMR)**
    Reduces search depth for moves later in the move ordering at depth ≥ 3, assuming
    that killer moves and history moves are more likely to fail high.

**Enhanced Evaluation Function**
    Considers multiple factors:
    
    - Material balance (men and kings with different values)
    - Piece-Square Tables (PST) for both men and kings
    - King advancement and centralization bonuses
    - Man advancement toward promotion zone

Performance Characteristics
---------------------------

Benchmark results from standard draughts positions show the engine's scaling across depths:

============  ============  ============  ============
Depth         Avg Time      Avg Nodes     Notes
============  ============  ============  ============
1             0.66 ms       24
2             3.88 ms       102
3             7.73 ms       269
4             20.24 ms      777
5             86.55 ms      2,896         Recommended for casual play
6             249.85 ms     9,163         Recommended for strong play
7             733.79 ms     24,528        Strong analysis
8             1.63 s        51,382        Extended analysis
9             5.63 s        141,284       Deep analysis
10            ~20 s         ~400,000      Still playable (with time limits)
============  ============  ============  ============

**Recommendations:**

- **Depth 3-4**: Fast response, suitable for casual play (< 50 ms per move)
- **Depth 5-6**: Strong play with reasonable response time (< 1 second per move)
- **Depth 7-8**: Very strong play, recommended for analysis (< 2 seconds per move)
- **Depth 9-10**: Expert-level play with extended time (5-20 seconds per move)

The engine can be configured with a ``time_limit`` parameter to constrain search time
across all depths using iterative deepening.

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

With time limits::

    # Search with 1-second time limit instead of fixed depth
    engine = AlphaBetaEngine(depth=20, time_limit=1.0)
    move, score = engine.get_best_move(board, with_evaluation=True)
    # Engine will iteratively deepen up to depth 20 or until time expires

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


Benchmarking the Engine
-----------------------

.. image:: _static/engine_benchmark.png
   :alt: Engine Benchmark Results
   :width: 600px