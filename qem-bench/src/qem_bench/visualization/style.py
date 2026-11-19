"""Shared publication style (Okabe-Ito colour-blind-safe palette, consistent sizes)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

METHOD_COLORS = {
    "baseline": "#555555", "readout": "#0072B2", "zne_linear": "#E69F00", "zne_richardson": "#D55E00",
    "combined_linear": "#009E73", "combined_richardson": "#CC79A7",
}
METHOD_LABELS = {
    "baseline": "Baseline", "readout": "Readout (REM)", "zne_linear": "ZNE-linear", "zne_richardson": "ZNE-Richardson",
    "combined_linear": "REM+ZNE-linear", "combined_richardson": "REM+ZNE-Richardson",
}
METHOD_MARKERS = {"baseline": "o", "readout": "s", "zne_linear": "^", "zne_richardson": "v",
                  "combined_linear": "D", "combined_richardson": "P"}
METHODS = list(METHOD_COLORS)
SINGLE = (3.5, 2.8)
DOUBLE = (7.2, 3.6)


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
        "legend.fontsize": 6.5, "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.grid": True,
        "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight",
        "figure.dpi": 110, "figure.constrained_layout.use": True,
    })


def save(fig: plt.Figure, out_dir: Path, name: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext, dpi in (("png", 300), ("pdf", None)):
        p = out_dir / f"{name}.{ext}"
        fig.savefig(p, dpi=dpi or "figure")
        paths.append(p)
    plt.close(fig)
    return paths
