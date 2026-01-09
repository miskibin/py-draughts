Writing Your Own AI
===================

This guide covers py-draughts features designed for AI developers building
custom agents, neural networks, or reinforcement learning systems.

Quick Example
-------------

Here's a minimal neural network agent using PyTorch:

.. code-block:: python

    import torch
    from draughts import Board, Agent

    class NeuralAgent:
        def __init__(self, model):
            self.model = model

        def select_move(self, board: Board):
            # Convert board to tensor (4 channels, 50 squares)
            x = torch.from_numpy(board.to_tensor()).unsqueeze(0)

            # Get policy logits from your network
            with torch.no_grad():
                logits = self.model(x)[0]

            # Mask illegal moves
            mask = board.legal_moves_mask()
            logits[~mask] = float('-inf')

            # Sample or take argmax
            idx = logits.argmax().item()
            return board.index_to_move(idx)

    # Usage
    board = Board()
    agent = NeuralAgent(your_trained_model)
    move = agent.select_move(board)

Agent Interface
---------------

The :class:`~draughts.Agent` protocol defines the minimal interface for AI agents:

.. code-block:: python

    from draughts import Agent, Board, Move

    class MyAgent:  # Implicitly implements Agent protocol
        def select_move(self, board: Board) -> Move:
            # Your logic here
            return board.legal_moves[0]

    # Type checking confirms protocol compliance
    agent: Agent = MyAgent()

For agents needing configuration, extend :class:`~draughts.BaseAgent`:

.. code-block:: python

    from draughts import BaseAgent, Board, Move

    class ConfigurableAgent(BaseAgent):
        def __init__(self, temperature: float = 1.0):
            super().__init__(name="SoftmaxBot")
            self.temperature = temperature

        def select_move(self, board: Board) -> Move:
            # Use self.temperature for sampling
            ...

.. autoclass:: draughts.Agent
    :members:

.. autoclass:: draughts.BaseAgent
    :members:

Using Agents with Benchmark
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To use agents with :class:`~draughts.Benchmark`, wrap them as engines:

.. code-block:: python

    from draughts import AgentEngine, Benchmark, BaseAgent

    class GreedyAgent(BaseAgent):
        def select_move(self, board):
            return max(board.legal_moves, key=lambda m: len(m.captured_list))

    # Method 1: Use as_engine() on BaseAgent
    engine1 = GreedyAgent().as_engine()

    # Method 2: Wrap any Agent with AgentEngine
    class RandomAgent:
        def select_move(self, board):
            import random
            return random.choice(board.legal_moves)

    engine2 = AgentEngine(RandomAgent(), name="Random")

    # Now benchmark them
    stats = Benchmark(engine1, engine2, games=10).run()

.. autoclass:: draughts.AgentEngine
    :members:

Board Tensor Representation
---------------------------

Use :meth:`~draughts.BaseBoard.to_tensor` to get a neural-network-ready representation:

.. code-block:: python

    from draughts import Board

    board = Board()
    tensor = board.to_tensor()

    print(tensor.shape)  # (4, 50) for 10x10 board

The 4 channels are:

====== ====================================
Channel Description
====== ====================================
0      Own men (1.0 where present)
1      Own kings (1.0 where present)
2      Opponent men (1.0 where present)
3      Opponent kings (1.0 where present)
====== ====================================

By default, "own" is relative to the current turn. Override with ``perspective``:

.. code-block:: python

    from draughts import Color

    # Always from white's perspective (useful for training)
    tensor = board.to_tensor(perspective=Color.WHITE)

Feature Extraction
------------------

For classical ML or analysis, use :meth:`~draughts.BaseBoard.features`:

.. code-block:: python

    from draughts import Board

    board = Board()
    board.push_uci("31-27")
    board.push_uci("18-22")

    f = board.features()
    print(f.white_men)         # 20
    print(f.black_men)         # 20
    print(f.mobility)          # Number of legal moves
    print(f.material_balance)  # (white_men + 2*kings) - (black_men + 2*kings)
    print(f.phase)             # 'opening', 'midgame', or 'endgame'

.. autoclass:: draughts.BoardFeatures
    :members:

Move Indexing for Policy Networks
---------------------------------

Policy networks typically output a fixed-size vector over all possible moves.
py-draughts provides tools to convert between moves and indices:

.. code-block:: python

    board = Board()

    # Get legal move mask (shape: SQUARES^2 = 2500 for 10x10)
    mask = board.legal_moves_mask()

    # Your network outputs logits of shape (2500,)
    logits = model(board.to_tensor())

    # Mask illegal moves
    logits[~mask] = float('-inf')

    # Convert winning index back to move
    best_idx = logits.argmax()
    move = board.index_to_move(best_idx)

    # Or convert a move to index (for training targets)
    target_idx = board.move_to_index(move)

**Index encoding**: ``from_square * SQUARES_COUNT + to_square``

For a 10x10 board (50 squares), indices range from 0 to 2499.

Cheap Position Cloning
----------------------

Tree search and simulation require copying positions. Use :meth:`~draughts.BaseBoard.copy`
for efficient cloning:

.. code-block:: python

    board = Board()

    # Fast copy - only bitboards, no move history
    clone = board.copy()

    # Explore a line
    for move in some_variation:
        clone.push(move)

    # Original unchanged
    assert board.position.tolist() != clone.position.tolist()

The ``copy()`` method is optimized:

- Copies only essential state (bitboards, turn, halfmove clock)
- New board has empty move stack
- ~10x faster than deepcopy

For full state preservation (including move history), use:

.. code-block:: python

    import copy
    full_clone = copy.deepcopy(board)

MCTS Example
------------

Here's a Monte Carlo Tree Search skeleton:

.. code-block:: python

    from draughts import Board, BaseAgent, Move
    import random

    class MCTSAgent(BaseAgent):
        def __init__(self, simulations: int = 1000):
            super().__init__(name=f"MCTS-{simulations}")
            self.simulations = simulations

        def select_move(self, board: Board) -> Move:
            root = Node(board, None)

            for _ in range(self.simulations):
                node = root
                sim_board = board.copy()  # Cheap copy!

                # Selection: walk to leaf
                while node.children and not sim_board.game_over:
                    node = node.select_child()
                    sim_board.push(node.move)

                # Expansion
                if not sim_board.game_over and not node.children:
                    for move in sim_board.legal_moves:
                        node.children.append(Node(sim_board, move))

                # Simulation
                while not sim_board.game_over:
                    sim_board.push(random.choice(sim_board.legal_moves))

                # Backpropagation
                result = sim_board.result
                while node:
                    node.update(result)
                    node = node.parent

            return max(root.children, key=lambda n: n.visits).move

Training Tips
-------------

**State representation**:

.. code-block:: python

    # For CNN: reshape to 2D grid
    tensor = board.to_tensor()  # (4, 50)
    # Note: Only 50 playable squares exist on 10x10 board

    # For flattening to MLP:
    flat = tensor.flatten()  # (200,)

**Data augmentation**: Draughts boards have rotational symmetry. A position
and its 180° rotation are strategically equivalent (with colors swapped):

.. code-block:: python

    # The position array is already 1D over playable squares
    # Reverse it and negate to get the symmetric position
    symmetric_pos = -board.position[::-1]

**Reward shaping**: Use ``features()`` for intermediate rewards:

.. code-block:: python

    f = board.features()
    reward = f.material_balance * 0.01  # Small material reward

**Board variants**: All methods work on any board variant:

.. code-block:: python

    from draughts import AmericanBoard, FrisianBoard

    board = AmericanBoard()  # 8x8, 32 squares
    tensor = board.to_tensor()  # (4, 32)
    mask = board.legal_moves_mask()  # (1024,)


API Reference
-------------

.. automethod:: draughts.BaseBoard.copy
.. automethod:: draughts.BaseBoard.to_tensor
.. automethod:: draughts.BaseBoard.features
.. automethod:: draughts.BaseBoard.legal_moves_mask
.. automethod:: draughts.BaseBoard.move_to_index
.. automethod:: draughts.BaseBoard.index_to_move

