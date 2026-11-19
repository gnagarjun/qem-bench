"""Pareto analysis of accuracy (RMSE) versus resource expenditure (total shots)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def pareto_mask(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """True for points not dominated (minimising both x and y; ties do not dominate)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = np.ones(x.size, dtype=bool)
    for i in range(x.size):
        dominated = (x <= x[i]) & (y <= y[i]) & ((x < x[i]) | (y < y[i]))
        mask[i] = not dominated.any()
    return mask


def pareto_table(agg: pd.DataFrame, group: list[str], x: str = "total_shots", y: str = "rmse") -> pd.DataFrame:
    parts = []
    for _, g in agg.dropna(subset=[x, y]).groupby(group, sort=True, dropna=False):
        parts.append(g.assign(pareto_optimal=pareto_mask(g[x].to_numpy(), g[y].to_numpy())))
    return pd.concat(parts, ignore_index=True) if parts else agg.assign(pareto_optimal=False)


PARETO_GROUP = ["block", "instance", "noise", "observable", "comparison"]
