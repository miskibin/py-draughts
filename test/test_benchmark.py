"""Tests for the benchmark module."""

import pytest
from draughts import (
    Benchmark, BenchmarkStats, GameResult, STANDARD_OPENINGS,
    AlphaBetaEngine, StandardBoard, AmericanBoard, FrisianBoard, RussianBoard,
    Color,
)
from draughts.benchmark import _engine_label


class TestGameResult:
    """Tests for GameResult model."""

    def test_default_values(self):
        result = GameResult(game_number=1)
        assert result.game_number == 1
        assert result.winner is None
        assert result.moves == 0
        assert result.e1_time == 0.0
        assert result.e2_time == 0.0
        assert result.termination == "unknown"

    def test_with_winner(self):
        result = GameResult(game_number=1, winner=Color.WHITE, moves=50)
        assert result.winner == Color.WHITE
        assert result.moves == 50


class TestBenchmarkStats:
    """Tests for BenchmarkStats model."""

    def test_empty_results(self):
        stats = BenchmarkStats(e1_name="A", e2_name="B")
        assert stats.games == 0
        assert stats.e1_wins == 0
        assert stats.e2_wins == 0
        assert stats.draws == 0
        assert stats.e1_win_rate == 0.5

    def test_computed_fields(self):
        results = [
            GameResult(game_number=1, winner=Color.WHITE, moves=40, e1_color=Color.WHITE),
            GameResult(game_number=2, winner=Color.BLACK, moves=50, e1_color=Color.WHITE),
            GameResult(game_number=3, winner=None, moves=60, e1_color=Color.BLACK),
        ]
        stats = BenchmarkStats(e1_name="A", e2_name="B", results=results)
        
        assert stats.games == 3
        assert stats.e1_wins == 1  # Game 1: e1=WHITE won
        assert stats.e2_wins == 1  # Game 2: BLACK won, e1=WHITE so e2 wins
        assert stats.draws == 1
        assert stats.avg_moves == 50.0

    def test_elo_difference_even(self):
        """50% win rate should give ~0 Elo difference."""
        results = [
            GameResult(game_number=1, winner=Color.WHITE, moves=40, e1_color=Color.WHITE),
            GameResult(game_number=2, winner=Color.BLACK, moves=40, e1_color=Color.WHITE),
        ]
        stats = BenchmarkStats(e1_name="A", e2_name="B", results=results)
        assert abs(stats.elo_diff) < 10

    def test_elo_difference_dominant(self):
        """All wins should give high Elo difference."""
        results = [
            GameResult(game_number=i, winner=Color.WHITE, moves=40, e1_color=Color.WHITE)
            for i in range(1, 11)
        ]
        stats = BenchmarkStats(e1_name="A", e2_name="B", results=results)
        assert stats.elo_diff == 800.0  # Capped at max

    def test_str_output(self):
        results = [GameResult(game_number=1, winner=None, moves=30, e1_color=Color.WHITE)]
        stats = BenchmarkStats(e1_name="E1", e2_name="E2", results=results, total_time=1.5)
        output = str(stats)
        
        assert "BENCHMARK" in output
        assert "E1" in output
        assert "E2" in output
        assert "Draw" in output


class TestEngineLabel:
    """Tests for engine labeling."""

    def test_label_with_depth(self):
        engine = AlphaBetaEngine(depth_limit=5)
        label = _engine_label(engine)
        assert "d=5" in label
        assert "AlphaBetaEngine" in label

    def test_label_with_time(self):
        engine = AlphaBetaEngine(depth_limit=None, time_limit=2.0)
        label = _engine_label(engine)
        assert "t=2.0s" in label

    def test_label_with_both(self):
        engine = AlphaBetaEngine(depth_limit=6, time_limit=1.0)
        label = _engine_label(engine)
        assert "d=6" in label
        assert "t=1.0s" in label

    def test_label_with_suffix(self):
        engine = AlphaBetaEngine(depth_limit=4)
        label = _engine_label(engine, " #1")
        assert label.endswith(" #1")

    def test_custom_name(self):
        engine = AlphaBetaEngine(depth_limit=4, name="MyBot")
        label = _engine_label(engine)
        assert "MyBot" in label


class TestBenchmarkInit:
    """Tests for Benchmark initialization."""

    def test_default_openings_standard(self):
        e1 = AlphaBetaEngine(depth_limit=2)
        e2 = AlphaBetaEngine(depth_limit=2)
        bench = Benchmark(e1, e2, board_class=StandardBoard)
        assert len(bench.openings) == len(STANDARD_OPENINGS)

    def test_default_openings_american(self):
        """Non-50 square boards should use starting position."""
        e1 = AlphaBetaEngine(depth_limit=2)
        e2 = AlphaBetaEngine(depth_limit=2)
        bench = Benchmark(e1, e2, board_class=AmericanBoard)
        assert len(bench.openings) == 1
        assert bench.openings[0][0] == "Start"

    def test_custom_openings(self):
        e1 = AlphaBetaEngine(depth_limit=2)
        e2 = AlphaBetaEngine(depth_limit=2)
        custom = ["W:W31,32:B1,2", "B:W40:B10"]
        bench = Benchmark(e1, e2, openings=custom)
        assert len(bench.openings) == 2
        assert bench.openings[0][0] == "Custom 1"
        assert bench.openings[1][0] == "Custom 2"

    def test_same_name_engines_distinguished(self):
        e1 = AlphaBetaEngine(depth_limit=3)
        e2 = AlphaBetaEngine(depth_limit=5)
        bench = Benchmark(e1, e2)
        assert "d=3" in bench.e1_name
        assert "d=5" in bench.e2_name
        assert bench.e1_name != bench.e2_name

    def test_identical_engines_get_suffix(self):
        e1 = AlphaBetaEngine(depth_limit=4)
        e2 = AlphaBetaEngine(depth_limit=4)
        bench = Benchmark(e1, e2)
        assert "#1" in bench.e1_name
        assert "#2" in bench.e2_name

    def test_different_names_preserved(self):
        e1 = AlphaBetaEngine(depth_limit=3, name="Bot1")
        e2 = AlphaBetaEngine(depth_limit=5, name="Bot2")
        bench = Benchmark(e1, e2)
        assert bench.e1_name == "Bot1"
        assert bench.e2_name == "Bot2"


class TestBenchmarkRun:
    """Tests for running benchmarks."""

    def test_run_returns_stats(self):
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, games=2, max_moves=10)
        stats = bench.run()
        
        assert isinstance(stats, BenchmarkStats)
        assert stats.games == 2
        assert len(stats.results) == 2

    def test_swap_colors(self):
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, games=4, max_moves=5, swap_colors=True)
        stats = bench.run()
        
        colors = [r.e1_color for r in stats.results]
        assert Color.WHITE in colors
        assert Color.BLACK in colors

    def test_no_swap_colors(self):
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, games=3, max_moves=5, swap_colors=False)
        stats = bench.run()
        
        assert all(r.e1_color == Color.WHITE for r in stats.results)

    def test_max_moves_respected(self):
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, games=1, max_moves=10)
        stats = bench.run()
        
        assert stats.results[0].moves <= 10

    def test_game_numbers_sequential(self):
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, games=5, max_moves=5)
        stats = bench.run()
        
        numbers = [r.game_number for r in stats.results]
        assert numbers == [1, 2, 3, 4, 5]


class TestBenchmarkBoardVariants:
    """Tests for different board variants."""

    @pytest.mark.parametrize("board_class", [StandardBoard, AmericanBoard, RussianBoard])
    def test_board_variant(self, board_class):
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, board_class=board_class, games=1, max_moves=10)
        stats = bench.run()
        
        assert stats.games == 1
        assert len(stats.results) == 1

    def test_frisian_variant(self):
        """Frisian has different rules, verify it works."""
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        bench = Benchmark(e1, e2, board_class=FrisianBoard, games=1, max_moves=10)
        stats = bench.run()
        
        assert stats.games == 1


class TestBenchmarkOpenings:
    """Tests for opening handling."""

    def test_openings_cycle(self):
        """Openings should cycle when games > openings."""
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        # Only 2 custom openings, but 4 games
        bench = Benchmark(e1, e2, games=4, max_moves=5,
                          openings=["W:W31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20",
                                    "B:W31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20"])
        stats = bench.run()
        
        openings = [r.opening for r in stats.results]
        assert openings[0] == "Custom 1"
        assert openings[1] == "Custom 2"
        assert openings[2] == "Custom 1"  # Cycles back
        assert openings[3] == "Custom 2"

    def test_invalid_opening_fen(self):
        """Invalid FEN should raise an error during game."""
        e1 = AlphaBetaEngine(depth_limit=1)
        e2 = AlphaBetaEngine(depth_limit=1)
        
        # This should raise when trying to parse invalid FEN
        with pytest.raises(Exception):
            bench = Benchmark(e1, e2, games=1, openings=["invalid_fen_string"])
            bench.run()


class TestStandardOpenings:
    """Tests for built-in openings."""

    def test_openings_not_empty(self):
        assert len(STANDARD_OPENINGS) > 0

    def test_openings_have_names_and_fens(self):
        for name, fen in STANDARD_OPENINGS:
            assert isinstance(name, str)
            assert len(name) > 0
            assert isinstance(fen, str)
            assert len(fen) > 0

    def test_all_openings_parse(self):
        """All built-in openings should be valid FENs."""
        for name, fen in STANDARD_OPENINGS:
            try:
                board = StandardBoard.from_fen(f'[FEN "{fen}"]')
                assert board is not None
            except Exception as e:
                pytest.fail(f"Opening '{name}' failed to parse: {e}")


class TestEngineNameParameter:
    """Tests for engine name parameter."""

    def test_engine_default_name(self):
        engine = AlphaBetaEngine(depth_limit=5)
        assert engine.name == "AlphaBetaEngine"

    def test_engine_custom_name(self):
        engine = AlphaBetaEngine(depth_limit=5, name="MyCustomEngine")
        assert engine.name == "MyCustomEngine"

    def test_benchmark_uses_custom_name(self):
        e1 = AlphaBetaEngine(depth_limit=3, name="FastBot")
        e2 = AlphaBetaEngine(depth_limit=5, name="StrongBot")
        bench = Benchmark(e1, e2, games=1, max_moves=5)
        stats = bench.run()
        
        assert stats.e1_name == "FastBot"
        assert stats.e2_name == "StrongBot"


class TestCsvExport:
    """Tests for CSV export functionality."""

    def test_to_csv_creates_file(self, tmp_path):
        results = [GameResult(game_number=1, winner=None, moves=30, e1_color=Color.WHITE)]
        stats = BenchmarkStats(e1_name="E1", e2_name="E2", results=results, total_time=1.0)
        
        csv_path = tmp_path / "test.csv"
        returned_path = stats.to_csv(csv_path)
        
        assert csv_path.exists()
        assert returned_path == csv_path

    def test_to_csv_has_header(self, tmp_path):
        results = [GameResult(game_number=1, winner=None, moves=30, e1_color=Color.WHITE)]
        stats = BenchmarkStats(e1_name="E1", e2_name="E2", results=results, total_time=1.0)
        
        csv_path = tmp_path / "test.csv"
        stats.to_csv(csv_path)
        
        content = csv_path.read_text()
        assert "timestamp" in content
        assert "engine1" in content
        assert "elo_diff" in content

    def test_to_csv_appends(self, tmp_path):
        csv_path = tmp_path / "test.csv"
        
        # First save
        results1 = [GameResult(game_number=1, winner=None, moves=30, e1_color=Color.WHITE)]
        stats1 = BenchmarkStats(e1_name="A", e2_name="B", results=results1, total_time=1.0)
        stats1.to_csv(csv_path)
        
        # Second save (should append)
        results2 = [GameResult(game_number=1, winner=Color.WHITE, moves=40, e1_color=Color.WHITE)]
        stats2 = BenchmarkStats(e1_name="C", e2_name="D", results=results2, total_time=2.0)
        stats2.to_csv(csv_path)
        
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows

    def test_to_csv_no_duplicate_header(self, tmp_path):
        csv_path = tmp_path / "test.csv"
        
        results = [GameResult(game_number=1, winner=None, moves=30, e1_color=Color.WHITE)]
        stats = BenchmarkStats(e1_name="E1", e2_name="E2", results=results, total_time=1.0)
        
        # Save twice
        stats.to_csv(csv_path)
        stats.to_csv(csv_path)
        
        content = csv_path.read_text()
        # Header should appear only once
        assert content.count("timestamp,engine1") == 1

    def test_to_csv_correct_values(self, tmp_path):
        results = [
            GameResult(game_number=1, winner=Color.WHITE, moves=40, e1_color=Color.WHITE),
            GameResult(game_number=2, winner=None, moves=50, e1_color=Color.BLACK),
        ]
        stats = BenchmarkStats(e1_name="Alpha", e2_name="Beta", results=results, total_time=5.5)
        
        csv_path = tmp_path / "test.csv"
        stats.to_csv(csv_path)
        
        content = csv_path.read_text()
        assert "Alpha" in content
        assert "Beta" in content
        assert ",2," in content  # 2 games

