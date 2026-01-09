py-draughts
===========

Fast, modern draughts library with move generation, validation, PDN support, and AI engine.

.. image:: https://badge.fury.io/py/py-draughts.svg
    :target: https://badge.fury.io/py/py-draughts

.. image:: https://static.pepy.tech/badge/py-draughts
    :target: https://pepy.tech/project/py-draughts

Installation
------------

.. code-block:: bash

    pip install py-draughts

Quick Start
-----------

.. code-block:: python

    from draughts import Board, AlphaBetaEngine

    # Create a board (Standard/International draughts)
    board = Board()

    # Make moves
    board.push_uci("31-27")
    board.push_uci("18-22")

    # Get legal moves
    print(list(board.legal_moves))

    # Use the AI engine
    engine = AlphaBetaEngine(depth_limit=5)
    best_move = engine.get_best_move(board)
    board.push(best_move)

Variants
--------

- :class:`draughts.StandardBoard` - International draughts (10×10, flying kings)
- :class:`draughts.AmericanBoard` - English checkers (8×8, men capture forward only)
- :class:`draughts.FrisianBoard` - Frisian draughts (10×10, orthogonal captures)
- :class:`draughts.RussianBoard` - Russian draughts (8×8, flying kings)

``Board`` is an alias for ``StandardBoard``.

API Reference
-------------

.. toctree::
    :maxdepth: 2

    core
    engine
    svg
    server

Performance
-----------

.. toctree::
    :maxdepth: 1

    benchmarking

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
