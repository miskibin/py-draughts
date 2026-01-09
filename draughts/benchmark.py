"""
Benchmarking module for comparing draughts engines.

Example:
    >>> from draughts import Benchmark, AlphaBetaEngine
    >>> stats = Benchmark(
    ...     AlphaBetaEngine(depth_limit=4),
    ...     AlphaBetaEngine(depth_limit=6),
    ...     games=10
    ... ).run()
"""

from __future__ import annotations

import csv
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, computed_field

from draughts.boards.base import BaseBoard
from draughts.boards.standard import Board as StandardBoard
from draughts.engines.engine import Engine
from draughts.models import Color
from draughts.move import Move


# Built-in openings for 10x10 boards (name, fen or None)
STANDARD_OPENINGS: list[tuple[str, Optional[str]]] = [
    ("Starting position", "W:W31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20"),
    ("Alma", "B:W17,19,21,24,25,26,27,28,29,30,31,32:B1,2,4,5,6,7,8,9,10,11,12,15"),
    ("Ayrshire Lassie", "B:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,12,15"),
    ("Centre", "B:W18,21,22,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,12,15"),
    ("Defiance", "B:W19,21,22,23,24,25,26,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,12,14,15"),
    ("Douglas", "B:W13,21,22,23,24,26,27,28,29,30,31,32:B1,2,3,5,6,7,8,9,10,11,12,15"),
    ("Dyke", "W:W17,21,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,12,19"),
    ("Edinburgh", "B:W19,21,22,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,11,12,15"),
    ("Fife", "W:W17,19,21,24,25,26,27,28,29,30,31,32:B1,2,3,4,6,7,8,9,10,12,14,15"),
    ("Glasgow", "W:W17,19,21,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,9,10,12,15,16"),
    ("Kelso", "B:W17,21,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,11,12,15"),
    ("Single Corner", "B:W18,21,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,12,15"),
    ("Switcher", "B:W17,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,12,15"),
]


class GameResult(BaseModel):
    """Result of a single game."""
    game_number: int
    winner: Optional[Color] = None
    moves: int = 0
    e1_time: float = 0.0
    e2_time: float = 0.0
    e1_nodes: int = 0
    e2_nodes: int = 0
    e1_color: Color = Color.WHITE
    opening: str = ""
    final_fen: str = ""
    termination: str = "unknown"

    model_config = {"arbitrary_types_allowed": True}


class BenchmarkStats(BaseModel):
    """Aggregated benchmark statistics."""
    e1_name: str
    e2_name: str
    results: list[GameResult] = Field(default_factory=list)
    total_time: float = 0.0

    model_config = {"arbitrary_types_allowed": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def games(self) -> int:
        return len(self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def e1_wins(self) -> int:
        return sum(1 for r in self.results if r.winner == r.e1_color)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def e2_wins(self) -> int:
        return sum(1 for r in self.results if r.winner and r.winner != r.e1_color)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def draws(self) -> int:
        return sum(1 for r in self.results if r.winner is None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def e1_win_rate(self) -> float:
        return (self.e1_wins + self.draws * 0.5) / self.games if self.games else 0.5

    @computed_field  # type: ignore[prop-decorator]
    @property
    def elo_diff(self) -> float:
        """Elo difference (positive = e1 stronger)."""
        if not self.games or self.e1_win_rate <= 0.001:
            return -800.0
        if self.e1_win_rate >= 0.999:
            return 800.0
        try:
            return max(-800, min(800, -400 * math.log10(1 / self.e1_win_rate - 1)))
        except (ValueError, ZeroDivisionError):
            return 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_moves(self) -> float:
        return sum(r.moves for r in self.results) / self.games if self.games else 0

    def _avg_per_move(self, attr: str, engine: int) -> float:
        total = sum(getattr(r, f"e{engine}_{attr}") for r in self.results)
        moves = sum((r.moves + 1) // 2 if (engine == 1) == (r.e1_color == Color.WHITE) 
                    else r.moves // 2 for r in self.results)
        return total / moves if moves else 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_time_e1(self) -> float:
        return self._avg_per_move("time", 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_time_e2(self) -> float:
        return self._avg_per_move("time", 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_nodes_e1(self) -> float:
        return self._avg_per_move("nodes", 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_nodes_e2(self) -> float:
        return self._avg_per_move("nodes", 2)

    def __str__(self) -> str:
        sep = "=" * 60
        return f"""
{sep}
  BENCHMARK: {self.e1_name} vs {self.e2_name}
{sep}

  RESULTS: {self.e1_wins}-{self.e2_wins}-{self.draws} (W-L-D)
  {self.e1_name} win rate: {self.e1_win_rate:.1%}
  Elo difference: {self.elo_diff:+.0f}

  PERFORMANCE
  Avg game length: {self.avg_moves:.1f} moves
  {self.e1_name}: {self.avg_time_e1*1000:.1f}ms/move, {self.avg_nodes_e1:.0f} nodes/move
  {self.e2_name}: {self.avg_time_e2*1000:.1f}ms/move, {self.avg_nodes_e2:.0f} nodes/move
  Total time: {self.total_time:.1f}s

  GAMES
{chr(10).join(f"  {r.game_number:3d}. {'Draw' if not r.winner else (self.e1_name if r.winner==r.e1_color else self.e2_name):15s} ({r.moves} moves)" for r in self.results)}

{sep}
"""

    def to_csv(self, path: Union[str, Path] = "benchmark_results.csv") -> Path:
        """
        Save benchmark results to CSV file.
        
        If the file exists, results are appended. Otherwise, a new file is created
        with headers.
        
        Args:
            path: Path to CSV file (default: "benchmark_results.csv")
        
        Returns:
            Path to the saved CSV file.
        
        Example:
            >>> stats = Benchmark(e1, e2, games=10).run()
            >>> stats.to_csv("results.csv")
        """
        path = Path(path)
        file_exists = path.exists()
        
        fieldnames = [
            "timestamp", "engine1", "engine2", "games", "e1_wins", "e2_wins", 
            "draws", "e1_win_rate", "elo_diff", "avg_moves", "avg_time_e1_ms",
            "avg_time_e2_ms", "avg_nodes_e1", "avg_nodes_e2", "total_time_s"
        ]
        
        row = {
            "timestamp": datetime.now().isoformat(),
            "engine1": self.e1_name,
            "engine2": self.e2_name,
            "games": self.games,
            "e1_wins": self.e1_wins,
            "e2_wins": self.e2_wins,
            "draws": self.draws,
            "e1_win_rate": f"{self.e1_win_rate:.3f}",
            "elo_diff": f"{self.elo_diff:.1f}",
            "avg_moves": f"{self.avg_moves:.1f}",
            "avg_time_e1_ms": f"{self.avg_time_e1 * 1000:.2f}",
            "avg_time_e2_ms": f"{self.avg_time_e2 * 1000:.2f}",
            "avg_nodes_e1": f"{self.avg_nodes_e1:.0f}",
            "avg_nodes_e2": f"{self.avg_nodes_e2:.0f}",
            "total_time_s": f"{self.total_time:.2f}",
        }
        
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        
        return path


def _play_game(
    e1: Engine, e2: Engine, board_class: type[BaseBoard],
    game_num: int, e1_white: bool, opening: tuple[str, Optional[str]], max_moves: int
) -> GameResult:
    """Play a single game and return result."""
    name, fen = opening
    board = board_class.from_fen(f'[FEN "{fen}"]') if fen else board_class()
    
    engines = (e1, e2) if e1_white else (e2, e1)
    e1_color = Color.WHITE if e1_white else Color.BLACK
    e1_time = 0.0
    e2_time = 0.0
    e1_nodes = 0
    e2_nodes = 0
    move_count = 0

    while not board.game_over and move_count < max_moves:
        is_e1 = (board.turn == e1_color)
        eng = engines[0] if board.turn == Color.WHITE else engines[1]
        
        t0 = time.perf_counter()
        try:
            result = eng.get_best_move(board)
            # Handle both Move and (Move, score) return types
            move: Move = result[0] if isinstance(result, tuple) else result
        except Exception:
            winner = Color.BLACK if board.turn == Color.WHITE else Color.WHITE
            return GameResult(
                game_number=game_num, winner=winner, moves=move_count,
                e1_time=e1_time, e2_time=e2_time, e1_nodes=e1_nodes, e2_nodes=e2_nodes,
                e1_color=e1_color, opening=name, final_fen=board.fen, termination="error"
            )
        
        elapsed = time.perf_counter() - t0
        nodes = getattr(eng, "nodes", 0) or getattr(eng, "inspected_nodes", 0)
        
        if is_e1:
            e1_time += elapsed
            e1_nodes += nodes
        else:
            e2_time += elapsed
            e2_nodes += nodes
        
        board.push(move)
        move_count += 1

    # Determine winner
    final_winner: Optional[Color] = None
    if not board.is_draw and move_count < max_moves:
        # Current player has no moves - they lose
        final_winner = Color.BLACK if board.turn == Color.WHITE else Color.WHITE
    
    term = "draw" if board.is_draw else ("max_moves" if move_count >= max_moves else "checkmate")
    
    return GameResult(
        game_number=game_num, winner=final_winner, moves=move_count,
        e1_time=e1_time, e2_time=e2_time, e1_nodes=e1_nodes, e2_nodes=e2_nodes,
        e1_color=e1_color, opening=name, final_fen=board.fen, termination=term
    )


def _engine_label(engine: Engine, suffix: str = "") -> str:
    """Generate a descriptive label for an engine."""
    name = getattr(engine, "name", engine.__class__.__name__)
    parts = []
    if engine.depth_limit is not None:
        parts.append(f"d={engine.depth_limit}")
    if engine.time_limit is not None:
        parts.append(f"t={engine.time_limit}s")
    return f"{name} ({', '.join(parts)}){suffix}" if parts else f"{name}{suffix}"


class Benchmark:
    """
    Benchmark two engines against each other.
    
    Example:
        >>> from draughts import Benchmark, AlphaBetaEngine
        >>> bench = Benchmark(AlphaBetaEngine(depth_limit=4), AlphaBetaEngine(depth_limit=6))
        >>> print(bench.run())
    """
    
    openings: list[tuple[str, Optional[str]]]
    
    def __init__(
        self,
        engine1: Engine,
        engine2: Engine,
        board_class: type[BaseBoard] = StandardBoard,
        games: int = 10,
        openings: Optional[list[str]] = None,
        swap_colors: bool = True,
        max_moves: int = 200,
        workers: int = 1,
    ):
        self.e1, self.e2 = engine1, engine2
        self.board_class = board_class
        self.n_games = games
        self.swap = swap_colors
        self.max_moves = max_moves
        self.workers = max(1, workers)
        
        # Generate unique names if engines have same name
        n1 = getattr(engine1, "name", engine1.__class__.__name__)
        n2 = getattr(engine2, "name", engine2.__class__.__name__)
        if n1 == n2:
            self.e1_name = _engine_label(engine1)
            self.e2_name = _engine_label(engine2)
            # If still same (identical config), add suffix
            if self.e1_name == self.e2_name:
                self.e1_name = _engine_label(engine1, " #1")
                self.e2_name = _engine_label(engine2, " #2")
        else:
            self.e1_name, self.e2_name = n1, n2
        
        if openings:
            self.openings = [(f"Custom {i+1}", f) for i, f in enumerate(openings)]
        elif board_class.SQUARES_COUNT == 50:
            self.openings = list(STANDARD_OPENINGS)
        else:
            self.openings = [("Start", None)]

    def run(self) -> BenchmarkStats:
        """Run benchmark and return statistics."""
        t0 = time.perf_counter()
        results: list[GameResult] = []
        
        configs: list[tuple[int, bool, tuple[str, Optional[str]]]] = [
            (i + 1, i % 2 == 0 if self.swap else True, self.openings[i % len(self.openings)])
            for i in range(self.n_games)
        ]
        
        if self.workers > 1:
            try:
                with ProcessPoolExecutor(max_workers=self.workers) as ex:
                    futures = {ex.submit(_play_game, self.e1, self.e2, self.board_class,
                                         n, w, o, self.max_moves): n for n, w, o in configs}
                    for f in as_completed(futures):
                        r = f.result()
                        results.append(r)
                        self._log(r)
            except Exception:
                results = self._run_sequential(configs)
        else:
            results = self._run_sequential(configs)
        
        results.sort(key=lambda r: r.game_number)
        
        return BenchmarkStats(
            e1_name=self.e1_name,
            e2_name=self.e2_name,
            results=results,
            total_time=time.perf_counter() - t0,
        )

    def _run_sequential(self, configs: list[tuple[int, bool, tuple[str, Optional[str]]]]) -> list[GameResult]:
        results: list[GameResult] = []
        for n, w, o in configs:
            r = _play_game(self.e1, self.e2, self.board_class, n, w, o, self.max_moves)
            results.append(r)
            self._log(r)
        return results

    def _log(self, r: GameResult) -> None:
        w = "Draw" if not r.winner else (self.e1_name if r.winner == r.e1_color else self.e2_name)
        print(f"Game {r.game_number}/{self.n_games}: {w} ({r.moves} moves)")


if __name__ == "__main__":
    from draughts import AlphaBetaEngine
    bench = Benchmark(AlphaBetaEngine(depth_limit=4), AlphaBetaEngine(depth_limit=6), workers=10)
    print(bench.run())
