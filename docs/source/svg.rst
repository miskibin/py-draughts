SVG Rendering
=============

The ``draughts.svg`` module provides functions for rendering draughts boards and pieces as SVG images.
It supports both 8×8 (American) and 10×10 (Standard/Frisian) board variants with full customization options.

.. contents:: Table of Contents
   :local:
   :depth: 2

Basic Usage
-----------

Rendering a Board
~~~~~~~~~~~~~~~~~

The simplest way to render a board is to pass a board object to the ``board()`` function:

.. code-block:: python

    import draughts

    board = draughts.StandardBoard()
    svg = draughts.svg.board(board, size=400)

.. image:: _static/board_standard.svg
   :alt: Standard draughts board
   :width: 400px

The function returns an SVG string that can be saved to a file or displayed in a Jupyter notebook.

Rendering a Single Piece
~~~~~~~~~~~~~~~~~~~~~~~~

You can render individual pieces using the ``piece()`` function:

.. code-block:: python

    import draughts

    # Piece values: -2=white king, -1=white man, 1=black man, 2=black king
    white_man = draughts.svg.piece(-1, size=60)
    black_king = draughts.svg.piece(2, size=60)

.. list-table:: Piece Types
   :widths: 25 25 25 25
   :header-rows: 1

   * - White Man
     - White King
     - Black Man
     - Black King
   * - .. image:: _static/piece_white_man.svg
          :width: 60px
     - .. image:: _static/piece_white_king.svg
          :width: 60px
     - .. image:: _static/piece_black_man.svg
          :width: 60px
     - .. image:: _static/piece_black_king.svg
          :width: 60px

Board Variants
--------------

The SVG module automatically adapts to different board sizes:

Standard (10×10)
~~~~~~~~~~~~~~~~

.. code-block:: python

    board = draughts.StandardBoard()
    draughts.svg.board(board, size=400)

.. image:: _static/board_standard.svg
   :alt: Standard 10x10 board
   :width: 400px

American (8×8)
~~~~~~~~~~~~~~

.. code-block:: python

    board = draughts.AmericanBoard()
    draughts.svg.board(board, size=400)

.. image:: _static/board_american.svg
   :alt: American 8x8 board
   :width: 400px

Highlighting
------------

Last Move
~~~~~~~~~

Highlight the squares involved in the last move:

.. code-block:: python

    board = draughts.StandardBoard()
    board.push_uci("32-28")
    draughts.svg.board(board, size=400, lastmove=board._moves_stack[-1])

.. image:: _static/board_lastmove.svg
   :alt: Board with last move highlighted
   :width: 400px

Custom Square Colors
~~~~~~~~~~~~~~~~~~~~

Fill specific squares with custom colors (using RGBA hex format for transparency):

.. code-block:: python

    board = draughts.StandardBoard()
    draughts.svg.board(
        board,
        size=400,
        fill={
            31: "#ff000080",  # Red with 50% opacity
            32: "#00ff0080",  # Green with 50% opacity
            33: "#0000ff80",  # Blue with 50% opacity
        }
    )

.. image:: _static/board_fill.svg
   :alt: Board with highlighted squares
   :width: 400px

Arrows
------

Draw arrows to annotate moves or tactics:

.. code-block:: python

    from draughts.svg import Arrow

    board = draughts.StandardBoard()
    draughts.svg.board(
        board,
        size=400,
        arrows=[
            Arrow(31, 27),                    # Green arrow (default)
            Arrow(32, 28, color="red"),       # Red arrow
        ]
    )

.. image:: _static/board_arrows.svg
   :alt: Board with arrows
   :width: 400px

Available arrow colors: ``green`` (default), ``red``, ``yellow``, ``blue``.

Board Orientation
-----------------

Flip the board to show black's perspective:

.. code-block:: python

    board = draughts.StandardBoard()
    draughts.svg.board(board, size=400, orientation=draughts.Color.BLACK)

.. image:: _static/board_flipped.svg
   :alt: Board from black's perspective
   :width: 400px

Display Options
---------------

Minimal Board
~~~~~~~~~~~~~

Remove coordinates and square numbers for a cleaner look:

.. code-block:: python

    board = draughts.StandardBoard()
    draughts.svg.board(board, size=400, coordinates=False, legend=False)

.. image:: _static/board_minimal.svg
   :alt: Minimal board
   :width: 400px

Custom Colors
~~~~~~~~~~~~~

Override default colors with the ``colors`` parameter:

.. code-block:: python

    board = draughts.StandardBoard()
    draughts.svg.board(
        board,
        size=400,
        colors={
            "square light": "#eeeed2",
            "square dark": "#769656",
            "piece white": "#ffffff",
            "piece black": "#000000",
        }
    )

Available color keys:

- ``square light``, ``square dark`` - Board square colors
- ``square light lastmove``, ``square dark lastmove`` - Last move highlight colors
- ``margin``, ``coord`` - Margin background and coordinate text colors
- ``piece white``, ``piece black`` - Piece fill colors
- ``piece white stroke``, ``piece black stroke`` - Piece outline colors
- ``crown white``, ``crown black`` - Crown colors for kings
- ``arrow green``, ``arrow red``, ``arrow yellow``, ``arrow blue`` - Arrow colors

Jupyter Notebook Integration
----------------------------

The SVG module is designed to work seamlessly with Jupyter notebooks. The returned ``SvgWrapper``
object implements ``_repr_svg_()`` for automatic display:

.. code-block:: python

    import draughts

    board = draughts.StandardBoard()
    draughts.svg.board(board)  # Automatically displayed in notebook

Saving to File
--------------

Save the SVG to a file:

.. code-block:: python

    import draughts

    board = draughts.StandardBoard()
    svg = draughts.svg.board(board, size=400)

    with open("board.svg", "w") as f:
        f.write(svg)

API Reference
-------------

board()
~~~~~~~

.. py:function:: draughts.svg.board(board=None, *, size=None, coordinates=True, colors={}, lastmove=None, arrows=[], fill={}, squares=None, orientation=Color.WHITE, legend=True)

   Renders a draughts board as an SVG image.

   :param board: A BaseBoard instance, or None for an empty board.
   :param size: Image size in pixels, or None for no size limit.
   :param coordinates: Whether to show coordinate labels on the margin.
   :param colors: Dictionary to override default colors.
   :param lastmove: A Move to highlight (shows start and end squares).
   :param arrows: List of Arrow objects or (tail, head) tuples to draw.
   :param fill: Dictionary mapping square indices to colors for highlighting.
   :param squares: Iterable of square indices to mark with an X.
   :param orientation: Viewing orientation (Color.WHITE = black at top).
   :param legend: Whether to show square numbers on the dark squares.
   :returns: SVG string wrapped in SvgWrapper for Jupyter integration.

piece()
~~~~~~~

.. py:function:: draughts.svg.piece(piece_value, *, size=None, colors={})

   Renders a single draughts piece as an SVG image.

   :param piece_value: Piece value (-2=white king, -1=white man, 1=black man, 2=black king).
   :param size: Image size in pixels, or None for no size limit.
   :param colors: Dictionary to override default colors.
   :returns: SVG string wrapped in SvgWrapper for Jupyter integration.

Arrow
~~~~~

.. py:class:: draughts.svg.Arrow(tail, head, *, color="green")

   Details of an arrow to be drawn.

   :param tail: Start square of the arrow (0-indexed).
   :param head: End square of the arrow (0-indexed).
   :param color: Arrow color (green, red, yellow, or blue).
