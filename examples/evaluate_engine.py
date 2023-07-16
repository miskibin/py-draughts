from pathlib import Path
import matplotlib.pyplot as plt
import json
from draughts.standard import Board, Color
from engine import MiniMaxEngine, AlphaBetaEngine, Engine
import numpy as np

path_to_games = Path().cwd() / "tools/random_positions.json"

with open(path_to_games, "r") as f:
    games = json.load(f)["positions"]
from pprint import pprint


def play_game(fen, engine1: Engine, engine2: Engine) -> int:
    board = Board.from_fen(fen)
    while not board.game_over:
        if board.turn == Color.WHITE:
            move = engine1.get_best_move(board)
        else:
            move = engine2.get_best_move(board)
        board.push(move)

    if board.is_threefold_repetition:
        return 1
    if board.turn == Color.WHITE:
        return 2
    if board.turn == Color.BLACK:
        return 0
    return -1


def plot_grouped_bar(results, labels):
    bar_labels = ("white wins", "draw", "black wins")
    results = np.array(results)
    results = dict(zip(bar_labels, results.T))
    x = np.arange(len(labels))  # the label locations
    width = 0.25  # the width of the bars
    multiplier = 0

    fig, ax = plt.subplots(layout="constrained")

    for attribute, measurement in results.items():
        offset = width * multiplier
        rects = ax.bar(x + offset, measurement, width, label=attribute)
        ax.bar_label(rects, padding=3)
        multiplier += 1

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel("Length (mm)")
    ax.set_title("Penguin attributes by species")
    ax.set_xticks(x + width, labels)
    ax.legend(loc="upper left")

    plt.show()


simple = MiniMaxEngine(3)
advanced = AlphaBetaEngine(3)


# Play games and update results
labels = ["White Wins", "Draws", "Black Wins"]
results_simple_vs_simple = [0, 0, 0]
results_simple_vs_advanced = [0, 0, 0]
for game in games:
    results_simple_vs_simple[play_game(game, simple, simple)] += 1
    results_simple_vs_advanced[play_game(game, simple, advanced)] += 1

# Plot the grouped bar chart
plot_grouped_bar(
    [results_simple_vs_simple, results_simple_vs_advanced],
    ["Simple vs Simple", "Simple vs Advanced"],
)
