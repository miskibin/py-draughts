Core
====

Colors
------

Constants for the side to move or the color of a piece.

.. py:data:: draughts.Color.WHITE
    :type: draughts.Color
    :value: -1

    Constant representing the white side.

.. py:data:: draughts.Color.BLACK
    :type: draughts.Color
    :value: 1

    Constant representing the black side.

Example usage::

    from draughts import StandardBoard, Color
    
    board = StandardBoard()
    print(board.turn)  # Color.WHITE
    
    # Toggle turn
    if board.turn == Color.WHITE:
        print("White to move")

Figures (Piece Types)
---------------------

Constants representing piece types in draughts.

.. py:data:: draughts.Figure.BLACK_KING
    :type: draughts.Figure
    :value: 2

    A black king piece.

.. py:data:: draughts.Figure.BLACK_MAN
    :type: draughts.Figure
    :value: 1

    A black man (regular piece).

.. py:data:: draughts.Figure.WHITE_KING
    :type: draughts.Figure
    :value: -2

    A white king piece.

.. py:data:: draughts.Figure.WHITE_MAN
    :type: draughts.Figure
    :value: -1

    A white man (regular piece).

.. py:data:: draughts.Figure.EMPTY
    :type: draughts.Figure
    :value: 0

    An empty square.

Squares
-------

In py-draughts, squares are numbered from 1 to 50 for standard (10×10) boards 
and 1 to 32 for American (8×8) boards. Only dark squares are numbered and used 
in the game.

Standard Board (10×10)
~~~~~~~~~~~~~~~~~~~~~~

Squares are numbered 1-50:

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

American Board (8×8)
~~~~~~~~~~~~~~~~~~~~

Squares are numbered 1-32:

.. code-block:: text

     1  2  3  4
   5  6  7  8
     9 10 11 12
  13 14 15 16
    17 18 19 20
  21 22 23 24
    25 26 27 28
  29 30 31 32

Board Factory
-------------

.. autofunction:: draughts.get_board

Example::

    from draughts import get_board
    
    # Create a standard board
    board = get_board('standard')
    
    # Create an American board
    board = get_board('american')
    
    # Create a Frisian board (with orthogonal captures)
    board = get_board('frisian')
    
    # Create a board from FEN
    board = get_board('standard', fen='W:W31,32,33:B18,19,20')

Boards
------

All board classes inherit from the base :class:`draughts.boards.base.BaseBoard` class.

StandardBoard
~~~~~~~~~~~~~

.. autoclass:: draughts.boards.standard.Board
    :members:
    :inherited-members:
    :show-inheritance:

AmericanBoard
~~~~~~~~~~~~~

.. autoclass:: draughts.boards.american.Board
    :members:
    :inherited-members:
    :show-inheritance:

FrisianBoard
~~~~~~~~~~~~

.. autoclass:: draughts.boards.frisian.Board
    :members:
    :inherited-members:
    :show-inheritance:

BaseBoard
~~~~~~~~~

.. autoclass:: draughts.boards.base.BaseBoard
    :members:

Moves
-----

.. autoclass:: draughts.move.Move
    :members:

Example::

    from draughts import StandardBoard
    
    board = StandardBoard()
    
    # Make a move using UCI notation
    move = board.push_uci("31-27")
    print(move)  # Move: 31->27
    
    # Iterate through legal moves
    for move in board.legal_moves:
        print(move)
    
    # Undo the last move
    board.pop()

FEN Notation
------------

py-draughts uses FEN (Forsyth-Edwards Notation) adapted for draughts to represent board positions.

Format::

    [Side to move]:[White pieces]:[Black pieces]

Example::

    W:W31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

Kings are prefixed with 'K'::

    W:WK10,K20:BK35,K45

Usage::

    from draughts import StandardBoard
    
    # From FEN
    fen = "W:WK10,K20:BK35,K45"
    board = StandardBoard.from_fen(fen)
    
    # To FEN
    fen_string = board.to_fen()

PDN Notation
------------

PDN (Portable Draughts Notation) is used for recording games, similar to PGN in chess.

Format::

    [GameType "20"]
    [Variant "Standard (international) checkers"]
    [Result "-"]
    1. 31-27 32-28 2. 27-23 28-24

Usage::

    from draughts import StandardBoard
    
    # Generate PDN
    board = StandardBoard()
    board.push_uci("31-27")
    board.push_uci("19-23")
    pdn = board.pdn
    print(pdn)
    
    # From PDN
    pdn_string = '''[GameType "20"]
    1. 32-28 19-23 2. 28x19 14x23'''
    board = StandardBoard.from_pdn(pdn_string)
