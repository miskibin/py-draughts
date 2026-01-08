#!/usr/bin/env python
"""
Benchmark comparison between py-draughts and pydraughts (PyPI).

Compares performance for:
- Legal moves generation
- Board initialization
- FEN parsing
- Making moves
"""

import sys
import time
from pathlib import Path
from statistics import mean, median, stdev

# Add project root to path for py-draughts import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import py-draughts (this project)
from draughts import StandardBoard as PyDraughtsBoard

# Import pydraughts (PyPI library)
try:
    from draughts import Board as PyDraughtsBoard_Check
    # If this works, we have a naming conflict - need to use different import
    # Actually both use 'draughts' package name, so we need subprocess isolation
    USE_SUBPROCESS = True
except ImportError:
    USE_SUBPROCESS = True

# We'll run pydraughts benchmarks in isolation to avoid import conflicts


# Test positions (FEN format compatible with both libraries)
TEST_POSITIONS = [
    # Standard starting position - use None for default
    None,
    # Midgame positions
    "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24",
    "B:W24,28,29,30,33,34,38,39,44,45,49,50:B1,2,6,7,8,12,13,17,18,22,23,27",
    # King positions
    "W:WK10,K20:BK30,K40",
    "W:WK10:B14,15,24,25",
    # Complex position
    "W:W28,33,34,38,39,43,44,48,49,50:B5,6,7,8,9,10,14,15,19,20",
]

WARMUP_ITERATIONS = 100
BENCHMARK_ITERATIONS = 1000


def benchmark_py_draughts():
    """Benchmark py-draughts (this project)."""
    results = {
        "board_init": [],
        "fen_parse": [],
        "legal_moves": [],
        "make_move": [],
    }
    
    # Warmup
    for _ in range(WARMUP_ITERATIONS):
        board = PyDraughtsBoard()
        list(board.legal_moves)
    
    # Board initialization benchmark
    for _ in range(BENCHMARK_ITERATIONS):
        start = time.perf_counter()
        board = PyDraughtsBoard()
        elapsed = time.perf_counter() - start
        results["board_init"].append(elapsed * 1_000_000)  # Convert to microseconds
    
    # FEN parsing benchmark
    for fen in TEST_POSITIONS[1:]:  # Skip None
        for _ in range(BENCHMARK_ITERATIONS // len(TEST_POSITIONS)):
            start = time.perf_counter()
            board = PyDraughtsBoard.from_fen(fen)
            elapsed = time.perf_counter() - start
            results["fen_parse"].append(elapsed * 1_000_000)
    
    # Legal moves benchmark
    for fen in TEST_POSITIONS:
        if fen:
            board = PyDraughtsBoard.from_fen(fen)
        else:
            board = PyDraughtsBoard()
        
        for _ in range(BENCHMARK_ITERATIONS // len(TEST_POSITIONS)):
            start = time.perf_counter()
            moves = list(board.legal_moves)
            elapsed = time.perf_counter() - start
            results["legal_moves"].append(elapsed * 1_000_000)
    
    # Make move benchmark
    for _ in range(BENCHMARK_ITERATIONS):
        board = PyDraughtsBoard()
        moves = list(board.legal_moves)
        if moves:
            start = time.perf_counter()
            board.push(moves[0])
            elapsed = time.perf_counter() - start
            results["make_move"].append(elapsed * 1_000_000)
    
    return {k: {"mean": mean(v), "median": median(v), "stdev": stdev(v) if len(v) > 1 else 0} 
            for k, v in results.items()}


def create_pydraughts_benchmark_script():
    """Create a temporary script to benchmark pydraughts in isolation."""
    return '''
import sys
import time
import json
from statistics import mean, median, stdev

# Remove any local paths that might shadow the installed package
sys.path = [p for p in sys.path if 'py-draughts' not in p and 'py_draughts' not in p]

try:
    from draughts import Board, Move
    import draughts as pydraughts_module
except ImportError as e:
    print(json.dumps({"error": f"pydraughts not installed: {e}"}))
    sys.exit(1)

TEST_POSITIONS = [
    None,
    "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24",
    "B:W24,28,29,30,33,34,38,39,44,45,49,50:B1,2,6,7,8,12,13,17,18,22,23,27",
    "W:WK10,K20:BK30,K40",
    "W:WK10:B14,15,24,25",
    "W:W28,33,34,38,39,43,44,48,49,50:B5,6,7,8,9,10,14,15,19,20",
]

WARMUP_ITERATIONS = 100
BENCHMARK_ITERATIONS = 1000

results = {
    "board_init": [],
    "fen_parse": [],
    "legal_moves": [],
    "make_move": [],
}

# Warmup
for _ in range(WARMUP_ITERATIONS):
    board = Board(variant="standard", fen="startpos")
    board.legal_moves()

# Board initialization benchmark
for _ in range(BENCHMARK_ITERATIONS):
    start = time.perf_counter()
    board = Board(variant="standard", fen="startpos")
    elapsed = time.perf_counter() - start
    results["board_init"].append(elapsed * 1_000_000)

# FEN parsing benchmark
for fen in TEST_POSITIONS[1:]:
    for _ in range(BENCHMARK_ITERATIONS // len(TEST_POSITIONS)):
        start = time.perf_counter()
        board = Board(variant="standard", fen=fen)
        elapsed = time.perf_counter() - start
        results["fen_parse"].append(elapsed * 1_000_000)

# Legal moves benchmark
for fen in TEST_POSITIONS:
    if fen:
        board = Board(variant="standard", fen=fen)
    else:
        board = Board(variant="standard", fen="startpos")
    
    for _ in range(BENCHMARK_ITERATIONS // len(TEST_POSITIONS)):
        start = time.perf_counter()
        moves = board.legal_moves()
        elapsed = time.perf_counter() - start
        results["legal_moves"].append(elapsed * 1_000_000)

# Make move benchmark
for _ in range(BENCHMARK_ITERATIONS):
    board = Board(variant="standard", fen="startpos")
    moves = board.legal_moves()
    if moves:
        start = time.perf_counter()
        board.push(moves[0])
        elapsed = time.perf_counter() - start
        results["make_move"].append(elapsed * 1_000_000)

output = {k: {"mean": mean(v), "median": median(v), "stdev": stdev(v) if len(v) > 1 else 0} 
          for k, v in results.items()}
output["version"] = pydraughts_module.__version__ if hasattr(pydraughts_module, "__version__") else "unknown"
print(json.dumps(output))
'''


def benchmark_pydraughts():
    """Benchmark pydraughts (PyPI) in isolated subprocess."""
    import subprocess
    import tempfile
    import json
    
    script = create_pydraughts_benchmark_script()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        script_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            return {"error": result.stderr or "Unknown error"}
        
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "Benchmark timed out"}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse output: {e}"}
    finally:
        Path(script_path).unlink(missing_ok=True)


def format_time(us: float) -> str:
    """Format time in appropriate units."""
    if us < 1:
        return f"{us * 1000:.2f} ns"
    elif us < 1000:
        return f"{us:.2f} µs"
    else:
        return f"{us / 1000:.2f} ms"


def calculate_speedup(py_draughts_us: float, pydraughts_us: float) -> str:
    """Calculate speedup factor."""
    if py_draughts_us <= 0 or pydraughts_us <= 0:
        return "N/A"
    
    speedup = pydraughts_us / py_draughts_us
    if speedup >= 1:
        return f"{speedup:.1f}x faster"
    else:
        return f"{1/speedup:.1f}x slower"


def generate_comparison_chart(py_draughts_results, pydraughts_results, output_path):
    """Generate a comparison bar chart."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("Installing matplotlib for chart generation...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib", "numpy", "-q"])
        import matplotlib.pyplot as plt
        import numpy as np
    
    operations = ["Board init", "FEN parse", "Legal moves", "Make move"]
    op_keys = ["board_init", "fen_parse", "legal_moves", "make_move"]
    
    py_times = [py_draughts_results[k]["median"] for k in op_keys]
    pypi_times = [pydraughts_results[k]["median"] for k in op_keys]
    
    # Calculate speedup factors
    speedups = [pypi / py if py > 0 else 0 for py, pypi in zip(py_times, pypi_times)]
    
    # Create figure with dark theme
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Set background color
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')
    
    x = np.arange(len(operations))
    width = 0.35
    
    # Colors - vibrant contrast
    py_color = '#58a6ff'  # GitHub blue
    pypi_color = '#f85149'  # GitHub red
    
    # Create bars with log scale for better visualization
    bars1 = ax.bar(x - width/2, py_times, width, label='py-draughts', color=py_color, 
                   edgecolor='white', linewidth=0.5, alpha=0.9)
    bars2 = ax.bar(x + width/2, pypi_times, width, label='pydraughts (PyPI)', color=pypi_color,
                   edgecolor='white', linewidth=0.5, alpha=0.9)
    
    # Use log scale for y-axis
    ax.set_yscale('log')
    
    # Labels and title
    ax.set_xlabel('Operation', fontsize=14, color='white', fontweight='bold')
    ax.set_ylabel('Time (µs) - log scale', fontsize=14, color='white', fontweight='bold')
    ax.set_title('py-draughts vs pydraughts Performance Comparison', 
                 fontsize=18, color='white', fontweight='bold', pad=20)
    
    ax.set_xticks(x)
    ax.set_xticklabels(operations, fontsize=12, color='white')
    ax.tick_params(axis='y', colors='white', labelsize=11)
    
    # Add speedup annotations above bars
    for i, (bar1, bar2, speedup) in enumerate(zip(bars1, bars2, speedups)):
        height = max(bar1.get_height(), bar2.get_height())
        ax.annotate(f'{speedup:.0f}x faster',
                    xy=(i, height),
                    xytext=(0, 15),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=13, fontweight='bold',
                    color='#7ee787',  # GitHub green
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#238636', 
                             edgecolor='none', alpha=0.8))
    
    # Add value labels on bars
    def add_labels(bars, color):
        for bar in bars:
            height = bar.get_height()
            if height < 1:
                label = f'{height*1000:.0f}ns'
            elif height < 1000:
                label = f'{height:.1f}µs'
            else:
                label = f'{height/1000:.2f}ms'
            ax.annotate(label,
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        fontsize=9, color=color, fontweight='medium')
    
    add_labels(bars1, py_color)
    add_labels(bars2, pypi_color)
    
    # Legend
    legend = ax.legend(loc='upper left', fontsize=12, framealpha=0.9,
                      facecolor='#161b22', edgecolor='#30363d')
    for text in legend.get_texts():
        text.set_color('white')
    
    # Grid
    ax.yaxis.grid(True, alpha=0.2, color='white', linestyle='--')
    ax.set_axisbelow(True)
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#30363d')
    ax.spines['bottom'].set_color('#30363d')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='#0d1117', edgecolor='none',
                bbox_inches='tight', pad_inches=0.2)
    plt.close()
    
    print(f"  Chart saved to: {output_path}")


def main():
    print("=" * 70)
    print("py-draughts vs pydraughts Benchmark Comparison")
    print("=" * 70)
    print(f"\nWarmup iterations: {WARMUP_ITERATIONS}")
    print(f"Benchmark iterations: {BENCHMARK_ITERATIONS}")
    print(f"Test positions: {len(TEST_POSITIONS)}")
    print()
    
    # Benchmark py-draughts
    print("Benchmarking py-draughts (this project)...")
    py_draughts_results = benchmark_py_draughts()
    print("  Done!")
    
    # Benchmark pydraughts
    print("\nBenchmarking pydraughts (PyPI)...")
    pydraughts_results = benchmark_pydraughts()
    
    if "error" in pydraughts_results:
        print(f"  Error: {pydraughts_results['error']}")
        print("\nInstall pydraughts with: pip install pydraughts")
        return
    
    print(f"  Done! (version: {pydraughts_results.get('version', 'unknown')})")
    
    # Generate chart
    print("\nGenerating comparison chart...")
    chart_path = Path(__file__).parent.parent / "docs" / "source" / "_static" / "speed_comparison.png"
    generate_comparison_chart(py_draughts_results, pydraughts_results, chart_path)
    
    # Display results
    print("\n" + "=" * 70)
    print("Results (median time)")
    print("=" * 70)
    print()
    print(f"{'Operation':<20} {'py-draughts':>15} {'pydraughts':>15} {'Speedup':>20}")
    print("-" * 70)
    
    operations = [
        ("Board init", "board_init"),
        ("FEN parse", "fen_parse"),
        ("Legal moves", "legal_moves"),
        ("Make move", "make_move"),
    ]
    
    markdown_rows = []
    
    for op_name, op_key in operations:
        py_time = py_draughts_results[op_key]["median"]
        pypi_time = pydraughts_results[op_key]["median"]
        speedup = calculate_speedup(py_time, pypi_time)
        
        print(f"{op_name:<20} {format_time(py_time):>15} {format_time(pypi_time):>15} {speedup:>20}")
        
        # Store for markdown output
        markdown_rows.append({
            "operation": op_name,
            "py_draughts": format_time(py_time),
            "pydraughts": format_time(pypi_time),
            "speedup": speedup,
        })
    
    print()
    print("=" * 70)
    print("Markdown table for README:")
    print("=" * 70)
    print()
    print("| Operation | py-draughts | pydraughts | Speedup |")
    print("|-----------|-------------|------------|---------|")
    for row in markdown_rows:
        print(f"| {row['operation']} | {row['py_draughts']} | {row['pydraughts']} | {row['speedup']} |")
    
    print()
    print("=" * 70)
    
    return py_draughts_results, pydraughts_results


if __name__ == "__main__":
    main()

