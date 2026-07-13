.. meta::
   :description: py-draughts engines — TurboEngine, a machine-learned pattern evaluation with PVS search for international draughts, and SimpleEngine, a general-purpose alpha-beta engine for every variant, plus a HUB protocol bridge for external engines like Scan and Kingsrow.
   :keywords: draughts engine, turboengine, machine-learned evaluation, alpha-beta draughts, hub protocol, scan engine, kingsrow, python checkers ai, transposition table

Engine
======

Two engines are built in: :class:`~draughts.TurboEngine` — the strongest, for
international 10x10 — and :class:`~draughts.SimpleEngine`, a lightweight
general-purpose engine that works on every variant.

Quick Start
-----------

.. code-block:: python

    from draughts import Board, TurboEngine

    board = Board()
    engine = TurboEngine(time_limit=0.5)   # strongest; international 10x10 only

    # Get best move
    best_move = engine.get_best_move(board)
    board.push(best_move)

    # Get move with evaluation score
    move, score = engine.get_best_move(board, with_evaluation=True)

Engine Interface
----------------

.. autoclass:: draughts.Engine
    :members:

TurboEngine
-----------

The strongest built-in engine, for the standard international (10x10) board
only. It uses Scan's 63-bit bitboard layout, a PVS search with transposition
table, and a machine-learned pattern evaluation trained on Scan self-play.
At equal time per move it beats :class:`~draughts.SimpleEngine` by several
hundred Elo while using less time.

.. code-block:: python

    from draughts import Board, TurboEngine

    board = Board()
    engine = TurboEngine(time_limit=0.5)   # or depth_limit=...
    move, score = engine.get_best_move(board, with_evaluation=True)

.. autoclass:: draughts.TurboEngine
    :members: __init__, get_best_move

SimpleEngine
------------

A lightweight general-purpose engine — alpha-beta search with a transposition
table and iterative deepening — that works on **every** board variant, unlike
:class:`~draughts.TurboEngine` (international only). Use it for American,
Frisian, Russian, Brazilian, and the other variants.

.. code-block:: python

    from draughts import Board, SimpleEngine

    board = Board()
    engine = SimpleEngine(depth_limit=5)
    move, score = engine.get_best_move(board, with_evaluation=True)

.. autoclass:: draughts.SimpleEngine
    :members: __init__, evaluate, get_best_move

Performance
~~~~~~~~~~~

``SimpleEngine`` search cost by depth:

============  ============  ============
Depth         Avg Time      Avg Nodes
============  ============  ============
5             274 ms        3,263
6             619 ms        7,330
7             2.20 s        21,642
8             6.55 s        98,987
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

Benchmarking
------------

Compare two engines against each other with comprehensive statistics.

Quick Start
~~~~~~~~~~~

.. code-block:: python

    from draughts import Benchmark, SimpleEngine

    # Compare two engines
    stats = Benchmark(
        SimpleEngine(depth_limit=4),
        SimpleEngine(depth_limit=6),
        games=20
    ).run()

    print(stats)

Output::

    ============================================================
      BENCHMARK: SimpleEngine (d=4) vs SimpleEngine (d=6)
    ============================================================

      RESULTS: 2-12-6 (W-L-D)
      SimpleEngine (d=4) win rate: 25.0%
      Elo difference: -191

      PERFORMANCE
      Avg game length: 85.3 moves
      SimpleEngine (d=4): 25.2ms/move, 312 nodes/move
      SimpleEngine (d=6): 142.5ms/move, 1850 nodes/move
      Total time: 45.2s
      ...

Benchmark Class
~~~~~~~~~~~~~~~

.. autoclass:: draughts.Benchmark
    :members: __init__, run

Parameters
~~~~~~~~~~

- **engine1, engine2**: Any :class:`Engine` instances to compare
- **board_class**: Board variant (``StandardBoard``, ``AmericanBoard``, etc.)
- **games**: Number of games to play (default: 10)
- **openings**: List of FEN strings for starting positions
- **swap_colors**: Alternate colors between games (default: True)
- **max_moves**: Maximum moves per game (default: 200)
- **workers**: Parallel workers (default: 1, sequential)

Custom Names
~~~~~~~~~~~~

Engines with the same class name are automatically distinguished by their settings::

    # These will show as "SimpleEngine (d=4)" and "SimpleEngine (d=6)"
    Benchmark(
        SimpleEngine(depth_limit=4),
        SimpleEngine(depth_limit=6)
    )

Or provide custom names::

    Benchmark(
        SimpleEngine(depth_limit=4, name="FastBot"),
        SimpleEngine(depth_limit=6, name="StrongBot")
    )

Custom Openings
~~~~~~~~~~~~~~~

By default, 10x10 boards use built-in opening positions. Provide your own::

    from draughts import Benchmark, SimpleEngine, STANDARD_OPENINGS

    # Use specific FEN positions
    custom_openings = [
        "W:W31,32,33,34,35:B1,2,3,4,5",
        "B:W40,41,42:B10,11,12",
    ]

    stats = Benchmark(
        SimpleEngine(depth_limit=4),
        SimpleEngine(depth_limit=6),
        openings=custom_openings
    ).run()

    # Or use the built-in openings
    print(f"Available openings: {len(STANDARD_OPENINGS)}")

Different Board Variants
~~~~~~~~~~~~~~~~~~~~~~~~

Test engines on any supported variant::

    from draughts import Benchmark, SimpleEngine
    from draughts import AmericanBoard, FrisianBoard, RussianBoard

    # American checkers (8x8)
    stats = Benchmark(
        SimpleEngine(depth_limit=5),
        SimpleEngine(depth_limit=7),
        board_class=AmericanBoard,
        games=10
    ).run()

Saving Results to CSV
~~~~~~~~~~~~~~~~~~~~~

Save benchmark results to CSV for tracking over time::

    stats = Benchmark(e1, e2, games=20).run()
    stats.to_csv("benchmark_results.csv")

If the file exists, results are appended. The CSV includes:

- Timestamp, engine names, game count
- Wins, losses, draws, win rate, Elo difference
- Average moves, time per move, nodes per move
- Total benchmark time

Statistics
~~~~~~~~~~

The :class:`BenchmarkStats` object provides:

- **games**: Total games played
- **e1_wins, e2_wins, draws**: Win/loss/draw counts
- **e1_win_rate**: Engine 1's win rate (0.0-1.0)
- **elo_diff**: Estimated Elo difference (positive = engine1 stronger)
- **avg_moves**: Average game length
- **avg_time_e1, avg_time_e2**: Average time per move
- **avg_nodes_e1, avg_nodes_e2**: Average nodes searched per move
- **results**: List of individual :class:`GameResult` objects

.. autoclass:: draughts.BenchmarkStats
    :members:

.. autoclass:: draughts.GameResult
    :members: