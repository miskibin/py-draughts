# py-draughts

[![GitHub Actions](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg)](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml)
[![PyPI version](https://badge.fury.io/py/py-draughts.svg)](https://badge.fury.io/py/py-draughts)


Efficient modern and flexible implementation of the draughts game with a beautiful web interface. 
Supports multiple variants of the game and allows playing against AI.



## Installation

```bash
pip install py-draughts
```

## [Documentation](https://michalskibinski109.github.io/py-draughts/)

## Usage



#### Initialize board

```python
>>> from draughts.standard import Board
>>> board = Board()
Board initialized with shape (10, 10). (base.py:108)
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
```

#### Shows simple ascii board

```python
>>> print(board)
-----------------------------------------
|   | b |   | b |   | b |   | b |   | b |
-----------------------------------------
| b |   | b |   | b |   | b |   | b |   |
-----------------------------------------
|   | b |   | b |   | b |   |   |   | b |
-----------------------------------------
|   |   |   |   |   |   | w |   |   |   |
-----------------------------------------
|   |   |   |   |   |   |   |   |   |   |
-----------------------------------------
|   |   |   |   |   |   |   |   |   |   |
-----------------------------------------
|   |   |   |   |   |   |   |   |   |   |
-----------------------------------------
| w |   |   |   | w |   | w |   | w |   |
-----------------------------------------
|   | w |   | w |   | w |   | w |   | w |
-----------------------------------------
| w |   | w |   | w |   | w |   | w |   |
```

### American checkers

```python
>>> from draughts.american import Board
>>> board = Board()
Board initialized with shape (8, 8). (base.py:108)
>>> print(board)
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
```


## UI

```python
from draughts.server import Server
Server().run()
```

### Use for testing your engine.

_Example with simplest possible engine._

```python
>>> server = Server(get_best_move_method=lambda board: np.random.choice([board.legal_moves]))
>>> server.run()
INFO:     Started server process [1617]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

_It is as simple as that!_

<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/a5e2ca89-28e1-4dcc-96ae-b18fc602c9bc" width="600" />

<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/b14523ea-4bc4-45e1-b5c0-5deea3ed5328" width="600" />

*Legal moves for selected square (on image "16")*

<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/c8245cbc-06ec-4623-81ab-c9aaa9302627" width="600" />


## Contributing

Contributions to this project are welcome. If you encounter any issues or have suggestions for improvements, please open an issue or submit a pull request on the project repository.

## Bibliography

1. [Notation](https://en.wikipedia.org/wiki/Portable_Draughts_Notation)
2. [Rules and variants](https://en.wikipedia.org/wiki/Checkers)
3. [List of PDNs](https://github.com/mig0/Games-Checkers/)
4. [Draughts online](https://lidraughts.org/)
5. [Additional 1 (Checkers online)](https://checkers.online/play)
6. [Additional 2 (Chinook)](https://webdocs.cs.ualberta.ca/~chinook/play/notation.html)