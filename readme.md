# py-draughts

[![GitHub Actions](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg)](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml)
[![PyPI version](https://badge.fury.io/py/py-draughts.svg)](https://badge.fury.io/py/py-draughts)
![PyPI - Downloads](https://img.shields.io/pypi/dm/py-draughts)


Efficient modern and flexible implementation of the draughts game with a beautiful web interface. 
Supports multiple variants of the game and allows playing against AI.

## Installation

```bash
pip install py-draughts
```

## Key features
1. Provides beautiful web interface for testing your engine/playing against AI.
2. Supports multiple variants of the game (with different board size). `standard`, `american` etc.
3. Follows international draughts standards. like `fen` `pdn` etc.
4. Allows to easily create new variants of the game. by extending the `Board` class.
5. Accurate documentation generated from code.



### [Documentation](https://michalskibinski109.github.io/py-draughts/)

## Usage



#### Displays simple ascii board

```python
>>> from draughts import get_board
>>> board = get_board("standard")
Board initialized with shape (10, 10). (base.py:108)
>>> board
 . b . b . b . b . b
 b . b . b . b . b .
 . b . b . b . b . b
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . . . . . . .
 w . w . w . w . w .
 . w . w . w . w . w
 w . w . w . w . w .
```

#### Make and undo moves

```python
>>> board.push_from_str("37-32")
>>> board.push_from_str("14-19")
>>> board.push_from_str("32-28")
>>> board.push_from_str("19-23")
>>> board.pop() # undo last move
>>> board.push_from_str("19-23")
>>> board.push_from_str("28x19")
>>> board
 . b . b . b . b . b
 b . b . b . b . b .
 . b . b . b . . . b
 . . . . . . w . . .
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . . . . . . .
 w . . . w . w . w .
 . w . w . w . w . w
 w . w . w . w . w .
```

#### Generate legal moves and validate moves

```python
>>> board.push_from_str("10x42")
Move: 10->42 is correct, but not legal in given position.
 Legal moves are: [Move: 36->31, Move: 37->32, Move: 37->31, Move: 38->33, Move: 38->32, Move: 39->34, Move: 39->33, Move: 40->35, Move: 40->34]

>>> list(board.legal_moves)
[Move: 36->31, Move: 37->32, Move: 37->31, Move: 38->33, Move: 38->32, Move: 39->34, Move: 39->33, Move: 40->35, Move: 40->34]
```

#### Generate fen string and load board from fen string


```python
>>> board =Board.from_fen("W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32")
Board initialized with shape (10, 10). (base.py:109)
>>> board.push_from_str("28-37")
>>> board.fen
'[FEN "B:W4,11,31,K33,K34,37,38,40,K41,43,K44,45,K46,47:BK3,21,27"]'
```
#### American checkers

```python
>>> from draughts import get_board
>>> board = get_board("american")
Board initialized with shape (8, 8). (base.py:108)
>>> board
 . b . b . b . b
 b . b . b . b .
 . b . b . b . b
 . . . . . . . .
 . . . . . . . .
 w . w . w . w .
 . w . w . w . w
 w . w . w . w .
```


## UI

1. Allows to play against AI.
2. Allows to play vs another player. (on the same computer)
3. Allows to test and find bugs in your engine.

```python
from draughts.server import Server
Server().run()
```

#### Use for testing your engine.

_Example with simplest possible engine._

```python
>>> server = Server(get_best_move_method=lambda board: np.random.choice(list(board.legal_moves)))
>>> server.run()
INFO:     Started server process [1617]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

_It is as simple as that!_

<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/b5b3c1fe-3e08-4114-b73b-2b136e3c1c9b" width="800" />


<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/4deead2a-adf1-4a7a-9422-c8da43f31a53" width="800" />


### testing best moves finding methods:

[Example](https://github.com/michalskibinski109/py-draughts/blob/main/examples/engine.py)

## Contributing

Contributions to this project are welcome. If you encounter any issues or have suggestions for improvements, please open an issue or submit a pull request on the project repository.

## Bibliography

1. [Notation](https://en.wikipedia.org/wiki/Portable_Draughts_Notation)
2. [Rules and variants](https://en.wikipedia.org/wiki/Checkers)
3. [List of PDNs](https://github.com/mig0/Games-Checkers/)
4. [Draughts online](https://lidraughts.org/)
5. [Additional 1 (Checkers online)](https://checkers.online/play)
6. [Additional 2 (Chinook)](https://webdocs.cs.ualberta.ca/~chinook/play/notation.html)
