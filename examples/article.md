# I created AI that plays board games without knowing rules.  

Developing a game engine for board games is a fascinating challenge that often requires a deep understanding of the game's rules, strategies, and nuances. However, what if I told you that you could create a game engine without actually having to understand the intricacies of the game itself? In this article, we'll explore a code implementation that demonstrates this concept by using an engine for a game of draughts (checkers) as an example.

## The Power of Abstraction

The key to developing a game engine without deep game-specific knowledge lies in the power of abstraction. By abstracting the game's rules and mechanics into a set of common functionalities, we can create a flexible engine that can be adapted to different board games. There is more then 20 variants of draughts. The engine can play all of them.

The provided code showcases an engine implementation based on the Alpha-Beta Pruning algorithm. This algorithm is widely used in game-playing AI systems to determine the best move in a given game state. By designing the engine to interact with a game server through a standardized interface, we can separate the game-specific details from the engine's logic.


## The Alpha-Beta Engine Implementation

The `AlphaBetaEngine` class demonstrates the concrete implementation of the engine using the Alpha-Beta Pruning algorithm. It includes methods for move evaluation, determining the best move, and performing the pruning process. While the code itself focuses on the specific game of draughts, the underlying principles can be applied to other board games as well.

The `evaluate()` method assigns a score to a given board configuration, representing its desirability. In the provided implementation, the score is simply calculated by negating the sum of the board positions. This simplistic evaluation function can be refined and customized for each game to reflect the specific strategies and objectives.

The `get_best_move()` method orchestrates the move calculation process. It iterates over the legal moves, evaluates each move's outcome using the Alpha-Beta Pruning algorithm, and selects the move with the highest or lowest evaluation, depending on the current player. By doing so, it identifies the move that is expected to lead to the most favorable game state.

## Environment
For draughts environment I will be use [py-draughts](https://github.com/michalskibinski109/py-draughts) library. It allows to play different variants of checkers using same interface.
Board is representen as `n` squares with values:
- `-2` - white king
- `-1` - white man
- `0` - empty square
- `1` - black man
- `2` - black king


## Implementation

### Evaluation
Our evaluation function can evaluate position like this regardless size of the board, **without understanding it**
```python
    def evaluate(self, board: Board) -> int:
        return -board._pos.sum()
```

### searching alghoritm (_alpha_beta_puring_)


For evalutating position we will just sum all pieces on the board

## The Potential of Game Engines

The development of game engines that don't require an in-depth understanding of the game rules opens up exciting possibilities. Game developers and enthusiasts can now create AI opponents for their games without needing to master the intricacies of each individual game. This accelerates the development process and allows for a wider range of games to benefit from sophisticated AI opponents.

Furthermore, these game engines can be used as educational tools. By abstracting the game mechanics and focusing on general strategies and algorithms, aspiring game developers and AI enthusiasts can experiment and learn more about various game-playing techniques. It becomes a gateway for exploring the world of artificial intelligence and game theory.

## Conclusion

Creating game engines that don't require an understanding of the game itself is an impressive feat made possible through the power of abstraction. By developing engines based on standardized interfaces and employing algorithms like Alpha-Beta Pruning, we can build intelligent opponents for board games without needing to be experts in each game's rules.

The provided code, although specific to the game of draughts, demonstrates the principles and possibilities of such game engines. By adhering to the engine interface and implementing algorithms that evaluate and determine moves, we can create versatile engines that can be applied to various board games.

Whether you're a game developer looking to enhance your games with AI opponents or an enthusiast interested in exploring artificial intelligence and game theory, developing game engines that don't require deep game-specific knowledge can open up a world of exciting opportunities. Embrace the power of abstraction, algorithmic thinking, and standardized interfaces, and let your game engines bring new dimensions to the world of board games.