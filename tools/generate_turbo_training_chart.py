#!/usr/bin/env python
"""
Generate the TurboEngine pattern-training figure for the docs.

Produces docs/source/_static/turbo_training_pipeline.png: a five-stage flow of
how turbo_weights.bin is trained (see tools/train_pattern_eval.py), plus an
inset showing the eleven overlapping 4x2 men patterns on the 10x10 board.

Everything drawn here is derived from the code, not from a benchmark run, so
the figure never asserts numbers the repo cannot reproduce.  The pattern count
and their exact squares come straight from draughts.engines.turbo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

from draughts.engines.turbo import PATTERNS, N_PATTERNS, PAT_ENTRIES, PAT_TRITS

INK = "#1f2933"
MUTED = "#52606d"
ACCENT = "#2563eb"
FILL = "#eef2ff"
EDGE = "#c7d2fe"
BAND = "#f8fafc"

STAGES = [
    ("1. Self-play", "Scan 3.1 plays short\nrollouts from randomised\nopenings for diversity"),
    ("2. Label", "sample every quiet position\n(no captures pending), tag it\nwith Scan's search score\n(White's perspective)"),
    ("3. Features", f"{N_PATTERNS} overlapping {PAT_TRITS//2}x2 men\nblocks -> base-3 trits\n(empty/white/black);\n+180 deg mirror augmentation"),
    ("4. Fit", "v2 hand eval fixed as base;\ntrain pattern residual toward\nScan score (Adam + L2)"),
    ("5. Export", f"int16 weights ->\nturbo_weights.bin\n({N_PATTERNS} x {PAT_ENTRIES} cells),\nloaded pure-Python"),
]


def _board_squares(pat):
    """Yield (row, col) grid cells (0..9) for the dark squares of a pattern.

    Square s (0..49) sits on row s//5; dark-square column is derived the same
    way turbo._file_of does, so the drawing matches the engine's geometry.
    """
    for s in pat:
        row, col = divmod(s, 5)
        f = 2 * col + 1 if row % 2 == 0 else 2 * col
        yield row, f


def draw():
    fig = plt.figure(figsize=(11.0, 4.6), dpi=140)
    fig.suptitle(
        "TurboEngine v3 - training the pattern evaluation",
        fontsize=15, fontweight="bold", color=INK, y=0.97,
    )

    # ---- top band: five-stage pipeline ---------------------------------
    ax = fig.add_axes([0.02, 0.42, 0.96, 0.44])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 10)
    ax.axis("off")

    n = len(STAGES)
    gap = 2.2
    total_gap = gap * (n - 1)
    bw = (100 - total_gap) / n
    for i, (title, body) in enumerate(STAGES):
        x = i * (bw + gap)
        box = FancyBboxPatch(
            (x, 0.6), bw, 8.8, boxstyle="round,pad=0.15,rounding_size=0.6",
            linewidth=1.4, edgecolor=EDGE, facecolor=FILL, mutation_aspect=0.5,
        )
        ax.add_patch(box)
        ax.text(x + bw / 2, 8.0, title, ha="center", va="center",
                fontsize=11, fontweight="bold", color=ACCENT)
        ax.text(x + bw / 2, 4.1, body, ha="center", va="center",
                fontsize=8.3, color=MUTED, linespacing=1.35)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch(
                (x + bw + 0.15, 5.0), (x + bw + gap - 0.15, 5.0),
                arrowstyle="-|>", mutation_scale=15, linewidth=1.6,
                color=ACCENT,
            ))

    # ---- bottom-left: the pattern layout on the board ------------------
    axb = fig.add_axes([0.06, 0.03, 0.30, 0.34])
    axb.set_xlim(-0.5, 10.5)
    axb.set_ylim(-0.5, 10.5)
    axb.set_aspect("equal")
    axb.axis("off")
    axb.set_title("11 overlapping men patterns", fontsize=9.5,
                  color=INK, pad=4)

    # playable dark squares, faint
    for row in range(10):
        for col in range(10):
            if (row + col) % 2 == 1:
                axb.add_patch(Rectangle(
                    (col, 9 - row), 1, 1, facecolor="#eceff4",
                    edgecolor="white", linewidth=0.5,
                ))
    # highlight three representative patterns in distinct hues
    hues = ["#2563eb", "#db2777", "#059669"]
    for pi, color in zip((0, 4, N_PATTERNS - 1), hues):
        for row, f in _board_squares(PATTERNS[pi]):
            axb.add_patch(Rectangle(
                (f, 9 - row), 1, 1, facecolor=color, alpha=0.32,
                edgecolor=color, linewidth=1.2,
            ))
    axb.text(5, -0.9, "each block = 8 squares, one base-3 weight table",
             ha="center", va="top", fontsize=7.6, color=MUTED)

    # ---- bottom-right: what is learned --------------------------------
    axn = fig.add_axes([0.40, 0.03, 0.56, 0.34])
    axn.axis("off")
    axn.add_patch(FancyBboxPatch(
        (0.0, 0.0), 1.0, 1.0, boxstyle="round,pad=0.02,rounding_size=0.03",
        linewidth=1.2, edgecolor=EDGE, facecolor=BAND,
        transform=axn.transAxes,
    ))
    lines = [
        (r"$E_{white} = \mathrm{v2\ hand\ eval}\;+\;\sum_p w_p[\,\mathrm{index}_p\,]$",
         13, INK),
        ("the hand eval is a fixed offset; only the pattern weights are trained,",
         9.2, MUTED),
        ("as a residual correction over the men layout.", 9.2, MUTED),
        ("Objective: teach (base + patterns) toward Scan's judgment; L2 keeps",
         9.2, MUTED),
        ("the many rare pattern cells small. Result: stronger, still pure-Python.",
         9.2, MUTED),
    ]
    y = 0.86
    for txt, fs, col in lines:
        axn.text(0.05, y, txt, ha="left", va="center", fontsize=fs,
                 color=col, transform=axn.transAxes)
        y -= 0.19

    out = Path(__file__).parent.parent / "docs" / "source" / "_static" / "turbo_training_pipeline.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    draw()
