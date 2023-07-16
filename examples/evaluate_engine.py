from pathlib import Path
import matplotlib.pyplot as plt
import json
from draughts.standard import Board, Color
from engine import MiniMaxEngine, AlphaBetaEngine, Engine, RandomEngine
import numpy as np
from time import time

path_to_games = Path().cwd() / "tools/random_positions.json"

with open(path_to_games, "r") as f:
    games = json.load(f)["positions"]
from pprint import pprint


def play_game(fen, engine1: Engine, engine2: Engine) -> list[int, float, float]:
    board = Board.from_fen(fen)
    engine1_time = []
    engine2_time = []
    while not board.game_over:
        start = time()
        if board.turn == Color.WHITE:
            move = engine1.get_best_move(board)
            engine1_time.append(time() - start)
        else:
            move = engine2.get_best_move(board)
            engine2_time.append(time() - start)
        board.push(move)
    engine1_time = sum(engine1_time) / len(engine1_time)
    engine2_time = sum(engine2_time) / len(engine2_time)
    if board.is_threefold_repetition:
        return 1, engine1_time, engine2_time
    if board.turn == Color.WHITE:
        return 2, engine1_time, engine2_time
    if board.turn == Color.BLACK:
        return 0, engine1_time, engine2_time


def plot_grouped_bar(results, labels):
    bar_labels = ("white wins", "draw", "black wins")
    results = np.array(results)
    results = dict(zip(bar_labels, results.T))
    x = np.arange(len(labels))  # the label locations
    width = 0.3  # the width of the bars
    multiplier = 0

    fig, ax = plt.subplots(layout="constrained")

    for attribute, measurement in results.items():
        measurement = np.array(measurement, dtype=np.int8)
        offset = width * multiplier
        rects = ax.bar(x + offset, measurement, width, label=attribute)
        ax.bar_label(rects, padding=2)
        multiplier += 1

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel("Number of games")
    ax.set_title("Results of games")
    ax.legend(loc="upper left")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)

    plt.show()


random = RandomEngine()
simple = MiniMaxEngine(2)
advanced = AlphaBetaEngine(2)


# Play games and update results
labels = ["White Wins", "Draws", "Black Wins"]
results_random_vs_simple = [0, 0, 0]
results_simple_vs_advanced = [0, 0, 0]
results_simple_vs_simple = [0, 0, 0]
random_t, simple_t, advanced_t = [], [], []
for game in games[:]:
    # start = time()
    result, engine1_time, engine2_time = play_game(game, random, simple)
    results_random_vs_simple[result] += 1
    random_t.append(engine1_time)
    simple_t.append(engine2_time)
    result, engine1_time, engine2_time = play_game(game, simple, simple)
    results_simple_vs_simple[result] += 1

    result, engine1_time, engine2_time = play_game(game, simple, advanced)
    results_simple_vs_advanced[result] += 1
    results_simple_vs_advanced[-1] += engine2_time
    advanced_t.append(engine2_time)
# Plot the grouped bar chart
plot_grouped_bar(
    [results_random_vs_simple, results_simple_vs_simple, results_simple_vs_advanced],
    ["Random vs MiniMax", "MiniMax vs MiniMax", "MiniMax vs AlphaBeta"],
)

# plot all average times in bar chart

data = {
    "Random": random_t,
    "MiniMax": simple_t,
    "AlphaBeta ": advanced_t,
}

fig, ax = plt.subplots()
ax.boxplot(data.values())
ax.set_xticklabels(data.keys())
ax.set_ylabel("Time (s)")
ax.set_title("Average time per move")


plt.show()
