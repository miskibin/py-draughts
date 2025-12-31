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
import venv
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# === Configuration ===
WARMUP_ROUNDS = 5
BENCHMARK_ROUNDS = 10
BENCHMARK_ITERATIONS = 10  # Number of times to run the legal moves benchmark
ENGINE_DEPTH = 3
NUM_GAMES = 40

# === Paths ===
PROJECT_ROOT = Path(__file__).parent.parent
POSITIONS_FILE = PROJECT_ROOT / "test" / "games" / "standard" / "random_positions.json"
WORKERS_DIR = PROJECT_ROOT / "tools" / "workers"
RESULTS_CSV = PROJECT_ROOT / "benchmark_results.csv"

console = Console()


def get_hardware_info() -> dict:
    """Collect hardware and system information."""
    info = {
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
        "num_games": NUM_GAMES,
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
    venv.create(path, with_pip=True, clear=True)
    if sys.platform == "win32":
        python = path / "Scripts" / "python.exe"
    else:
        python = path / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip", "-q"],
        check=True,
        capture_output=True,
    )
    return python


def install_package(python: Path, source: Path):
    """Install py-draughts from wheel or source."""
    subprocess.run(
        [str(python), "-m", "pip", "install", str(source), "-q"],
        check=True,
        capture_output=True,
    )


def run_legal_moves_benchmark(python: Path) -> dict:
    """Run legal moves benchmark in isolated environment."""
    worker = WORKERS_DIR / "benchmark_legal_moves.py"
    result = subprocess.run(
        [str(python), str(worker), str(POSITIONS_FILE), str(WARMUP_ROUNDS), str(BENCHMARK_ROUNDS)],
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
        self.process = None
    
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
        )
        # Wait for ready signal
        ready = self.process.stdout.readline()
        if not ready or "ready" not in ready:
            raise RuntimeError(f"Worker failed to start: {ready}")
    
    def get_move(self, fen: str | None, depth: int) -> dict:
        """Get engine move from persistent worker."""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("Worker not running")
        
        cmd = json.dumps({"cmd": "move", "fen": fen, "depth": depth})
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()
        
        response = self.process.stdout.readline()
        if not response:
            return {"error": "Worker died"}
        return json.loads(response)
    
    def stop(self):
        """Stop the worker process."""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


def get_engine_move(python: Path, fen: str | None, depth: int) -> dict:
    """Get engine move from isolated environment (legacy, spawns new process)."""
    worker = WORKERS_DIR / "get_engine_move.py"
    args = [str(python), str(worker), fen or "", str(depth)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return {"error": result.stderr}
    return json.loads(result.stdout)


def play_match(python1: Path, python2: Path, num_games: int, depth: int) -> dict:
    """Play engine vs engine match using persistent workers."""
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

    # Start persistent workers (avoids ~500ms startup per move!)
    with EngineWorker(python1) as worker1, EngineWorker(python2) as worker2:
        with console.status("[bold green]Playing match...") as status:
            for game_num in range(num_games):
                status.update(f"[bold green]Game {game_num + 1}/{num_games}...")

                # Alternate who plays white
                if game_num % 2 == 0:
                    white_worker, black_worker = worker1, worker2
                    white_ver = "v1"
                else:
                    white_worker, black_worker = worker2, worker1
                    white_ver = "v2"

                fen = None
                move_count = 0
                result = {}

                while move_count < 200:
                    is_white_turn = move_count % 2 == 0
                    current_worker = white_worker if is_white_turn else black_worker
                    current_ver = white_ver if is_white_turn else ("v2" if white_ver == "v1" else "v1")

                    result = current_worker.get_move(fen, depth)

                    if result.get("error") or result.get("game_over") or not result.get("move"):
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

                    fen = result["fen"]
                    move_count += 1

                # Determine winner
                game_result = result.get("result", "1/2-1/2")
                if game_result == "1-0":
                    winner = white_ver
                elif game_result == "0-1":
                    winner = "v2" if white_ver == "v1" else "v1"
                else:
                    winner = "draw"

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

        # Legal moves benchmark - run multiple iterations
        console.print(f"\n[bold]Legal moves benchmark ({BENCHMARK_ITERATIONS} iterations, {BENCHMARK_ROUNDS} rounds each, {WARMUP_ROUNDS} warmup)...[/]")

        lm1_results = []
        lm2_results = []

        for i in range(BENCHMARK_ITERATIONS):
            with console.status(f"[green]Iteration {i + 1}/{BENCHMARK_ITERATIONS} - Benchmarking snapshot..."):
                lm1 = run_legal_moves_benchmark(py1)
            with console.status(f"[green]Iteration {i + 1}/{BENCHMARK_ITERATIONS} - Benchmarking current..."):
                lm2 = run_legal_moves_benchmark(py2)

            if "error" in lm1 or "error" in lm2:
                console.print(f"[red]Error in iteration {i + 1}: {lm1.get('error', '')} {lm2.get('error', '')}[/]")
                sys.exit(1)

            lm1_results.append(lm1)
            lm2_results.append(lm2)
            console.print(f"  Iteration {i + 1}: Snapshot={lm1['median_ms']:.2f}ms, Current={lm2['median_ms']:.2f}ms")

        # Calculate statistics across all iterations
        from statistics import median, mean, stdev

        lm1_medians = [r["median_ms"] for r in lm1_results]
        lm2_medians = [r["median_ms"] for r in lm2_results]

        lm_table = Table(title=f"Legal Moves Benchmark ({BENCHMARK_ITERATIONS} iterations)", box=box.ROUNDED)
        lm_table.add_column("Metric", style="cyan")
        lm_table.add_column("Snapshot", justify="right")
        lm_table.add_column("Current", justify="right")
        lm_table.add_column("Change", justify="right")

        lm_table.add_row(
            f"Positions count",
            f"{lm1_results[0]['positions_count']}",
            f"{lm2_results[0]['positions_count']}",
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

        # Engine match
        console.print(f"\n[bold]Engine match ({NUM_GAMES} games, depth={ENGINE_DEPTH})...[/]")
        match = play_match(py1, py2, NUM_GAMES, ENGINE_DEPTH)

        # Calculate averages
        v1_avg_nodes = match["v1_nodes"] / match["v1_moves"] if match["v1_moves"] else 0
        v2_avg_nodes = match["v2_nodes"] / match["v2_moves"] if match["v2_moves"] else 0
        v1_avg_time = match["v1_time_ms"] / match["v1_moves"] if match["v1_moves"] else 0
        v2_avg_time = match["v2_time_ms"] / match["v2_moves"] if match["v2_moves"] else 0

        v1_pct = (match["v1_wins"] / NUM_GAMES) * 100
        v2_pct = (match["v2_wins"] / NUM_GAMES) * 100
        draw_pct = (match["draws"] / NUM_GAMES) * 100

        match_table = Table(title=f"Match Results ({NUM_GAMES} games)", box=box.ROUNDED)
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

        if match["draws"] == NUM_GAMES:
            console.print("[dim]Note: 100% draws expected with identical code (deterministic engine)[/]")

        # Append results to CSV
        append_results_to_csv(
            snapshot_name=snapshot_path.name,
            git_info=git,
            lm1_medians=lm1_medians,
            lm2_medians=lm2_medians,
            match_stats=match,
            positions_count=lm1_results[0]["positions_count"],
        )


if __name__ == "__main__":
    main()
