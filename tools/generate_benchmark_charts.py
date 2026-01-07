#!/usr/bin/env python
"""
Generate benchmark charts and tables for documentation.
Creates charts for:
1. Legal moves generation performance
2. Engine depth timing benchmark
"""

import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("Installing matplotlib and numpy for chart generation...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib", "numpy"])
    import matplotlib.pyplot as plt
    import numpy as np

from draughts.boards.standard import Board
from draughts.engines import AlphaBetaEngine


def benchmark_legal_moves():
    """Benchmark legal moves generation."""
    positions = [
        ('[FEN "W:W28,33,34,38,39,43,44,48,49,50:B5,6,7,8,9,10,14,15,19,20"]', "Opening"),
        ('[FEN "W:WK10:B14,15,24,25"]', "King Captures"),
        ('[FEN "W:W31,32,33,34,35:B16,17,18,19,20"]', "Midgame"),
        ('[FEN "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24"]', "Complex"),
        (None, "Start Position"),
    ]
    
    results = []
    iterations = 1000
    
    for fen, name in positions:
        if fen:
            board = Board.from_fen(fen)
        else:
            board = Board()
        
        # Warmup
        for _ in range(100):
            list(board.legal_moves)
        
        # Benchmark
        start = time.perf_counter()
        for _ in range(iterations):
            list(board.legal_moves)
        elapsed = time.perf_counter() - start
        
        avg_time_us = (elapsed / iterations) * 1_000_000
        moves_count = len(list(board.legal_moves))
        
        results.append({
            "name": name,
            "avg_time_us": avg_time_us,
            "moves_count": moves_count,
        })
        print(f"  {name}: {avg_time_us:.2f} µs ({moves_count} moves)")
    
    return results


def benchmark_engine_depth(max_depth=10):
    """Benchmark engine at different depths."""
    test_positions = [
        None,  # Starting position
        '[FEN "W:W27,28,32,33,37,38,42,43,47,48:B3,4,8,9,13,14,18,19,23,24"]',
        '[FEN "B:W24,28,29,30,33,34,38,39,44,45,49,50:B1,2,6,7,8,12,13,17,18,22,23,27"]',
        '[FEN "W:WK10,K20:BK30,K40"]',
    ]
    
    moves_per_position = 2
    results = []
    
    for depth in range(1, max_depth + 1):
        engine = AlphaBetaEngine(depth_limit=depth)
        
        total_time = 0.0
        total_moves = 0
        total_nodes = 0
        
        for fen in test_positions:
            if fen:
                board = Board.from_fen(fen)
            else:
                board = Board()
            
            for _ in range(moves_per_position):
                if not list(board.legal_moves):
                    break
                
                engine.nodes = 0
                start = time.perf_counter()
                move = engine.get_best_move(board)
                elapsed = time.perf_counter() - start
                
                total_time += elapsed
                total_moves += 1
                total_nodes += engine.nodes
                
                board.push(move)
        
        avg_time_ms = (total_time / total_moves * 1000) if total_moves > 0 else 0
        avg_nodes = total_nodes // total_moves if total_moves > 0 else 0
        
        results.append({
            "depth": depth,
            "avg_time_ms": avg_time_ms,
            "avg_nodes": avg_nodes,
            "total_time": total_time,
        })
        
        print(f"  Depth {depth}: {avg_time_ms:.2f} ms, {avg_nodes:,} nodes")
        
        # Stop if taking too long
        if avg_time_ms > 15000:  # 15 seconds
            print(f"  Stopping at depth {depth} (> 15s per move)")
            break
    
    return results


def generate_charts(legal_moves_results, engine_results, output_dir):
    """Generate PNG charts for documentation."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Chart 1: Legal Moves Performance
    plt.figure(figsize=(10, 6))
    names = [r["name"] for r in legal_moves_results]
    times = [r["avg_time_us"] for r in legal_moves_results]
    moves = [r["moves_count"] for r in legal_moves_results]
    
    colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(names)))
    bars = plt.bar(names, times, color=colors, edgecolor='navy', linewidth=1.2)
    
    # Add move count labels on bars
    for bar, move_count in zip(bars, moves):
        height = bar.get_height()
        plt.annotate(f'{move_count} moves',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    plt.xlabel('Position Type', fontsize=12)
    plt.ylabel('Time (microseconds)', fontsize=12)
    plt.title('Legal Moves Generation Performance', fontsize=14, fontweight='bold')
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    plt.savefig(output_dir / 'legal_moves_benchmark.png', dpi=150)
    plt.close()
    print(f"  Saved: {output_dir / 'legal_moves_benchmark.png'}")
    
    # Chart 2: Engine Depth Performance (Time)
    plt.figure(figsize=(10, 6))
    depths = [r["depth"] for r in engine_results]
    times = [r["avg_time_ms"] for r in engine_results]
    
    plt.plot(depths, times, 'b-o', linewidth=2, markersize=8, 
             markerfacecolor='lightblue', markeredgecolor='navy')
    plt.fill_between(depths, times, alpha=0.3)
    
    plt.xlabel('Search Depth', fontsize=12)
    plt.ylabel('Average Time per Move (ms)', fontsize=12)
    plt.title('AlphaBeta Engine - Search Time by Depth', fontsize=14, fontweight='bold')
    plt.xticks(depths)
    plt.yscale('log')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'engine_depth_time.png', dpi=150)
    plt.close()
    print(f"  Saved: {output_dir / 'engine_depth_time.png'}")
    
    # Chart 3: Engine Depth Performance (Nodes)
    plt.figure(figsize=(10, 6))
    nodes = [r["avg_nodes"] for r in engine_results]
    
    plt.plot(depths, nodes, 'g-s', linewidth=2, markersize=8,
             markerfacecolor='lightgreen', markeredgecolor='darkgreen')
    plt.fill_between(depths, nodes, alpha=0.3, color='green')
    
    plt.xlabel('Search Depth', fontsize=12)
    plt.ylabel('Average Nodes Searched', fontsize=12)
    plt.title('AlphaBeta Engine - Nodes Searched by Depth', fontsize=14, fontweight='bold')
    plt.xticks(depths)
    plt.yscale('log')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'engine_depth_nodes.png', dpi=150)
    plt.close()
    print(f"  Saved: {output_dir / 'engine_depth_nodes.png'}")
    
    # Chart 4: Combined engine benchmark
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    color1 = 'tab:blue'
    ax1.set_xlabel('Search Depth', fontsize=12)
    ax1.set_ylabel('Time (ms)', color=color1, fontsize=12)
    ax1.plot(depths, times, 'o-', color=color1, linewidth=2, markersize=8, label='Time (ms)')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_yscale('log')
    
    ax2 = ax1.twinx()
    color2 = 'tab:green'
    ax2.set_ylabel('Nodes', color=color2, fontsize=12)
    ax2.plot(depths, nodes, 's-', color=color2, linewidth=2, markersize=8, label='Nodes')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_yscale('log')
    
    plt.title('AlphaBeta Engine Performance by Depth', fontsize=14, fontweight='bold')
    fig.tight_layout()
    plt.savefig(output_dir / 'engine_benchmark.png', dpi=150)
    plt.close()
    print(f"  Saved: {output_dir / 'engine_benchmark.png'}")


def generate_rst_tables(legal_moves_results, engine_results):
    """Generate RST table content."""
    
    # Legal moves table
    legal_moves_table = """
.. list-table:: Legal Moves Generation Performance
   :header-rows: 1
   :widths: 30 20 20

   * - Position Type
     - Time (µs)
     - Move Count
"""
    for r in legal_moves_results:
        legal_moves_table += f"   * - {r['name']}\n     - {r['avg_time_us']:.2f}\n     - {r['moves_count']}\n"
    
    # Engine depth table
    engine_table = """
.. list-table:: Engine Depth Performance
   :header-rows: 1
   :widths: 15 25 30

   * - Depth
     - Avg Time
     - Avg Nodes
"""
    for r in engine_results:
        time_str = f"{r['avg_time_ms']:.2f} ms" if r['avg_time_ms'] < 1000 else f"{r['avg_time_ms']/1000:.2f} s"
        engine_table += f"   * - {r['depth']}\n     - {time_str}\n     - {r['avg_nodes']:,}\n"
    
    return legal_moves_table, engine_table


def main():
    print("=" * 70)
    print("Generating Benchmark Charts for Documentation")
    print("=" * 70)
    
    print("\n1. Benchmarking Legal Moves Generation...")
    legal_moves_results = benchmark_legal_moves()
    
    print("\n2. Benchmarking Engine Depth Performance...")
    engine_results = benchmark_engine_depth(max_depth=10)
    
    print("\n3. Generating Charts...")
    output_dir = Path(__file__).parent.parent / "docs" / "source" / "_static"
    generate_charts(legal_moves_results, engine_results, output_dir)
    
    print("\n4. Generating RST Tables...")
    legal_table, engine_table = generate_rst_tables(legal_moves_results, engine_results)
    
    print("\n" + "=" * 70)
    print("Legal Moves Table (for RST):")
    print("=" * 70)
    print(legal_table)
    
    print("\n" + "=" * 70)
    print("Engine Depth Table (for RST):")
    print("=" * 70)
    print(engine_table)
    
    print("\n✓ Charts saved to:", output_dir)
    print("✓ Copy the tables above into your documentation as needed")
    
    return legal_moves_results, engine_results


if __name__ == "__main__":
    main()
