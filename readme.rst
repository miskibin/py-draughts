py-draughts
=============

.. image:: https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg
   :target: https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml

.. image:: https://badge.fury.io/py/fast_checkers.svg
   :target: https://badge.fury.io/py/fast_checkers

Draughts
--------


Efficient Modern and flexible implementation of draughts game with beautiful web interface. 
Supports multiple variants of the game and allows to play against AI.




`Documentation <https://michalskibinski109.github.io/py-draughts/>`_
-----------------------------------------------------------------

Installation
------------

.. code-block:: bash

    python -m pip install py-draughts

Usage
-----

simple
*******

.. code-block:: python

    >>> import draughts.american as draughts

    >>> board = draughts.Board()
    ---------------------------------
    |   | b |   | b |   | b |   | b |
    ---------------------------------
    | b |   | b |   | b |   | b |   |
    ---------------------------------
    |   | b |   | b |   | b |   | b |
    ---------------------------------
    |   |   |   |   |   |   |   |   |
    ---------------------------------
    |   |   |   |   |   |   |   |   |
    ---------------------------------
    | w |   | w |   | w |   | w |   |
    ---------------------------------
    |   | w |   | w |   | w |   | w |
    ---------------------------------
    | w |   | w |   | w |   | w |   |


Moving pieces
*************

.. code-block:: python

    >>> board.push_from_str("24-19")
    >>> board.push_from_str("12-16")
    >>> board.push_from_str("23-18")
    >>> board.push_from_str("16x23")
    >>> board.push_from_str("26x19")
    >>> board.pop()
    >>> print(board)
    ---------------------------------
    |   | b |   | b |   | b |   | b |
    ---------------------------------
    | b |   | b |   | b |   | b |   |
    ---------------------------------
    |   | b |   | b |   | b |   |   |
    ---------------------------------
    |   |   |   |   |   |   |   |   |
    ---------------------------------
    |   |   |   | w |   |   |   |   |
    ---------------------------------
    | w |   | w |   | b |   |   |   |
    ---------------------------------
    |   | w |   | w |   | w |   | w |
    ---------------------------------
    | w |   | w |   | w |   | w |   |


.. code-block:: python

    >>> print(list(board.legal_moves))
    [Move: 21->17, Move: 22->18, Move: 22->17, Move: 23->19, Move: 23->18, Move: 24->20, Move: 24->19]

Creating custom board
*********************

.. code-block:: python

    import draughts.base as draughts
    import numpy as np
    CUSTOM_POSITION = np.array([1] * 20 + [-1] * 12, dtype=np.int8)
    board = draughts.BaseBoard(starting_position=CUSTOM_POSITION)
    board.legal_moves = ... # create your own custom legal_moves method (property)

UI
--

.. code-block:: python

    from draughts.server import Server
    Server().run()

*It is as simple as that!*


.. image:: https://github.com/michalskibinski109/py-draughts/assets/77834536/a5e2ca89-28e1-4dcc-96ae-b18fc602c9bc
   :width: 600

.. image:: https://github.com/michalskibinski109/py-draughts/assets/77834536/b14523ea-4bc4-45e1-b5c0-5deea3ed5328
   :width: 600

* legal moves for selected square (on image ``16``)* 

.. image:: https://github.com/michalskibinski109/py-draughts/assets/77834536/c8245cbc-06ec-4623-81ab-c9aaa9302627
   :width: 600

Contributing
------------

Contributions to this project are welcome. If you encounter any issues or have suggestions for improvements, please open an issue or submit a pull request on the project repository.

Bibliography
------------

1. `notation <https://en.wikipedia.org/wiki/Portable_Draughts_Notation>`_
2. `rules and variants <https://en.wikipedia.org/wiki/Checkers>`_
3. `list of pdns <https://github.com/mig0/Games-Checkers/>`_
4. `droughts online  <https://lidraughts.org/>`_
5. `additional 1 (checkers online) <https://checkers.online/play>`_
6. `additional 2 (chinook) <https://webdocs.cs.ualberta.ca/~chinook/play/notation.html>`_
