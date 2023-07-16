# py-draughts

[![GitHub Actions](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg)](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml)
[![PyPI version](https://badge.fury.io/py/py-draughts.svg)](https://badge.fury.io/py/py-draughts)
[![Downloads](https://static.pepy.tech/personalized-badge/py-draughts?period=month&units=none&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/py-draughts)


Efficient modern and flexible implementation of the draughts game with a beautiful web interface. 
Supports multiple variants of the game and allows playing against AI.

## Installation

```bash
pip install py-draughts
```

## Running UI with default AI

```bash
python -m draughts.server
```

### [Documentation](https://michalskibinski109.github.io/py-draughts/)

## Key features

-  Displays simple ascii board for different variants of the game.

```python
>>> board = get_board('standard', "W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32")
>>> board
 . . . . . B . w . .
 . . . . . . . . . .
 . w . . . . . . . .
 . . . . . . . . . .
 . b . . . . . . . .
 . . b . w . . . . .
 . w . b . W . W . .
 . . . . w . . . w .
 . W . . . w . W . w
 W . w . . . . . . .

>>> board = get_board("american")
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

- Make and undo moves

```python
>>> board.push_uci("37-32")
>>> board.pop() # undo last move
Move: 37->32
```

- detects draws and wins

```python
>>> board.game_over
False
>>> board.is_threefold_repetition
False
```
- Validate and generate moves

```python
>>> board.push_uci("10x42")
Move: 37->32 is correct, but not legal in given position.
Legal moves are: [Move: 28->37, Move: 31->22]

>>> list(board.legal_moves)
[Move: 28->37, Move: 31->22]
```

- Reads and writes fen strings

```python
>>> board = get_board('standard', "W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32")
>>> board.fen
'[FEN "W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32"]'
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
>>> get_best_mv = lambda board: np.random.choice(list(board.legal_moves))
>>> server = Server(get_best_move_method=get_best_mv)
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
