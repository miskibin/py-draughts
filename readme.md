# py-draughts

[![GitHub Actions](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml/badge.svg)](https://github.com/michalskibinski109/checkers/actions/workflows/python-app.yml)
[![PyPI version](https://badge.fury.io/py/py-draughts.svg)](https://badge.fury.io/py/py-draughts)
[![Downloads](https://static.pepy.tech/badge/py-draughts)](https://pepy.tech/project/py-draughts)
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://miskibin.github.io/py-draughts/)

Fast, modern draughts library with move generation, validation, PDN support, and AI engine.

> [!IMPORTANT]  
> Best optimized draughts library utilizing bitboards for ~200x faster move generation than alternatives.

<img width="1905" alt="Web UI" src="https://github.com/user-attachments/assets/8c3e255e-7fbb-4ae6-a9ab-2445c486c349" />

## [Installation](https://miskibin.github.io/py-draughts/)

```bash
pip install py-draughts
```

## [Core](https://miskibin.github.io/py-draughts/core.html)

```python
>>> import draughts
>>> board = draughts.Board()

>>> board.legal_moves
[Move: 31->27, Move: 31->26, Move: 32->28, ...]

>>> board.push_uci("31-27")
>>> board.push_uci("18-22")
>>> board.push_uci("27x18")
>>> board.push_uci("12x23")

>>> board
 . b . b . b . b . b
 b . b . b . b . b .
 . b . b . . . b . b
 . . . . b . b . b .
 . . . b . . . . . .
 . . . . . . . . . .
 . w . w . w . w . w
 w . w . w . w . w .
 . w . w . w . w . w
 w . w . w . w . w .

>>> board.pop()  # Unmake the last move
Move: 12->23

>>> board.turn
Color.WHITE
```

### Make and unmake moves

```python
>>> board.push_uci("32-28")  # Make a move
>>> board.pop()              # Unmake the last move
Move: 32->28
```

### Show ASCII board

```python
>>> board = draughts.Board()
>>> print(board)
 . b . b . b . b . b     .  1 .  2 .  3 .  4 .  5
 b . b . b . b . b .      6 .  7 .  8 .  9 . 10 .
 . b . b . b . b . b     . 11 . 12 . 13 . 14 . 15
 b . b . b . b . b .     16 . 17 . 18 . 19 . 20 .
 . . . . . . . . . .     . 21 . 22 . 23 . 24 . 25
 . . . . . . . . . .     26 . 27 . 28 . 29 . 30 .
 . w . w . w . w . w     . 31 . 32 . 33 . 34 . 35
 w . w . w . w . w .     36 . 37 . 38 . 39 . 40 .
 . w . w . w . w . w     . 41 . 42 . 43 . 44 . 45
 w . w . w . w . w .     46 . 47 . 48 . 49 . 50 .
```

### Detects draws and game end

```python
>>> board.is_draw
False
>>> board.is_threefold_repetition
False
>>> board.game_over
False
>>> board.result
'-'
```

### [FEN](https://miskibin.github.io/py-draughts/core.html#notation) parsing and writing

```python
>>> board.fen
'[FEN "W:W:W31,32,33,...:B1,2,3,..."]'

>>> board = draughts.Board.from_fen("W:WK10,K20:BK35,K45")
>>> board
 . . . . . . . B . .
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . . . . . . .
 . . . . W . . . . .
 . . . . . . . . . .
 . . . . W . . . . .
 B . . . . . . . . .
```

### [PDN](https://miskibin.github.io/py-draughts/core.html#notation) parsing and writing

```python
>>> board = draughts.Board()
>>> board.push_uci("32-28")
>>> board.push_uci("18-23")
>>> board.pdn
'[GameType "20"]
[Variant "Standard (international) checkers"]
[Result "-"]
1. 32-28 18-23'

>>> board = draughts.Board.from_pdn('[GameType "20"]\n1. 32-28 19-23 2. 28x19 14x23')
```

## [Variants](https://miskibin.github.io/py-draughts/core.html#boards)

| Variant | Class | Board | Flying Kings | Max Capture |
|---------|-------|-------|--------------|-------------|
| Standard | `StandardBoard` | 10×10 | Yes | Required |
| American | `AmericanBoard` | 8×8 | No | Not required |
| Frisian | `FrisianBoard` | 10×10 | Yes | Required |
| Russian | `RussianBoard` | 8×8 | Yes | Not required |

```python
>>> from draughts import StandardBoard, AmericanBoard, FrisianBoard, RussianBoard

>>> board = AmericanBoard()
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

## [SVG Rendering](https://miskibin.github.io/py-draughts/svg.html)

```python
>>> import draughts
>>> board = draughts.Board()
>>> draughts.svg.board(board, size=400)  # Returns SVG string
```

<img src="docs/source/_static/board_standard.svg" alt="Standard draughts board" width="400">

```python
>>> board = draughts.Board.from_fen("W:WK10,K20:BK35,K45")
>>> draughts.svg.board(board, size=400)
```

<img src="docs/source/_static/board_kings.svg" alt="Board with kings" width="400">

## [Engine](https://miskibin.github.io/py-draughts/engine.html)

Built-in alpha-beta engine with transposition tables and iterative deepening:

```python
>>> from draughts import Board, AlphaBetaEngine

>>> board = Board()
>>> engine = AlphaBetaEngine(depth_limit=5)

>>> move = engine.get_best_move(board)
>>> move
Move: 32->28

>>> move, score = engine.get_best_move(board, with_evaluation=True)
>>> score
0.15
```

### External Engines (Hub Protocol)

Use external engines like [Scan](https://hjetten.home.xs4all.nl/scan/scan.html) via the Hub protocol:

```python
>>> from draughts import Board, HubEngine

>>> with HubEngine("path/to/scan.exe", time_limit=1.0) as engine:
...     board = Board()
...     move, score = engine.get_best_move(board, with_evaluation=True)
...     print(f"Best: {move}, Score: {score}")
Best: 32-28, Score: 0.15
```

## [Server](https://miskibin.github.io/py-draughts/server.html)

Interactive web interface for playing and engine testing:

```python
from draughts import Board, Server, AlphaBetaEngine, HubEngine

server = Server(
    board=Board(),
    white_engine=AlphaBetaEngine(depth_limit=6),
    black_engine=HubEngine("path/to/scan.exe", time_limit=1.0)
)
server.run() # Open http://localhost:8000
```

<img width="1914" height="1022" alt="image" src="https://github.com/user-attachments/assets/20fefe48-c0d8-470d-b7d8-b9fd4e9d72e0" />


## [Performance](https://miskibin.github.io/py-draughts/benchmarking.html)

Legal moves generation in **~10-30 microseconds**:

| Operation | py-draughts | pydraughts | Speedup |
|-----------|-------------|------------|---------|
| Board init | 2.30 µs | 547.10 µs | **238x faster** |
| FEN parse | 21.00 µs | 358.90 µs | **17x faster** |
| Legal moves | 17.40 µs | 3.61 ms | **207x faster** |
| Make move | 0.90 µs | 507.75 µs | **564x faster** |

<img src="docs/source/_static/speed_comparison.png" alt="Speed Comparison Chart" width="700">

Engine search at various depths:

| Depth | Time | Nodes |
|-------|------|-------|
| 5 | 130 ms | 3,525 |
| 6 | 350 ms | 9,537 |
| 7 | 933 ms | 25,202 |
| 8 | 4.9 s | 122,168 |

<img src="docs/source/_static/engine_benchmark.png" alt="Engine Benchmark" width="600">

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## License

py-draughts is licensed under the GPL 3.
