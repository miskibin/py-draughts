Engine
======

AI engines for playing draughts.

Quick Start
-----------

.. code-block:: python

    from draughts import Board, AlphaBetaEngine

    board = Board()
    engine = AlphaBetaEngine(depth_limit=5)

    # Get best move
    best_move = engine.get_best_move(board)
    board.push(best_move)

    # Get move with evaluation score
    move, score = engine.get_best_move(board, with_evaluation=True)

Engine Interface
----------------

.. autoclass:: draughts.Engine
    :members:

AlphaBetaEngine
---------------

.. autoclass:: draughts.AlphaBetaEngine
    :members: __init__, evaluate, get_best_move

Performance
~~~~~~~~~~~

============  ============  ============
Depth         Avg Time      Avg Nodes
============  ============  ============
5             130 ms        2,896
6             350 ms        9,163
7             933 ms        24,528
8             4.9 s         122,168
============  ============  ============

- **Depth 5-6**: Strong play, responsive (< 1s per move)
- **Depth 7-8**: Very strong, suitable for analysis

.. image:: _static/engine_benchmark.png
   :alt: Engine Benchmark
   :width: 500px

HubEngine
---------

Use external engines implementing the Hub protocol (e.g., `Scan <https://hjetten.home.xs4all.nl/scan/scan.html>`_).

.. autoclass:: draughts.HubEngine
    :members: __init__, start, quit, get_best_move

Example::

    from draughts import Board, HubEngine

    with HubEngine("path/to/scan.exe", time_limit=1.0) as engine:
        board = Board()
        move, score = engine.get_best_move(board, with_evaluation=True)

Custom Engine
-------------

Inherit from :class:`~draughts.Engine` to create your own::

    from draughts import Engine
    import random

    class RandomEngine(Engine):
        def get_best_move(self, board, with_evaluation=False):
            move = random.choice(list(board.legal_moves))
            return (move, 0.0) if with_evaluation else move

Use with the :doc:`server` for interactive testing.
