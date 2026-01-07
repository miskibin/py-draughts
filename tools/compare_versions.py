#!/usr/bin/env python
"""
Compare two versions of py-draughts: a snapshot vs current source.

Usage:
    python tools/compare_versions.py                         # latest snapshot vs current
    python tools/compare_versions.py snapshots/snapshot_xxx  # specific snapshot vs current
"""

import csv
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# === Configuration ===
WARMUP_ROUNDS = 5
BENCHMARK_ROUNDS = 10
BENCHMARK_ITERATIONS = 10  # Number of times to run the legal moves benchmark
ENGINE_DEPTH = 3

# === Paths ===
PROJECT_ROOT = Path(__file__).parent.parent
POSITIONS_FILE = PROJECT_ROOT / "test" / "games" / "standard" / "random_positions.json"
OPENINGS_FILE = PROJECT_ROOT / "tools" / "openings.csv"
WORKERS_DIR = PROJECT_ROOT / "tools" / "workers"
RESULTS_CSV = PROJECT_ROOT / "benchmark_results.csv"

console = Console()


def load_openings() -> list[dict]:
    """Load openings from CSV file."""
    openings = []
    with open(OPENINGS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            openings.append({
                "name": row["name"],
                "moves": row["moves"],
                "fen": row["fen"] if row["fen"].strip() else None,
            })
    return openings


def get_hardware_info() -> dict[str, Any]:
    """Collect hardware and system information."""
    info: dict[str, Any] = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }
    
    # Try to get CPU info
    try:
        import cpuinfo
        cpu = cpuinfo.get_cpu_info()
        info["cpu_brand"] = cpu.get("brand_raw", "unknown")
        info["cpu_cores"] = cpu.get("count", "unknown")
    except ImportError:
        info["cpu_brand"] = platform.processor() or "unknown"
        try:
            import os
            info["cpu_cores"] = os.cpu_count() or "unknown"
        except Exception:
            info["cpu_cores"] = "unknown"
    
    # Try to get memory info
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_gb"] = round(mem.total / (1024**3), 1)
    except ImportError:
        info["ram_gb"] = "unknown"
    
    return info


def append_results_to_csv(
    snapshot_name: str,
    git_info: dict,
    lm1_medians: list,
    lm2_medians: list,
    match_stats: dict,
    positions_count: int,
    num_games: int,
    num_openings: int,
):
    """Append benchmark results to CSV file."""
    from statistics import median, mean, stdev
    
    hardware = get_hardware_info()
    
    # Calculate derived metrics
    v1_avg_nodes = match_stats["v1_nodes"] / match_stats["v1_moves"] if match_stats["v1_moves"] else 0
    v2_avg_nodes = match_stats["v2_nodes"] / match_stats["v2_moves"] if match_stats["v2_moves"] else 0
    v1_avg_time = match_stats["v1_time_ms"] / match_stats["v1_moves"] if match_stats["v1_moves"] else 0
    v2_avg_time = match_stats["v2_time_ms"] / match_stats["v2_moves"] if match_stats["v2_moves"] else 0
    
    lm_change_pct = ((median(lm2_medians) - median(lm1_medians)) / median(lm1_medians)) * 100 if median(lm1_medians) else 0
    time_change_pct = ((v2_avg_time - v1_avg_time) / v1_avg_time) * 100 if v1_avg_time else 0
    
    row = {
        # Timestamp
        "timestamp": datetime.now().isoformat(),
        
        # Version info
        "snapshot_name": snapshot_name,
        "snapshot_branch": git_info.get("branch", ""),
        "snapshot_commit": git_info.get("commit", ""),
        "snapshot_dirty": git_info.get("dirty", False),
        
        # Test parameters
        "warmup_rounds": WARMUP_ROUNDS,
        "benchmark_rounds": BENCHMARK_ROUNDS,
        "benchmark_iterations": BENCHMARK_ITERATIONS,
        "engine_depth": ENGINE_DEPTH,
        "num_games": num_games,
        "num_openings": num_openings,
        "positions_count": positions_count,
        
        # Legal moves - snapshot
        "lm_snapshot_median_ms": round(median(lm1_medians), 3),
        "lm_snapshot_mean_ms": round(mean(lm1_medians), 3),
        "lm_snapshot_min_ms": round(min(lm1_medians), 3),
        "lm_snapshot_max_ms": round(max(lm1_medians), 3),
        "lm_snapshot_stdev_ms": round(stdev(lm1_medians), 3) if len(lm1_medians) > 1 else 0,
        
        # Legal moves - current
        "lm_current_median_ms": round(median(lm2_medians), 3),
        "lm_current_mean_ms": round(mean(lm2_medians), 3),
        "lm_current_min_ms": round(min(lm2_medians), 3),
        "lm_current_max_ms": round(max(lm2_medians), 3),
        "lm_current_stdev_ms": round(stdev(lm2_medians), 3) if len(lm2_medians) > 1 else 0,
        "lm_change_pct": round(lm_change_pct, 2),
        
        # Engine match results
        "match_snapshot_wins": match_stats["v1_wins"],
        "match_current_wins": match_stats["v2_wins"],
        "match_draws": match_stats["draws"],
        "match_snapshot_avg_nodes": round(v1_avg_nodes, 1),
        "match_current_avg_nodes": round(v2_avg_nodes, 1),
        "match_snapshot_avg_time_ms": round(v1_avg_time, 2),
        "match_current_avg_time_ms": round(v2_avg_time, 2),
        "match_time_change_pct": round(time_change_pct, 2),
        "match_snapshot_total_nodes": match_stats["v1_nodes"],
        "match_current_total_nodes": match_stats["v2_nodes"],
        
        # Hardware info
        "hw_platform": hardware["platform"],
        "hw_platform_release": hardware["platform_release"],
        "hw_architecture": hardware["architecture"],
        "hw_cpu_brand": hardware["cpu_brand"],
        "hw_cpu_cores": hardware["cpu_cores"],
        "hw_ram_gb": hardware["ram_gb"],
        "hw_python_version": hardware["python_version"],
    }
    
    # Check if file exists to determine if we need headers
    file_exists = RESULTS_CSV.exists()
    
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    
    console.print(f"\n[dim]Results appended to {RESULTS_CSV}[/]")


def create_venv(path: Path) -> Path:
    """Create virtualenv and return python executable path."""
    subprocess.run(["uv", "venv", str(path), "--native-tls"], check=True, capture_output=True)
    if sys.platform == "win32":
        python = path / "Scripts" / "python.exe"
    else:
        python = path / "bin" / "python"
    return python


def install_package(python: Path, source: Path):
    """Install py-draughts from wheel or source, plus psutil for benchmarking."""
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(source), "-q", "--native-tls"],
        check=True,
        capture_output=True,
    )
    # Install psutil for high priority/CPU affinity in benchmarks
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), "psutil", "-q", "--native-tls"],
        check=True,
        capture_output=True,
    )

def run_legal_moves_benchmark(python: Path, iterations: int = 1) -> dict:
    """Run legal moves benchmark in isolated environment.
    
    Args:
        python: Path to Python executable
        iterations: Number of iterations to run (all in one process for stability)
    """
    worker = WORKERS_DIR / "benchmark_legal_moves.py"
    result = subprocess.run(
        [str(python), str(worker), str(POSITIONS_FILE), str(WARMUP_ROUNDS), str(BENCHMARK_ROUNDS), str(iterations)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"error": result.stderr}
    return json.loads(result.stdout)


class EngineWorker:
    """Persistent engine worker that stays alive across multiple moves."""
    
    def __init__(self, python: Path):
        self.python = python
        self.process: subprocess.Popen[str] | None = None
    
    def start(self):
        """Start the worker process."""
        worker = WORKERS_DIR / "engine_worker.py"
        self.process = subprocess.Popen(
            [str(self.python), str(worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env={**__import__("os").environ, "PYTHONUNBUFFERED": "1"},
        )
        # Wait for ready signal
        assert self.process.stdout is not None
        ready = self.process.stdout.readline()
        if not ready:
            # Try to get stderr for better error message
            assert self.process.stderr is not None
            stderr = self.process.stderr.read()
            raise RuntimeError(f"Worker failed to start (no output). stderr: {stderr}")
        try:
            data = json.loads(ready)
            if data.get("status") != "ready":
                raise RuntimeError(f"Worker failed to start: {ready}")
        except json.JSONDecodeError:
            raise RuntimeError(f"Worker failed to start (invalid JSON): {ready}")
    
    def new_game(self, fen: str | None) -> dict:
        """Start a new game from given position."""
        if not self.process or self.process.poll() is not None:
            try:
                self.start()
            except Exception as e:
                return {"error": f"Worker restart failed: {e}"}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        
        cmd = json.dumps({"cmd": "new_game", "fen": fen})
        try:
            self.process.stdin.write(cmd + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            return {"error": f"Worker communication failed: {e}"}
        
        response = self.process.stdout.readline()
        if not response:
            return {"error": "Worker died"}
        return json.loads(response)
    
    def get_move(self, depth: int) -> dict:
        """Get engine move from persistent worker (uses current board state)."""
        if not self.process or self.process.poll() is not None:
            # Worker died, try to restart it
            try:
                self.start()
            except Exception as e:
                return {"error": f"Worker restart failed: {e}"}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        
        cmd = json.dumps({"cmd": "move", "depth": depth})
        try:
            self.process.stdin.write(cmd + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            return {"error": f"Worker communication failed: {e}"}
        
        response = self.process.stdout.readline()
        if not response:
            return {"error": "Worker died"}
        return json.loads(response)
    
    def apply_move(self, move_str: str) -> dict:
        """Apply opponent's move to our board."""
        if not self.process or self.process.poll() is not None:
            try:
                self.start()
            except Exception as e:
                return {"error": f"Worker restart failed: {e}"}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        
        cmd = json.dumps({"cmd": "apply_move", "move": move_str})
        try:
            self.process.stdin.write(cmd + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            return {"error": f"Worker communication failed: {e}"}
        
        response = self.process.stdout.readline()
        if not response:
            return {"error": "Worker died"}
        return json.loads(response)
    
    def stop(self):
        """Stop the worker process."""
        if self.process and self.process.poll() is None:
            try:
                assert self.process.stdin is not None
                self.process.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self.stop()


def get_engine_move(python: Path, fen: str | None, depth: int) -> dict:
    """Get engine move from isolated environment (legacy, spawns new process)."""
    worker = WORKERS_DIR / "get_engine_move.py"
    args = [str(python), str(worker), fen or "", str(depth)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return {"error": result.stderr}
    return json.loads(result.stdout)


def play_match(python1: Path, python2: Path, openings: list[dict], depth: int) -> dict:
    """Play engine vs engine match using persistent workers.
    
    Each opening is played twice: once with v1 as white, once with v2 as white.
    """
    stats = {
        "v1_wins": 0,
        "v2_wins": 0,
        "draws": 0,
        "v1_nodes": 0,
        "v2_nodes": 0,
        "v1_time_ms": 0,
        "v2_time_ms": 0,
        "v1_moves": 0,
        "v2_moves": 0,
    }

    num_games = len(openings) * 2  # Each opening played twice (swap colors)
    game_num = 0

    # Start persistent workers (avoids ~500ms startup per move!)
    with EngineWorker(python1) as worker1, EngineWorker(python2) as worker2:
        with console.status("[bold green]Playing match...") as status:
            for opening in openings:
                opening_name = opening["name"]
                opening_fen = opening["fen"]
                
                # Play each opening twice: v1 as white, then v2 as white
                for swap in range(2):
                    game_num += 1
                    color_info = "snapshot=W" if swap == 0 else "current=W"
                    status.update(f"[bold green]Game {game_num}/{num_games}: {opening_name} ({color_info})...")

                    # Determine who plays white
                    if swap == 0:
                        white_worker, black_worker = worker1, worker2
                        white_ver = "v1"
                    else:
                        white_worker, black_worker = worker2, worker1
                        white_ver = "v2"

                    # Initialize both workers with the opening position
                    # Each worker maintains its own board state for proper draw detection
                    init1 = worker1.new_game(opening_fen)
                    init2 = worker2.new_game(opening_fen)
                    
                    if init1.get("error") or init2.get("error"):
                        console.print(f"[red]Failed to init game: {init1.get('error') or init2.get('error')}[/]")
                        continue

                    move_count = 0
                    result = {}
                    termination = ""
                    
                    # Determine whose turn it is from FEN
                    # FEN starts with 'W:' or 'B:' to indicate turn
                    if opening_fen and opening_fen.startswith("B:"):
                        is_white_turn = False
                    else:
                        is_white_turn = True  # Default to white's turn

                    while move_count < 400:
                        current_worker = white_worker if is_white_turn else black_worker
                        other_worker = black_worker if is_white_turn else white_worker
                        current_ver = white_ver if is_white_turn else ("v2" if white_ver == "v1" else "v1")

                        result = current_worker.get_move(depth)

                        if result.get("error"):
                            termination = "error"
                            break
                        if result.get("game_over"):
                            termination = "game_over"
                            break
                        if not result.get("move"):
                            termination = "no_move"
                            break

                        # Track stats
                        if current_ver == "v1":
                            stats["v1_nodes"] += result.get("nodes", 0)
                            stats["v1_time_ms"] += result.get("time_ms", 0)
                            stats["v1_moves"] += 1
                        else:
                            stats["v2_nodes"] += result.get("nodes", 0)
                            stats["v2_time_ms"] += result.get("time_ms", 0)
                            stats["v2_moves"] += 1

                        # Sync the move to the other worker's board
                        # This preserves move history for proper draw detection
                        sync_result = other_worker.apply_move(result["move"])
                        if sync_result.get("error"):
                            termination = "sync_error"
                            break
                        
                        move_count += 1
                        is_white_turn = not is_white_turn

                    if move_count >= 400 and not termination:
                        termination = "move_limit"

                    # Determine winner
                    game_result = result.get("result", "1/2-1/2")
                    if game_result == "1-0":
                        winner = white_ver
                    elif game_result == "0-1":
                        winner = "v2" if white_ver == "v1" else "v1"
                    else:
                        winner = "draw"

                    winner_label = "draw"
                    if winner == "v1":
                        winner_label = "snapshot"
                    elif winner == "v2":
                        winner_label = "current"

                    full_moves = (move_count + 1) // 2
                    term_suffix = f", term={termination}" if termination else ""
                    console.print(
                        f"Game {game_num}/{num_games} | {opening_name} ({color_info}) | moves={full_moves} (plies={move_count}) | result={game_result} | winner={winner_label}{term_suffix}",
                        highlight=False,
                    )

                    if winner == "v1":
                        stats["v1_wins"] += 1
                    elif winner == "v2":
                        stats["v2_wins"] += 1
                    else:
                        stats["draws"] += 1

    return stats


def find_latest_snapshot() -> Path | None:
    """Find most recent snapshot directory."""
    snapshots_dir = PROJECT_ROOT / "snapshots"
    if not snapshots_dir.exists():
        return None
    dirs = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
    return dirs[-1] if dirs else None


def format_change(old: float, new: float, lower_is_better: bool = True) -> str:
    """Format percentage change with color."""
    if old == 0:
        return "[white]+0.0%[/]"
    change = ((new - old) / old) * 100
    if lower_is_better:
        style = "green" if change < -5 else "red" if change > 5 else "white"
    else:
        style = "red" if change < -5 else "green" if change > 5 else "white"
    return f"[{style}]{change:+.1f}%[/]"


def main():
    # Resolve snapshot path
    if len(sys.argv) > 1:
        snapshot_path = Path(sys.argv[1])
        if not snapshot_path.is_absolute():
            snapshot_path = PROJECT_ROOT / snapshot_path
    else:
        snapshot_path = find_latest_snapshot()

    if not snapshot_path or not snapshot_path.exists():
        console.print("[red]No snapshot found. Create one with: python tools/create_snapshot.py[/]")
        sys.exit(1)

    # Find wheel
    wheels = list(snapshot_path.glob("*.whl"))
    if not wheels:
        console.print(f"[red]No wheel found in {snapshot_path}[/]")
        sys.exit(1)
    wheel = wheels[0]

    # Load metadata
    meta_path = snapshot_path / "metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    git = meta.get("git", {})
    snapshot_label = snapshot_path.name
    if git:
        dirty = "*" if git.get("dirty") else ""
        snapshot_label += f" ({git.get('branch')}@{git.get('commit')}{dirty})"

    console.print(Panel.fit(
        f"[bold]Snapshot:[/] {snapshot_label}\n[bold]Current:[/] source code",
        title="Version Comparison",
        border_style="blue",
    ))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Setup environments
        console.print("\n[bold]Setting up environments...[/]")

        with console.status("[green]Creating snapshot venv..."):
            py1 = create_venv(tmpdir / "venv1")
            install_package(py1, wheel)
        console.print("  ✓ Snapshot ready")

        with console.status("[green]Creating current venv..."):
            py2 = create_venv(tmpdir / "venv2")
            install_package(py2, PROJECT_ROOT)
        console.print("  ✓ Current ready")

        # Legal moves benchmark - run all iterations in single process for stability
        console.print(f"\n[bold]Legal moves benchmark ({BENCHMARK_ITERATIONS} iterations, {BENCHMARK_ROUNDS} rounds each, {WARMUP_ROUNDS} warmup)...[/]")

        with console.status("[green]Benchmarking snapshot (all iterations in one process)..."):
            lm1 = run_legal_moves_benchmark(py1, BENCHMARK_ITERATIONS)
        
        if "error" in lm1:
            console.print(f"[red]Snapshot benchmark error: {lm1['error']}[/]")
            sys.exit(1)
            
        with console.status("[green]Benchmarking current (all iterations in one process)..."):
            lm2 = run_legal_moves_benchmark(py2, BENCHMARK_ITERATIONS)
        
        if "error" in lm2:
            console.print(f"[red]Current benchmark error: {lm2['error']}[/]")
            sys.exit(1)

        # Display individual iteration results
        lm1_medians = lm1.get("iteration_medians", [lm1["median_ms"]])
        lm2_medians = lm2.get("iteration_medians", [lm2["median_ms"]])
        
        for i in range(len(lm1_medians)):
            console.print(f"  Iteration {i + 1}: Snapshot={lm1_medians[i]:.2f}ms, Current={lm2_medians[i]:.2f}ms")

        # Calculate statistics across all iterations
        from statistics import median, mean, stdev

        lm_table = Table(title=f"Legal Moves Benchmark ({BENCHMARK_ITERATIONS} iterations)", box=box.ROUNDED)
        lm_table.add_column("Metric", style="cyan")
        lm_table.add_column("Snapshot", justify="right")
        lm_table.add_column("Current", justify="right")
        lm_table.add_column("Change", justify="right")

        lm_table.add_row(
            f"Positions count",
            f"{lm1['positions_count']}",
            f"{lm2['positions_count']}",
            "",
        )
        lm_table.add_section()
        lm_table.add_row(
            "Median (of medians)",
            f"{median(lm1_medians):.2f} ms",
            f"{median(lm2_medians):.2f} ms",
            format_change(median(lm1_medians), median(lm2_medians)),
        )
        lm_table.add_row(
            "Mean",
            f"{mean(lm1_medians):.2f} ms",
            f"{mean(lm2_medians):.2f} ms",
            format_change(mean(lm1_medians), mean(lm2_medians)),
        )
        lm_table.add_row(
            "Min",
            f"{min(lm1_medians):.2f} ms",
            f"{min(lm2_medians):.2f} ms",
            format_change(min(lm1_medians), min(lm2_medians)),
        )
        lm_table.add_row(
            "Max",
            f"{max(lm1_medians):.2f} ms",
            f"{max(lm2_medians):.2f} ms",
            format_change(max(lm1_medians), max(lm2_medians)),
        )
        if len(lm1_medians) > 1:
            lm_table.add_row(
                "Std Dev",
                f"{stdev(lm1_medians):.2f} ms",
                f"{stdev(lm2_medians):.2f} ms",
                "",
            )

        console.print()
        console.print(lm_table)

        # Load openings
        openings = load_openings()
        num_games = len(openings) * 2  # Each opening played as both colors

        # Engine match
        console.print(f"\n[bold]Engine match ({num_games} games from {len(openings)} openings, depth={ENGINE_DEPTH})...[/]")
        match = play_match(py1, py2, openings, ENGINE_DEPTH)

        # Calculate averages
        v1_avg_nodes = match["v1_nodes"] / match["v1_moves"] if match["v1_moves"] else 0
        v2_avg_nodes = match["v2_nodes"] / match["v2_moves"] if match["v2_moves"] else 0
        v1_avg_time = match["v1_time_ms"] / match["v1_moves"] if match["v1_moves"] else 0
        v2_avg_time = match["v2_time_ms"] / match["v2_moves"] if match["v2_moves"] else 0

        v1_pct = (match["v1_wins"] / num_games) * 100
        v2_pct = (match["v2_wins"] / num_games) * 100
        draw_pct = (match["draws"] / num_games) * 100

        match_table = Table(title=f"Match Results ({num_games} games from {len(openings)} openings)", box=box.ROUNDED)
        match_table.add_column("Metric", style="cyan")
        match_table.add_column("Snapshot", justify="right")
        match_table.add_column("Current", justify="right")
        match_table.add_column("Change", justify="right")

        match_table.add_row("Wins", str(match["v1_wins"]), str(match["v2_wins"]), "")
        match_table.add_row("Win %", f"{v1_pct:.0f}%", f"{v2_pct:.0f}%", "")
        match_table.add_row("Draws", "", "", f"{match['draws']} ({draw_pct:.0f}%)")
        match_table.add_section()
        match_table.add_row(
            "Avg nodes/move",
            f"{v1_avg_nodes:,.0f}",
            f"{v2_avg_nodes:,.0f}",
            format_change(v1_avg_nodes, v2_avg_nodes),
        )
        match_table.add_row(
            "Avg time/move",
            f"{v1_avg_time:.1f} ms",
            f"{v2_avg_time:.1f} ms",
            format_change(v1_avg_time, v2_avg_time),
        )
        match_table.add_row(
            "Total nodes",
            f"{match['v1_nodes']:,}",
            f"{match['v2_nodes']:,}",
            "",
        )

        console.print()
        console.print(match_table)

        # Summary
        console.print()
        lm1_median = median(lm1_medians)
        lm2_median = median(lm2_medians)
        lm_change = ((lm2_median - lm1_median) / lm1_median) * 100 if lm1_median else 0
        time_change = ((v2_avg_time - v1_avg_time) / v1_avg_time) * 100 if v1_avg_time else 0

        if abs(lm_change) < 5 and abs(time_change) < 5:
            console.print("[green]✓ Performance is consistent with snapshot[/]")
        elif lm_change < -5 or time_change < -5:
            console.print("[green]✓ Performance improved![/]")
        else:
            console.print("[yellow]⚠ Performance regression detected[/]")

        if match["draws"] == num_games:
            console.print("[dim]Note: 100% draws expected with identical code (deterministic engine)[/]")

        # Append results to CSV
        append_results_to_csv(
            snapshot_name=snapshot_path.name,
            git_info=git,
            lm1_medians=lm1_medians,
            lm2_medians=lm2_medians,
            match_stats=match,
            positions_count=lm1["positions_count"],
            num_games=num_games,
            num_openings=len(openings),
        )


if __name__ == "__main__":
    main()
