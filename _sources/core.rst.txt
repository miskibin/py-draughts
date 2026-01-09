Core API
========

Quick Start
-----------

.. code-block:: python

    from draughts import Board

    board = Board()                    # Standard 10×10 board
    board.push_uci("31-27")            # Make a move
    print(board.legal_moves)           # Get legal moves
    board.pop()                        # Undo move

Board Classes
-------------

==================  =====  ============  ==============  =============
Class               Size   Flying Kings  Max Capture     Description
==================  =====  ============  ==============  =============
``Board``           10×10  Yes           Required        Alias for StandardBoard
``StandardBoard``   10×10  Yes           Required        International draughts
``AmericanBoard``   8×8    No            Not required    English checkers
``FrisianBoard``    10×10  Yes           Required        Orthogonal captures allowed
``RussianBoard``    8×8    Yes           Not required    Flying kings, free capture
==================  =====  ============  ==============  =============

.. code-block:: python

    from draughts import Board, StandardBoard, AmericanBoard, RussianBoard

    board = Board()           # Same as StandardBoard()
    board = AmericanBoard()   # 8×8 English checkers
    board = RussianBoard()    # 8×8 Russian draughts

Making Moves
------------

.. code-block:: python

    board = Board()

    # Push move using UCI notation
    board.push_uci("31-27")
    board.push_uci("18-22")
    board.push_uci("27x18")   # Capture notation

    # Push a Move object
    move = board.legal_moves[0]
    board.push(move)

    # Undo moves
    last_move = board.pop()   # Returns the undone Move

Legal Moves
-----------

.. code-block:: python

    board = Board()

    # Get all legal moves
    moves = board.legal_moves
    print(len(moves))  # 9 in starting position

    # Check if a move is a capture
    for move in board.legal_moves:
        if move.captured_list:
            print(f"{move} captures {len(move.captured_list)} pieces")

Game State
----------

.. code-block:: python

    board = Board()

    board.turn                    # Color.WHITE or Color.BLACK
    board.game_over               # True if game ended
    board.is_draw                 # True if drawn
    board.is_threefold_repetition # True if position repeated 3x
    board.result                  # "1-0", "0-1", "1/2-1/2", or "-"

FEN Notation
------------

FEN represents board positions. Format: ``[Turn]:[White pieces]:[Black pieces]``

.. code-block:: python

    board = Board()

    # Get FEN
    print(board.fen)
    # '[FEN "W:W:W31,32,...,50:B1,2,...,20"]'

    # Create from FEN (kings prefixed with K)
    board = Board.from_fen("W:WK10,K20:BK35,K45")

PDN Notation
------------

PDN records game moves, similar to PGN in chess.

.. code-block:: python

    board = Board()
    board.push_uci("32-28")
    board.push_uci("18-23")

    # Get PDN
    print(board.pdn)
    # [GameType "20"]
    # [Variant "Standard (international) checkers"]
    # [Result "-"]
    # 1. 32-28 18-23

    # Create from PDN
    pdn = '[GameType "20"]\n1. 32-28 19-23 2. 28x19 14x23'
    board = Board.from_pdn(pdn)

Board Position
--------------

.. code-block:: python

    board = Board()

    # Get position as numpy array
    pos = board.position  # Shape: (50,) for standard board
    # Values: 1=black man, 2=black king, -1=white man, -2=white king, 0=empty

    # Access individual squares (0-indexed)
    piece = board[30]  # Square 31

    # ASCII representation
    print(board)

Square Numbering
----------------

Only dark squares are playable. Squares are numbered 1-50 (standard) or 1-32 (american/russian).

**Standard Board (10×10)**

.. code-block:: text

       1   2   3   4   5
     6   7   8   9  10
      11  12  13  14  15
    16  17  18  19  20
      21  22  23  24  25
    26  27  28  29  30
      31  32  33  34  35
    36  37  38  39  40
      41  42  43  44  45
    46  47  48  49  50

**American/Russian Board (8×8)**

.. code-block:: text

       1   2   3   4
     5   6   7   8
       9  10  11  12
    13  14  15  16
      17  18  19  20
    21  22  23  24
      25  26  27  28
    29  30  31  32

Types Reference
---------------

Color
~~~~~

.. py:data:: draughts.Color.WHITE
   :value: -1

.. py:data:: draughts.Color.BLACK
   :value: 1

Figure
~~~~~~

.. py:data:: draughts.Figure.WHITE_MAN
   :value: -1

.. py:data:: draughts.Figure.WHITE_KING
   :value: -2

.. py:data:: draughts.Figure.BLACK_MAN
   :value: 1

.. py:data:: draughts.Figure.BLACK_KING
   :value: 2

.. py:data:: draughts.Figure.EMPTY
   :value: 0

Move
~~~~

.. code-block:: python

    move = board.legal_moves[0]

    move.square_list      # [30, 26] - squares visited (0-indexed)
    move.captured_list    # [] or [22] - captured squares
    move.is_promotion     # True if promotes to king
    str(move)             # "31-27" or "26x17"

API Reference
-------------

BaseBoard
~~~~~~~~~

.. autoclass:: draughts.boards.base.BaseBoard
   :members: push, pop, push_uci, legal_moves, is_draw, game_over, result, fen, from_fen, pdn, from_pdn, position, is_threefold_repetition, is_capture, turn
   :noindex:
