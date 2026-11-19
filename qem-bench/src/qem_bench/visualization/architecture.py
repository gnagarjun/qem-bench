"""Figure 1: framework architecture (drawn programmatically, no data)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from qem_bench.visualization.style import save

STAGES = [
    ("YAML configs\n(pydantic-validated)", "#e8eef7"), ("Seeds\n(SeedSequence)", "#e8eef7"),
    ("Circuits\nBell / GHZ / QAOA\n+ ideal references", "#e6f4ea"), ("Transpile\n{rz, sx, x, cx}", "#e6f4ea"),
    ("Noise models\ndepol. + readout\n(+T1/T2)", "#fdf0e0"), ("Execution\nAer: exact | per-shot", "#fdf0e0"),
    ("Mitigation\nbaseline, REM,\nZNE, REM+ZNE", "#f6e6f0"), ("Resource ledger\nshots A / B, timings", "#f6e6f0"),
    ("Raw runs\nparquet + manifest", "#eeeeee"), ("Analysis\nstats, FDR, Pareto,\nefficiency", "#eeeeee"),
    ("Figures, tables,\npaper, viewer", "#eeeeee"),
]


def architecture_figure(out_dir: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.set_axis_off()
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 2.2)
    pos: list[tuple[float, float]] = [(float(i % 6), 1.3 if i < 6 else 0.15) for i in range(len(STAGES))]
    pos = [(x + 0.05, y) if i < 6 else (5 - (i - 6) + 0.05, y) for i, (x, y) in enumerate(pos)]
    for (x, y), (label, col) in zip(pos, STAGES, strict=True):
        ax.add_patch(FancyBboxPatch((x, y), 0.88, 0.72, boxstyle="round,pad=0.02", fc=col, ec="#333333", lw=0.7))
        ax.text(x + 0.44, y + 0.36, label, ha="center", va="center", fontsize=6.2)
    for i in range(len(pos) - 1):
        (x0, y0), (x1, y1) = pos[i], pos[i + 1]
        if y0 == y1:
            a = ((x0 + 0.9, y0 + 0.36), (x1 - 0.02, y1 + 0.36)) if x1 > x0 else ((x0 - 0.02, y0 + 0.36), (x1 + 0.9, y1 + 0.36))
        else:
            a = ((x0 + 0.44, y0 - 0.02), (x1 + 0.44, y1 + 0.74))
        ax.add_patch(FancyArrowPatch(*a, arrowstyle="-|>", mutation_scale=7, lw=0.7, color="#333333"))
    ax.set_title("QEM-Bench experimental pipeline", fontsize=8.5)
    return save(fig, out_dir, "fig01_architecture")
