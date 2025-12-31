#!/usr/bin/env python
"""
Compare two versions of py-draughts: a snapshot vs current source.

Usage:
    python tools/compare_versions.py                    # compares latest snapshot vs current
    python tools/compare_versions.py snapshots/snapshot_xxx  # compares specific snapshot vs current
"""

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from statistics import median

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Config
WARMUP_ROUNDS = 3
BENCHMARK_ROUNDS = 10
ENGINE_DEPTH = 3
NUM_GAMES = 20

# Test positions (subset for speed)
TEST_POSITIONS = [
    "W:W31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50:B1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20",
    "W:WK4,K5,29,31:B18,K20,22",
    "B:WK28,32,K38:BK18",
    "W:W25,26,32,34,35,37,38,42,43,45:B3,5,6,9,11,13,14,16,24,27",
    "B:W25,26,30,33,35,40,42,43:B3,5,6,9,18,19,24,27",
    "W:WK15,20,26,35:B3,5,6,37,K47",
    "B:W21,K33:B5,6,14,K36",
    "W:WK25:B6,10,K15",
    "B:W24,26,28,29,34,36,37:B3,13,15,17,20,25,27",
    "W:W25,26,32,33,35,36,38,39,40,48:B6,8,12,13,14,15,16,17,23,24",
]


# Benchmark script that runs in isolated venv
BENCHMARK_SCRIPT = '''
import json
import logging
import time
from statistics import median

logging.disable(logging.CRITICAL)

POSITIONS = __POSITIONS__
WARMUP = __WARMUP__
ROUNDS = __ROUNDS__
DEPTH = __DEPTH__

from draughts import get_board
from draughts.engine import AlphaBetaEngine

results = {"legal_moves": {}, "engine": {}}

# Legal moves benchmark
times = []
for _ in range(WARMUP + ROUNDS):
    start = time.perf_counter()
    for fen in POSITIONS:
        if fen.startswith("B:B:") or fen.startswith("W:W:"):
            fen = fen[2:]
        board = get_board("standard", fen)
        list(board.legal_moves)
    elapsed = time.perf_counter() - start
    times.append(elapsed)

results["legal_moves"]["times"] = times[WARMUP:]
results["legal_moves"]["median_ms"] = median(times[WARMUP:]) * 1000

# Engine benchmark  
times = []
nodes = []
for _ in range(WARMUP + ROUNDS):
    total_nodes = 0
    start = time.perf_counter()
    for fen in POSITIONS[:5]:  # fewer positions for engine
        if fen.startswith("B:B:") or fen.startswith("W:W:"):
            fen = fen[2:]
        board = get_board("standard", fen)
        if not board.game_over:
            engine = AlphaBetaEngine(depth=DEPTH)  # fresh engine each position
            engine.get_best_move(board)
            total_nodes += engine.inspected_nodes
    elapsed = time.perf_counter() - start
    times.append(elapsed)
    nodes.append(total_nodes)

results["engine"]["times"] = times[WARMUP:]
results["engine"]["median_ms"] = median(times[WARMUP:]) * 1000
results["engine"]["median_nodes"] = int(median(nodes[WARMUP:]))

print(json.dumps(results))
'''

GAME_SCRIPT = '''
import json
import logging
logging.disable(logging.CRITICAL)

from draughts import get_board
from draughts.engine import AlphaBetaEngine

fen = "__FEN__"
depth = __DEPTH__

board = get_board("standard", fen) if fen else get_board("standard")

if board.game_over:
    print(json.dumps({"move": None, "fen": board.fen, "game_over": True, "result": board.result}))
else:
    engine = AlphaBetaEngine(depth=depth)
    move = engine.get_best_move(board)
    if move:
        board.push(move)
        print(json.dumps({"move": str(move), "fen": board.fen, "game_over": board.game_over, 
                          "result": board.result if board.game_over else None}))
    else:
        print(json.dumps({"move": None, "fen": board.fen, "game_over": True, "result": "no_move"}))
'''


def create_venv(path: Path) -> Path:
    """Create virtualenv and return python path."""
    venv.create(path, with_pip=True, clear=True)
    python = path / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip", "-q"], check=True, capture_output=True)
    return python


def install_version(python: Path, source: Path, is_wheel: bool):
    """Install py-draughts in venv."""
    subprocess.run([str(python), "-m", "pip", "install", str(source), "-q"], check=True, capture_output=True)


def run_benchmark(python: Path) -> dict:
    """Run benchmark script in isolated environment."""
    script = BENCHMARK_SCRIPT.replace("__POSITIONS__", repr(TEST_POSITIONS))
    script = script.replace("__WARMUP__", str(WARMUP_ROUNDS))
    script = script.replace("__ROUNDS__", str(BENCHMARK_ROUNDS))
    script = script.replace("__DEPTH__", str(ENGINE_DEPTH))
    
    result = subprocess.run([str(python), "-c", script], capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr}
    return json.loads(result.stdout)


def get_move(python: Path, fen: str | None, depth: int) -> dict:
    """Get engine move from isolated environment."""
    script = GAME_SCRIPT.replace("__FEN__", fen or "")
    script = script.replace("__DEPTH__", str(depth))
    result = subprocess.run([str(python), "-c", script], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return {"error": result.stderr}
    return json.loads(result.stdout)


def play_match(python1: Path, python2: Path, num_games: int, depth: int) -> dict:
    """Play engine vs engine match."""
    results = {"v1_wins": 0, "v2_wins": 0, "draws": 0, "games": []}
    
    with console.status("[bold green]Playing engine match...") as status:
        for game_num in range(num_games):
            # Alternate colors
            white_py, black_py = (python1, python2) if game_num % 2 == 0 else (python2, python1)
            white_ver = "v1" if game_num % 2 == 0 else "v2"
            
            status.update(f"[bold green]Game {game_num + 1}/{num_games}...")
            
            fen = None  # Start position
            moves = 0
            max_moves = 200
            
            while moves < max_moves:
                current_py = white_py if moves % 2 == 0 else black_py
                result = get_move(current_py, fen, depth)
                
                if result.get("error") or result.get("game_over") or not result.get("move"):
                    break
                
                fen = result["fen"]
                moves += 1
                
                if result.get("game_over"):
                    break
            
            # Determine winner
            game_result = result.get("result", "1/2-1/2")
            if game_result == "1-0":
                winner = white_ver
            elif game_result == "0-1":
                winner = "v2" if white_ver == "v1" else "v1"
            else:
                winner = "draw"
            
            if winner == "v1":
                results["v1_wins"] += 1
            elif winner == "v2":
                results["v2_wins"] += 1
            else:
                results["draws"] += 1
            
            results["games"].append({"white": white_ver, "result": game_result, "moves": moves})
    
    return results


def find_latest_snapshot(project_root: Path) -> Path | None:
    """Find the most recent snapshot."""
    snapshots_dir = project_root / "snapshots"
    if not snapshots_dir.exists():
        return None
    snapshots = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
    return snapshots[-1] if snapshots else None


def main():
    project_root = Path(__file__).parent.parent
    
    # Determine snapshot to compare
    if len(sys.argv) > 1:
        snapshot_path = Path(sys.argv[1])
        if not snapshot_path.is_absolute():
            snapshot_path = project_root / snapshot_path
    else:
        snapshot_path = find_latest_snapshot(project_root)
    
    if not snapshot_path or not snapshot_path.exists():
        console.print("[red]No snapshot found. Create one first with: python tools/create_snapshot.py")
        sys.exit(1)
    
    # Find wheel in snapshot
    wheel = list(snapshot_path.glob("*.whl"))
    if not wheel:
        console.print(f"[red]No wheel found in {snapshot_path}")
        sys.exit(1)
    wheel = wheel[0]
    
    # Load metadata
    meta_path = snapshot_path / "metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    git_info = meta.get("git", {})
    snapshot_label = f"{snapshot_path.name}"
    if git_info:
        dirty = "*" if git_info.get("dirty") else ""
        snapshot_label += f" ({git_info.get('branch')}@{git_info.get('commit')}{dirty})"
    
    console.print(Panel.fit(
        f"[bold]Snapshot:[/] {snapshot_label}\n[bold]Current:[/] source code",
        title="Version Comparison",
        border_style="blue"
    ))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Setup environments
        console.print("\n[bold]Setting up environments...[/]")
        
        with console.status("[green]Creating snapshot venv..."):
            python1 = create_venv(tmpdir / "venv1")
            install_version(python1, wheel, is_wheel=True)
        console.print("  ✓ Snapshot environment ready")
        
        with console.status("[green]Creating current venv..."):
            python2 = create_venv(tmpdir / "venv2")
            install_version(python2, project_root, is_wheel=False)
        console.print("  ✓ Current environment ready")
        
        # Run benchmarks
        console.print("\n[bold]Running benchmarks...[/]")
        
        with console.status("[green]Benchmarking snapshot..."):
            bench1 = run_benchmark(python1)
        with console.status("[green]Benchmarking current..."):
            bench2 = run_benchmark(python2)
        
        if "error" in bench1 or "error" in bench2:
            console.print(f"[red]Benchmark error: {bench1.get('error', '')} {bench2.get('error', '')}")
            sys.exit(1)
        
        # Display benchmark results
        table = Table(title="Benchmark Results", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Snapshot", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Change", justify="right")
        
        # Legal moves
        lm1 = bench1["legal_moves"]["median_ms"]
        lm2 = bench2["legal_moves"]["median_ms"]
        lm_change = ((lm2 - lm1) / lm1) * 100 if lm1 > 0 else 0
        change_style = "green" if lm_change < -5 else "red" if lm_change > 5 else "white"
        table.add_row(
            "Legal moves (median ms)",
            f"{lm1:.2f}",
            f"{lm2:.2f}",
            f"[{change_style}]{lm_change:+.1f}%[/]"
        )
        
        # Engine time
        e1 = bench1["engine"]["median_ms"]
        e2 = bench2["engine"]["median_ms"]
        e_change = ((e2 - e1) / e1) * 100 if e1 > 0 else 0
        change_style = "green" if e_change < -5 else "red" if e_change > 5 else "white"
        table.add_row(
            f"Engine search depth={ENGINE_DEPTH} (median ms)",
            f"{e1:.2f}",
            f"{e2:.2f}",
            f"[{change_style}]{e_change:+.1f}%[/]"
        )
        
        # Nodes
        n1 = bench1["engine"]["median_nodes"]
        n2 = bench2["engine"]["median_nodes"]
        n_change = ((n2 - n1) / n1) * 100 if n1 > 0 else 0
        change_style = "green" if n_change < -5 else "red" if n_change > 5 else "white"
        table.add_row(
            "Nodes searched",
            f"{n1:,}",
            f"{n2:,}",
            f"[{change_style}]{n_change:+.1f}%[/]"
        )
        
        console.print()
        console.print(table)
        
        # Engine match
        console.print(f"\n[bold]Engine Match ({NUM_GAMES} games, depth={ENGINE_DEPTH})...[/]")
        match = play_match(python1, python2, NUM_GAMES, ENGINE_DEPTH)
        
        total = NUM_GAMES
        v1_pct = (match["v1_wins"] / total) * 100
        v2_pct = (match["v2_wins"] / total) * 100
        draw_pct = (match["draws"] / total) * 100
        
        match_table = Table(title="Match Results", box=box.ROUNDED)
        match_table.add_column("Version", style="cyan")
        match_table.add_column("Wins", justify="right")
        match_table.add_column("Percentage", justify="right")
        
        match_table.add_row("Snapshot", str(match["v1_wins"]), f"{v1_pct:.0f}%")
        match_table.add_row("Current", str(match["v2_wins"]), f"{v2_pct:.0f}%")
        match_table.add_row("Draws", str(match["draws"]), f"{draw_pct:.0f}%")
        
        console.print()
        console.print(match_table)
        
        # Summary
        console.print()
        if abs(lm_change) < 5 and abs(e_change) < 5 and abs(n_change) < 5:
            console.print("[green]✓ Performance is consistent with snapshot[/]")
        elif lm_change < -5 or e_change < -5:
            console.print("[green]✓ Performance improved![/]")
        else:
            console.print("[yellow]⚠ Performance regression detected[/]")
        
        # Note about draws
        if match["draws"] == NUM_GAMES:
            console.print("[dim]Note: 100% draws is expected when comparing identical code (deterministic engine)[/]")


if __name__ == "__main__":
    main()
