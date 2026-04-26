"""
Smoke tests for the Texel-style eval tuner in ``tools.tune_eval``.

We don't try to hit a target loss — just verify that:

* The dataset builder produces ``(board, label)`` pairs with labels in
  ``[0, 1]``.
* ``fit_K`` returns a positive scale.
* ``coordinate_descent`` improves (or matches) the initial loss.
* The CLI runs end-to-end on a tiny synthetic dataset and writes JSON
  consumable by ``AlphaBetaEngine(eval_params=...)``.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from draughts import AlphaBetaEngine, StandardBoard
from tools import tune_eval


def test_synthetic_dataset_has_labels_in_range() -> None:
    rng = random.Random(0)
    pairs = tune_eval.synthetic_dataset(StandardBoard, n=20, rng=rng)
    assert len(pairs) == 20
    for board, label in pairs:
        assert isinstance(board, StandardBoard)
        assert label in (0.0, 0.5, 1.0)


def test_fit_K_is_positive() -> None:
    rng = random.Random(1)
    dataset = tune_eval.synthetic_dataset(StandardBoard, n=30, rng=rng)
    eng = AlphaBetaEngine(depth_limit=1)
    K = tune_eval.fit_K(dataset, eng.evaluate)
    assert 0 < K < 100  # sanity


def test_coordinate_descent_does_not_regress() -> None:
    """Tuning must not increase the training loss vs the starting params."""
    rng = random.Random(2)
    dataset = tune_eval.synthetic_dataset(StandardBoard, n=40, rng=rng)
    start = dict(AlphaBetaEngine.DEFAULT_EVAL_PARAMS)

    eng = AlphaBetaEngine(depth_limit=1, eval_params=start)
    K0 = tune_eval.fit_K(dataset, eng.evaluate)
    loss_before = tune_eval._loss(dataset, eng.evaluate, K0)

    bounds = {
        "man_value": (1.0, 1.0, 0.0),
        "king_value": (2.5, 4.0, 0.1),
        "tempo": (0.0, 0.2, 0.05),
        "back_rank_bonus": (0.0, 0.3, 0.05),
    }
    tuned = tune_eval.coordinate_descent(start, bounds, dataset, iters=2)

    eng.eval_params = tuned
    K1 = tune_eval.fit_K(dataset, eng.evaluate)
    loss_after = tune_eval._loss(dataset, eng.evaluate, K1)

    assert loss_after <= loss_before + 1e-6, f"loss regressed: {loss_before} -> {loss_after}"


def test_tuned_json_is_consumable_by_engine(tmp_path: Path) -> None:
    """End-to-end: run the CLI on synthetic data and load the result."""
    out = tmp_path / "tuned.json"
    tune_eval.main(
        [
            "--source", "synthetic",
            "--positions", "20",
            "--iters", "1",
            "--seed", "3",
            "--out", str(out),
        ]
    )
    data = json.loads(out.read_text())
    assert set(data.keys()) >= set(AlphaBetaEngine.DEFAULT_EVAL_PARAMS.keys())

    # Engine accepts the tuned params and still produces a legal move.
    eng = AlphaBetaEngine(depth_limit=2, eval_params=data)
    board = StandardBoard()
    move = eng.get_best_move(board)
    assert move in list(board.legal_moves)
