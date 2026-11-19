"""Experimental design: enumeration and cost estimation of the reduced factorial design.

Strategy (documented in docs/methodology.md): a *core* grid crosses circuit instance x
noise level x shot budget for all methods, while noise intensity is studied by
one-factor-at-a-time *sensitivity sweeps* around the moderate level (gate noise and
readout noise varied separately) and ZNE design choices by a dedicated block. This avoids
the multiplicative cost of a full factorial while still isolating each factor.
"""

from __future__ import annotations

import pandas as pd

from qem_bench.config import ExperimentConfig


def design_matrix(cfg: ExperimentConfig) -> pd.DataFrame:
    rows = []
    for b in cfg.blocks:
        reps = b.repetitions or cfg.repetitions
        for inst in b.instances:
            for nref in b.noise:
                spec = cfg.resolve_noise(nref)
                for shots in b.shots:
                    rows.append({"block": b.name, "instance": inst, "noise": spec.name, "shots": shots,
                                 "repetitions": reps, "n_methods": len(b.methods),
                                 "comparisons": "".join(b.comparisons), "scales": str(b.zne.scale_factors),
                                 "folding": b.zne.folding})
    return pd.DataFrame(rows)


def design_summary(cfg: ExperimentConfig) -> dict[str, int]:
    dm = design_matrix(cfg)
    return {"blocks": len(cfg.blocks), "conditions": len(dm),
            "condition_repetitions": int(dm["repetitions"].sum()) if len(dm) else 0}
