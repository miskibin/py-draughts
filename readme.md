# py-draughts

[![GitHub Actions](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg)](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml)
[![PyPI version](https://badge.fury.io/py/py-draughts.svg)](https://badge.fury.io/py/py-draughts)
[![Downloads](https://static.pepy.tech/badge/py-draughts)](https://pepy.tech/project/py-draughts)

Efficient modern and flexible implementation of the draughts game with a beautiful web interface. 
Supports multiple variants of the game and allows playing against AI.

<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/11e6be5e-0cfc-412c-ac0b-2b8e87a4f450" width="800" style="border-radius: 1%;">

## Installation

```bash
pip install py-draughts
```


### [Documentation](https://miskibin.github.io/py-draughts/)

## Key features

-  Displays simple ascii board for different variants of the game.

```python
>>> from draughts import get_board
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
>>> board.push_uci("31-27")
>>> board.pop() # undo last move
Move: 31->27
>>> board.turn
Color.WHITE
```

- detects draws and wins

> [!Important]  
> Those methods are variant specific. Each variant has different set of them.


```python
>>> board.game_over
False
>>> board.is_threefold_repetition
False
>>> board.is_5_moves_rule
False
>>> board.is_16_moves_rule
False
>>> board.is_25_moves_rule
False
>>> board.is_draw
False
```

- Validate and generate moves

```python
>>> board.push_uci("31-22")
ValueError: 31-22 is correct, but not legal in given position.
Legal moves are: ['31-27', '31-26', '32-28', '32-27', '33-29', '33-28', '34-30', '34-29', '35-30']

>>> list(board.legal_moves)
['31-27', '31-26', '32-28', '32-27', '33-29', '33-28', '34-30', '34-29', '35-30']
```

- Reads and writes fen strings


- Writes PDN strings

```python
>>> board.push_uci("31-27")
>>> board.push_uci("32-28")
>>> board.push_uci("27-23")
>>> board.push_uci("28-24")

>>> board.pdn
'[GameType "20"]
 [Variant "Standard (international) checkers"]
 [Result "-"]
 1. 31-27 32-28 2. 27-23 28-24'
```

```python
>>> board = get_board('standard', "W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32")
>>> board.fen
'[FEN "W:W4,11,28,31,K33,K34,38,40,K41,43,K44,45,K46,47:BK3,21,27,32"]'
```
- Has powerful AI engine

```python
>>> from draughts.engine import AlphaBetaEngine
>>> engine = AlphaBetaEngine(depth=5)
>>> engine.get_best_move(board, with_evaluation=True)
Move: 28->37, 3.0
```

The engine uses **alpha-beta pruning** with several optimizations:
- **Move ordering**: Captures are evaluated first for better pruning
- **Transposition table**: Caches positions to avoid redundant calculations  
- **Enhanced evaluation**: Considers material, positioning, and king promotion

**Performance guide:**
- Depth 3-4: Fast, good for interactive play (~0.1s per move)
- Depth 5-6: Strong play with reasonable speed (~1-5s per move)
- Depth 7+: Very strong but slower, best for analysis (>10s per move)

## UI

1. Allows to play against AI.
2. Allows to play vs another player. (on the same computer)
3. Allows to test and find bugs in your engine.

```python
python -m draughts.server.server
```

#### Use for testing your engine.



_Example with simplest possible engine._



```python
>>> from draughts import Server
>>> import numpy as np
>>> get_best_mv = lambda board: np.random.choice(list(board.legal_moves))
>>> server = Server(get_best_move_method=get_best_mv)
>>> server.run()
INFO:     Started server process [1617]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

_It is as simple as that!_

> [!Warning]  
> Server will not start when using _google colab_

---

<img src="https://github.com/michalskibinski109/py-draughts/assets/77834536/11e4b7ea-4b47-4ab2-80b8-6d6cf1052869" width="800" />


## Contributing

Contributions to this project are welcome. If you encounter any issues or have suggestions for improvements, please open an issue or submit a pull request on the project repository.

## Bibliography

1. [Notation](https://en.wikipedia.org/wiki/Portable_Draughts_Notation)
2. [Rules and variants](https://en.wikipedia.org/wiki/Checkers)
3. [List of PDNs](https://github.com/mig0/Games-Checkers/)
4. [Draughts online](https://lidraughts.org/)
5. [Additional 1 (Checkers online)](https://checkers.online/play)
6. [Additional 2 (Chinook)](https://webdocs.cs.ualberta.ca/~chinook/play/notation.html)
