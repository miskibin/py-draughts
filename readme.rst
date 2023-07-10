Fast Checkers
=============

.. image:: https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg
   :target: https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml

.. image:: https://badge.fury.io/py/fast_checkers.svg
   :target: https://badge.fury.io/py/fast_checkers

Checkers
--------

Efficient Modern and flexible implementation of checkers game with beautiful web interface. Supports multiple variants of the game and allows to play against AI.

Documentation
-------------

`Documentation <https://michalskibinski109.github.io/checkers/>`_

Installation
------------

.. code-block:: bash

    python -m pip install fast-checkers

Usage
-----

simple
*******

.. code-block:: python

    >>> import checkers.american as checkers

    >>> board = checkers.Board()
    ---------------------------------
    |   | x |   | x |   | x |   | x |
    ---------------------------------
    | x |   | x |   | x |   | x |   |
    ---------------------------------
    |   | x |   | x |   | x |   | x |
    ---------------------------------
    |   |   |   |   |   |   |   |   |
    ---------------------------------
    |   |   |   |   |   |   |   |   |
    ---------------------------------
    | o |   | o |   | o |   | o |   |
    ---------------------------------
    |   | o |   | o |   | o |   | o |
    ---------------------------------
    | o |   | o |   | o |   | o |   |


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
    |   | x |   | x |   | x |   | x |
    ---------------------------------
    | x |   | x |   | x |   | x |   |
    ---------------------------------
    |   | x |   | x |   | x |   |   |
    ---------------------------------
    |   |   |   |   |   |   |   |   |
    ---------------------------------
    |   |   |   | o |   |   |   |   |
    ---------------------------------
    | o |   | o |   | x |   |   |   |
    ---------------------------------
    |   | o |   | o |   | o |   | o |
    ---------------------------------
    | o |   | o |   | o |   | o |   |


.. code-block:: python

    >>> print(list(board.legal_moves))
    [Move: 21->17, Move: 22->18, Move: 22->17, Move: 23->19, Move: 23->18, Move: 24->20, Move: 24->19]

Creating custom board
*********************

.. code-block:: python

    import checkers.base as checkers
    import numpy as np
    CUSTOM_POSITION = np.array([1] * 20 + [-1] * 12, dtype=np.int8)
    board = checkers.BaseBoard(starting_position=CUSTOM_POSITION)
    board.legal_moves = ... # create your own custom legal_moves method (property)

UI
--

.. code-block:: python

    from checkers.server import Server
    Server().run()

*It is as simple as that!*


.. image:: https://github.com/michalskibinski109/checkers/assets/77834536/4ec36e49-38cc-45e8-a500-d0d24b21fce7
   :width: 600

.. image:: https://github.com/michalskibinski109/checkers/assets/77834536/b7e0bf73-1bc5-4769-8f82-a22cde3b7e90
   :width: 600

*pseudo legal moves for selected square* 

.. image:: https://github.com/michalskibinski109/checkers/assets/77834536/ef64179a-1e7d-46d4-991e-5a34fc803d7e
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
