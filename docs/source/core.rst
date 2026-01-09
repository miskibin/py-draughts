Core API
========

Boards
------

All board classes inherit from :class:`~draughts.BaseBoard`.
Use ``Board`` (alias for ``StandardBoard``) for the most common variant.

.. autoclass:: draughts.StandardBoard
    :members:
    :inherited-members:
    :show-inheritance:

.. autoclass:: draughts.AmericanBoard
    :members:
    :show-inheritance:
    :noindex:

.. autoclass:: draughts.FrisianBoard
    :members:
    :show-inheritance:
    :noindex:

.. autoclass:: draughts.RussianBoard
    :members:
    :show-inheritance:
    :noindex:

BaseBoard
~~~~~~~~~

.. autoclass:: draughts.BaseBoard
    :members:
    :noindex:

Moves
-----

.. autoclass:: draughts.Move
    :members:

Types
-----

.. autoclass:: draughts.Color
    :members:
    :undoc-members:

.. autoclass:: draughts.Figure
    :members:
    :undoc-members:

Square Numbering
----------------

Only dark squares are playable and numbered.

**Standard Board (10×10)** - Squares 1-50:

.. code-block:: text

     1  2  3  4  5
   6  7  8  9  10
    11 12 13 14 15
  16 17 18 19 20
    21 22 23 24 25
  26 27 28 29 30
    31 32 33 34 35
  36 37 38 39 40
    41 42 43 44 45
  46 47 48 49 50

**American/Russian Board (8×8)** - Squares 1-32:

.. code-block:: text

     1  2  3  4
   5  6  7  8
     9 10 11 12
  13 14 15 16
    17 18 19 20
  21 22 23 24
    25 26 27 28
  29 30 31 32

Notation
--------

**FEN** (Forsyth-Edwards Notation) represents board positions::

    W:W31,32,33:B18,19,20     # W = White to move, pieces listed
    W:WK10,K20:BK35,K45       # K prefix = King

**PDN** (Portable Draughts Notation) records games::

    [GameType "20"]
    [Variant "Standard"]
    1. 31-27 18-22 2. 27x18 12x23

Usage::

    from draughts import Board

    # From FEN
    board = Board.from_fen("W:WK10,K20:BK35,K45")

    # To FEN
    print(board.fen)

    # From PDN
    board = Board.from_pdn('[GameType "20"]\n1. 32-28 19-23')

    # To PDN
    print(board.pdn)
