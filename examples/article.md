# I created AI that plays board games without knowing rules.  

Developing a game engine for board games is a fascinating challenge that often requires a deep understanding of the game's rules, strategies, and nuances. However, what if I told you that you could create a game engine without actually having to understand the intricacies of the game itself? In this article, we'll explore a code implementation that demonstrates this concept by using an engine for a game of draughts (checkers) as an example.

## The Power of Abstraction

The key to developing a game engine without deep game-specific knowledge lies in the power of abstraction. By abstracting the game's rules and mechanics into a set of common functionalities, we can create a flexible engine that can be adapted to different board games. There is more then 20 variants of draughts. The engine can play all of them.

The provided code showcases an engine implementation based on the Alpha-Beta Pruning algorithm. This algorithm is widely used in game-playing AI systems to determine the best move in a given game state. By designing the engine to interact with a game server through a standardized interface, we can separate the game-specific details from the engine's logic.

## Environment
For draughts environment I will be use [py-draughts](https://github.com/michalskibinski109/py-draughts) library. It allows to play different variants of checkers using same interface.
Board is representen as `n` squares with values:
- `-2` - white king
- `-1` - white man
- `0` - empty square
- `1` - black man
- `2` - black king


## Implementation
### Implementation

The provided code demonstrates the implementation of a game engine for the game of draughts (checkers) using the Alpha-Beta Pruning algorithm. Let's analyze the code to understand how the engine functions.

#### Evaluation Function

The evaluation function is responsible for assigning a value to a given board position, indicating how favorable it is for the player. In the code, the evaluation function is implemented as follows:

```python
def evaluate(self, board: Board) -> int:
    return -board._pos.sum()
```

#### Random Engine

A simple example implementation of the `Engine` interface is provided by the `RandomEngine` class. This engine selects a random move from the list of legal moves available for the current board state:

```python
class RandomEngine(Engine):
    def get_best_move(self, board: Board = None) -> tuple:
        return np.random.choice(list(board.legal_moves))
```

This engine can be used as a baseline for testing purposes or as a starting point for developing more sophisticated engines.

#### Minimax Engine

The `MiniMaxEngine` class implements the minimax algorithm, a widely used approach for game-playing AI. It explores the game tree up to a specified depth, evaluating the leaf nodes using the provided evaluation function. The engine then selects the move that leads to the best evaluation score:

```python
class MiniMaxEngine:
    def __init__(self, depth):
        self.depth = depth

    def get_best_move(self, board: Board = None) -> tuple:
        best_move = None
        best_evaluation = -100 if board.turn == Color.WHITE else 100
        for move in board.legal_moves:
            board.push(move)
            evaluation = self.__minimax(board, self.depth)
            board.pop()
            if best_move is None or evaluation > best_evaluation:
                best_move = move
                best_evaluation = evaluation
        return move

    def __minimax(self, board: Board, depth: int) -> float:
        if board.game_over:
            return -100 if board.turn == Color.WHITE else 100
        if depth == 0:
            return self.evaluate(board)
        if board.turn == Color.WHITE:
            best_evaluation = -100
            for move in board.legal_moves:
                board.push(move)
                evaluation = self.__minimax(board, depth - 1)
                board.pop()
                best_evaluation = max(best_evaluation, evaluation)
            return best_evaluation
        else:
            best_evaluation = 100
            for move in board.legal_moves:
                board.push(move)
                evaluation = self.__minimax(board, depth - 1)
                board.pop()
                best_evaluation = min(best_evaluation, evaluation)
            return best_evaluation
```

The minimax engine recursively explores the game tree by alternating between maximizing and minimizing players. It keeps track of the best evaluation value found so far and selects the move associated with that value.

#### Alpha-Beta Engine

The `AlphaBetaEngine` class implements the Alpha-Beta Pruning algorithm, an optimization over the minimax algorithm. It avoids exploring certain branches of the game tree that are guaranteed to be worse than previously explored branches, reducing the number of evaluations:

```python
class AlphaBetaEngine:
    def __init__(self, depth):
        self.depth = depth
        self.inspected_nodes = 0

    def get_best_move(self, board: Board = None) -> tuple:
        self.inspected_nodes = 0
        move, evaluation = self.__get_engine_move(board)
        return move

    def __get_engine_move(self, board: Board) -> tuple:
        depth = self.depth
        legal_moves = list(board.legal_moves)
        legal_moves.sort(key=lambda move: board.is_capture(move), reverse=True)
        evals = []
        alpha, beta = -100, 100
        for move in legal_moves:
            board.push(move)
            evals.append(
                self.__alpha_beta_pruning(
                    board,
                    depth - 1,
                    alpha,
                    beta,
                )
            )
            board.pop()
            if board.turn == Color.WHITE:
                alpha = max(alpha, evals[-1])
            else:
                beta = min(beta, evals[-1])
        index = (
            evals.index(max(evals))
            if board.turn == Color.WHITE
            else evals.index(min(evals))
        )
        return legal_moves[index], evals[index]

    def __alpha_beta_pruning(
        self, board: Board, depth: int, alpha: float, beta: float
    ) -> float:
        if board.game_over:
            return -100 if board.turn == Color.WHITE else 100
        if depth == 0:
            self.inspected_nodes += 1
            return self.evaluate(board)
        legal_moves = list(board.legal_moves)
        legal_moves.sort(key=lambda move: board.is_capture(move), reverse=True)
        for move in legal_moves:
            board.push(move)
            evaluation = self.__alpha_beta_pruning(board, depth - 1, alpha, beta)
            board.pop()
            if board.turn == Color.WHITE:
                alpha = max(alpha, evaluation)
            else:
                beta = min(beta, evaluation)
            if beta <= alpha:
                break
        return alpha if board.turn == Color.WHITE else beta
```

The AlphaBetaEngine class extends the Engine interface and provides an implementation for the get_best_move method. It uses the alpha-beta pruning technique to improve the efficiency of the search algorithm by eliminating unnecessary evaluations.


## Results:


## The Potential of Game Engines

The development of game engines that don't require an in-depth understanding of the game rules opens up exciting possibilities. Game developers and enthusiasts can now create AI opponents for their games without needing to master the intricacies of each individual game. This accelerates the development process and allows for a wider range of games to benefit from sophisticated AI opponents.

Furthermore, these game engines can be used as educational tools. By abstracting the game mechanics and focusing on general strategies and algorithms, aspiring game developers and AI enthusiasts can experiment and learn more about various game-playing techniques. It becomes a gateway for exploring the world of artificial intelligence and game theory.

## Conclusion

Creating game engines that don't require an understanding of the game itself is an impressive feat made possible through the power of abstraction. By developing engines based on standardized interfaces and employing algorithms like Alpha-Beta Pruning, we can build intelligent opponents for board games without needing to be experts in each game's rules.

The provided code, although specific to the game of draughts, demonstrates the principles and possibilities of such game engines. By adhering to the engine interface and implementing algorithms that evaluate and determine moves, we can create versatile engines that can be applied to various board games.

Whether you're a game developer looking to enhance your games with AI opponents or an enthusiast interested in exploring artificial intelligence and game theory, developing game engines that don't require deep game-specific knowledge can open up a world of exciting opportunities. Embrace the power of abstraction, algorithmic thinking, and standardized interfaces, and let your game engines bring new dimensions to the world of board games.