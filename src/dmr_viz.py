"""
Matplotlib theme for the DM Remission analysis.

Colour tokens come from a validated categorical palette.  The three
categorical slots used here clear the all-pairs colour-vision-deficiency and
normal-vision separation gates on a light surface; the aqua slot sits below
3:1 contrast, so every chart that uses it also carries direct labels or is
printed next to its table.

Figures are written for a light background (notebook output, and the PNGs are
meant to be dropped into a report).
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# categorical slots 1-3
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
SERIES = [BLUE, ORANGE, AQUA]

# diverging pair + neutral midpoint (improvement <-> deterioration)
DIV_GOOD = BLUE
DIV_BAD = "#e34948"
DIV_MID = "#f0efec"

# status
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"

# sequential blue ramp
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# chrome
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

THAI_FONTS = ["Noto Sans Thai", "Tahoma", "Ayuthaya", "Thonburi",
              "Sarabun", "Leelawadee UI"]


def use_theme() -> None:
    """Apply the house style: recessive chrome, thin marks, no top/right spine."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 150,
        "figure.dpi": 110,
        "font.family": "sans-serif",
        "font.sans-serif": THAI_FONTS + ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 10,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titlesize": 12,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2.0,
        "lines.markersize": 8,
        "patch.linewidth": 0,
    })


def caption(ax, text: str) -> None:
    """Put a source / definition note under an axes."""
    ax.annotate(text, xy=(0, -0.18), xycoords="axes fraction",
                fontsize=8, color=MUTED, va="top", ha="left", wrap=True)


def bare_y(ax) -> None:
    """Drop the y grid and spine for charts that carry direct labels instead."""
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
