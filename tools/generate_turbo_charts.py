#!/usr/bin/env python
"""
Generate the TurboEngine documentation figures (PNGs in docs/source/_static).

Figures
-------
* ``turbo_elo_ladder.png``       measured internal Elo vs search depth (+ per-ply gain)
* ``turbo_strength.png``         trained-vs-untrained ablation & flagship gap (Elo, 2*SE)
* ``turbo_weights.png``          learned pattern-weight distribution + per-pattern activity
* ``turbo_eval_learned.png``     mean learned correction by local men balance (what it learned)
* ``turbo_pattern_coverage.png`` the 11 overlapping men patterns on the board
* ``turbo_training_pipeline.png`` schematic of the offline training pipeline

Elo figures read ``docs/source/_static/turbo_elo.json`` (produced by
``tools/measure_turbo_elo.py``); weight figures read the shipped
``draughts/engines/turbo_weights.bin`` directly.  Colours use a colourblind-safe
palette (validated blue/green/orange + a blue->orange diverging ramp).

Usage::

    python tools/generate_turbo_charts.py     # regenerate every figure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent))

from draughts.engines import turbo  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "docs" / "source" / "_static"
ELO_JSON = STATIC / "turbo_elo.json"

# --- validated colourblind-safe palette (light surface) --------------------
BLUE = "#2a78d6"
GREEN = "#008300"
ORANGE = "#eb6834"
MAGENTA = "#e87ba4"
INK = "#0b0b0b"
MUTED = "#52514e"
GRIDC = "#dcdcd8"
SURFACE = "#fcfcfb"
# sequential blue ramp (light -> dark)
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "font.size": 11,
        "axes.grid": True,
        "grid.color": GRIDC,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _save(fig, name):
    STATIC.mkdir(parents=True, exist_ok=True)
    path = STATIC / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {path.relative_to(ROOT)}")


def _load_elo():
    if not ELO_JSON.exists():
        print(
            f"  (skip Elo figures: {ELO_JSON.relative_to(ROOT)} not found -- "
            f"run tools/measure_turbo_elo.py first)"
        )
        return None
    return json.loads(ELO_JSON.read_text())


# ---------------------------------------------------------------------------
# 1. Elo ladder (cumulative internal Elo vs depth + per-ply gain)
# ---------------------------------------------------------------------------


def fig_ladder(elo):
    ladder = elo.get("ladder")
    curve = elo.get("ladder_cumulative")
    if not ladder or not curve:
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    depths = [c["depth"] for c in curve]
    vals = [c["elo"] for c in curve]
    ses = [2 * c["se"] for c in curve]
    ax1.errorbar(
        depths,
        vals,
        yerr=ses,
        fmt="-o",
        color=BLUE,
        ecolor=MUTED,
        elinewidth=1.2,
        capsize=4,
        markersize=8,
        markerfacecolor=BLUE,
        markeredgecolor="white",
        linewidth=2.2,
        zorder=3,
    )
    ax1.fill_between(depths, vals, alpha=0.10, color=BLUE)
    for d, v in zip(depths, vals):
        ax1.annotate(
            f"{v:+.0f}",
            (d, v),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=10,
            color=INK,
            fontweight="bold",
        )
    anchor = elo.get("ladder_anchor_depth", depths[0])
    ax1.set_xlabel("search depth (plies)")
    ax1.set_ylabel(f"internal Elo (anchored at depth {anchor} = 0)")
    ax1.set_title("Strength vs search depth", fontweight="bold", loc="left")
    ax1.set_xticks(depths)

    labels = [f"d{r['low']}→d{r['high']}" for r in ladder]
    gains = [r["elo"] for r in ladder]
    gse = [r["elo_2se"] for r in ladder]
    bars = ax2.bar(
        labels, gains, color=BLUES[3], edgecolor="white", linewidth=1.5, width=0.62, zorder=3
    )
    ax2.errorbar(
        range(len(labels)),
        gains,
        yerr=gse,
        fmt="none",
        ecolor=MUTED,
        elinewidth=1.2,
        capsize=4,
        zorder=4,
    )
    for b, g in zip(bars, gains):
        ax2.annotate(
            f"{g:+.0f}",
            (b.get_x() + b.get_width() / 2, g),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=10,
            color=INK,
            fontweight="bold",
        )
    ax2.set_ylabel("Elo gained per extra ply")
    ax2.set_title("Marginal value of one more ply", fontweight="bold", loc="left")
    ax2.axhline(0, color=MUTED, linewidth=0.8)

    g = ladder[0]
    fig.suptitle(
        f"TurboEngine measured strength  ({g['games']} games/rung, "
        f"self-play, fixed depth; error bars ±2·SE)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    _save(fig, "turbo_elo_ladder.png")


# ---------------------------------------------------------------------------
# 2. Strength summary: ablation + flagship (horizontal Elo bars, 2*SE)
# ---------------------------------------------------------------------------


def fig_strength(elo):
    rows = []
    abl = elo.get("ablation")
    if abl:
        rows.append(
            (
                "Trained eval vs\nsame engine, patterns off",
                abl["elo"],
                abl["elo_2se"],
                GREEN,
                f"{abl['wins']}–{abl['losses']}–{abl['draws']}, d={abl['depth']}",
            )
        )
    for f in elo.get("flagship", []):
        if f.get("mode") == "fixed-depth":
            rows.append(
                (
                    f"TurboEngine vs SimpleEngine\n(equal depth {f['depth']})",
                    f["elo"],
                    f["elo_2se"],
                    BLUE,
                    f"{f['wins']}–{f['losses']}–{f['draws']}",
                )
            )
        else:
            rows.append(
                (
                    f"TurboEngine vs SimpleEngine\n(equal time {f['time_control']}s)",
                    f["elo"],
                    f["elo_2se"],
                    ORANGE,
                    f"{f['wins']}–{f['losses']}–{f['draws']}",
                )
            )
    if not rows:
        return
    rows.reverse()
    fig, ax = plt.subplots(figsize=(9.5, 0.9 + 1.05 * len(rows)))
    ys = np.arange(len(rows))
    labels, vals, errs, colors, wld = zip(*rows)
    ax.barh(
        ys,
        vals,
        xerr=errs,
        color=colors,
        edgecolor="white",
        linewidth=1.5,
        height=0.55,
        error_kw=dict(ecolor=MUTED, elinewidth=1.4, capsize=5),
        zorder=3,
    )
    ax.axvline(0, color=MUTED, linewidth=1.0)
    reach = max(abs(v) + e for v, e in zip(vals, errs))
    pad = 0.03 * reach
    for y, v, e, w in zip(ys, vals, errs, wld):
        # place the label just past the error-bar cap so it never overlaps it
        xt = (v + e + pad) if v >= 0 else (v - e - pad)
        ax.annotate(
            f"{v:+.0f} ± {e:.0f} Elo  ({w})",
            (xt, y),
            va="center",
            ha="left" if v >= 0 else "right",
            fontsize=9.5,
            color=INK,
            fontweight="bold",
        )
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Elo advantage of the first engine  (positive = stronger)")
    ax.set_title(
        "How much strength the trained eval and the search buy", fontweight="bold", loc="left"
    )
    ax.grid(axis="y", visible=False)
    has_neg = any(v < 0 for v in vals)
    ax.set_xlim(-(0.55 if has_neg else 0.06) * reach, reach * 1.85)
    _save(fig, "turbo_strength.png")


# ---------------------------------------------------------------------------
# 3. Learned pattern weights: distribution + per-pattern activity
# ---------------------------------------------------------------------------


def _weights_matrix():
    """(N_PATTERNS, PAT_ENTRIES) int array of the shipped trained weights."""
    return np.array(turbo.PAT_W, dtype=np.int32)


def fig_weights():
    W = _weights_matrix()
    nz = W[W != 0]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    ax1.hist(nz, bins=60, color=BLUE, edgecolor="white", linewidth=0.4)
    ax1.axvline(0, color=MUTED, linewidth=1.0)
    ax1.set_xlabel("learned weight (centipawn correction)")
    ax1.set_ylabel("number of pattern cells")
    ax1.set_title("Distribution of learned weights", fontweight="bold", loc="left")
    frac = 100 * nz.size / W.size
    ax1.annotate(
        f"{W.shape[0]} patterns × {W.shape[1]} cells = {W.size:,}\n"
        f"{nz.size:,} non-zero ({frac:.0f}%)\n"
        f"range [{nz.min()}, {nz.max()}] cp",
        (0.97, 0.95),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=9.5,
        color=MUTED,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GRIDC),
    )

    activity = np.abs(W).mean(axis=1)
    order = np.arange(W.shape[0])
    ax2.bar(order, activity, color=BLUES[3], edgecolor="white", linewidth=1.2, zorder=3)
    ax2.set_xlabel("pattern index (11 overlapping 4×2 men blocks)")
    ax2.set_ylabel("mean |weight| over cells (cp)")
    ax2.set_title("How active each pattern is", fontweight="bold", loc="left")
    ax2.set_xticks(order)

    fig.suptitle(
        "TurboEngine trained pattern evaluation (turbo_weights.bin)", fontsize=12, x=0.01, ha="left"
    )
    _save(fig, "turbo_weights.png")


# ---------------------------------------------------------------------------
# 4. What the eval learned: mean correction by local men balance
# ---------------------------------------------------------------------------


def fig_eval_learned():
    W = _weights_matrix()
    T = turbo.PAT_TRITS
    # base-3 digit counts per cell index, 0..3^T-1
    idx = np.arange(3**T)
    digits = np.zeros((3**T, T), dtype=np.int8)
    x = idx.copy()
    for i in range(T):
        digits[:, i] = x % 3
        x //= 3
    n_white = (digits == 1).sum(axis=1)
    n_black = (digits == 2).sum(axis=1)

    grid = np.full((T + 1, T + 1), np.nan)
    counts = np.zeros((T + 1, T + 1))
    total = W.mean(axis=0)  # mean weight per cell across patterns
    for nw in range(T + 1):
        for nb in range(T + 1 - nw):
            mask = (n_white == nw) & (n_black == nb)
            if mask.any():
                grid[nb, nw] = total[mask].mean()
                counts[nb, nw] = mask.sum()

    lim = np.nanmax(np.abs(grid))
    fig, ax = plt.subplots(figsize=(7.4, 6.0))
    # diverging blue(-) -> gray -> orange(+)
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("bo", [BLUE, "#8fb4e6", "#f0efec", "#f2a583", ORANGE])
    im = ax.imshow(grid, origin="lower", cmap=cmap, vmin=-lim, vmax=lim)
    ax.set_xlabel("white men in the 8-square block")
    ax.set_ylabel("black men in the 8-square block")
    ax.set_title(
        "What the pattern eval learned\n(mean correction, white perspective)",
        fontweight="bold",
        loc="left",
    )
    ax.set_xticks(range(T + 1))
    ax.set_yticks(range(T + 1))
    ax.grid(False)
    for nw in range(T + 1):
        for nb in range(T + 1 - nw):
            if not np.isnan(grid[nb, nw]) and counts[nb, nw] > 0:
                v = grid[nb, nw]
                ax.text(
                    nw,
                    nb,
                    f"{v:+.0f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=INK if abs(v) < 0.6 * lim else "white",
                )
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label("mean learned correction (cp)")
    _save(fig, "turbo_eval_learned.png")


# ---------------------------------------------------------------------------
# 5. Pattern coverage on the board
# ---------------------------------------------------------------------------


def fig_pattern_coverage():
    pats = turbo.PATTERNS
    n = len(pats)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(2.5 * cols, 2.5 * rows))
    axes = np.array(axes).reshape(-1)
    for p, ax in enumerate(axes):
        ax.set_xlim(-0.5, 9.5)
        ax.set_ylim(-0.5, 9.5)
        ax.set_aspect("equal")
        ax.axis("off")
        if p >= n:
            continue
        squares = set(pats[p])
        for sq in range(50):
            row = sq // 5
            f = turbo._file_of(sq)
            xx, yy = f, 9 - row
            hit = sq in squares
            ax.add_patch(
                plt.Rectangle(
                    (xx - 0.5, yy - 0.5),
                    1,
                    1,
                    facecolor=ORANGE if hit else "#ececea",
                    edgecolor="white",
                    linewidth=1.0,
                )
            )
        ax.set_title(f"pattern {p}", fontsize=9.5, color=INK)
    fig.suptitle(
        "The 11 overlapping 4×2 men patterns (dark squares of the 10×10 board)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    _save(fig, "turbo_pattern_coverage.png")


# ---------------------------------------------------------------------------
# 6. Training pipeline schematic
# ---------------------------------------------------------------------------


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 26)
    ax.axis("off")
    steps = [
        ("1. Self-play", "Scan 3.1 (or v2)\nshallow rollouts from\nrandomised openings", BLUES[1]),
        ("2. Sample", "keep fully-quiet\npositions; label with\nScan score / result", BLUES[2]),
        (
            "3. Features",
            "v2 hand eval (fixed)\n+ 11 base-3 pattern\nindices; 180° mirror",
            BLUES[3],
        ),
        ("4. Fit", "Texel logistic /\nleast-squares (Adam,\nL2) — patterns only", BLUES[4]),
        ("5. Ship", "int16 weights →\nturbo_weights.bin\n(stdlib load)", BLUES[5]),
    ]
    w, gap = 16.5, 3.0
    x = 2.0
    for i, (title, body, color) in enumerate(steps):
        ax.add_patch(
            plt.Rectangle((x, 4), w, 17, facecolor=color, edgecolor="white", linewidth=2, zorder=2)
        )
        tc = "white" if i >= 2 else INK
        ax.text(
            x + w / 2,
            18.2,
            title,
            ha="center",
            va="top",
            fontsize=11,
            fontweight="bold",
            color=tc,
            zorder=3,
        )
        ax.text(x + w / 2, 14.0, body, ha="center", va="top", fontsize=8.6, color=tc, zorder=3)
        if i < len(steps) - 1:
            ax.annotate(
                "",
                (x + w + gap - 0.4, 12.5),
                (x + w + 0.4, 12.5),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=2),
            )
        x += w + gap
    ax.text(
        0.5,
        23.6,
        "TurboEngine v3 offline training pipeline",
        fontsize=13,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        0.5,
        1.4,
        "The search and the v2 hand eval are frozen; only the residual pattern "
        "weights are learned, so the pure-Python leaf is unchanged.",
        fontsize=9,
        color=MUTED,
        style="italic",
    )
    _save(fig, "turbo_training_pipeline.png")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.parse_args()

    print("Generating TurboEngine figures ->", STATIC.relative_to(ROOT))
    fig_pipeline()
    fig_weights()
    fig_eval_learned()
    fig_pattern_coverage()
    elo = _load_elo()
    if elo:
        fig_ladder(elo)
        fig_strength(elo)
    print("done.")


if __name__ == "__main__":
    main()
