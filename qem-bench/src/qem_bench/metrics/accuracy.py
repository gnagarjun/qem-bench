"""Accuracy metrics. theta_ideal is the exact noiseless expectation value."""

from __future__ import annotations

import numpy as np


def bias(est: np.ndarray, ideal: float) -> float:
    """E[theta_hat] - theta_ideal (sample mean over independent repetitions)."""
    return float(np.mean(est) - ideal)


def mse(est: np.ndarray, ideal: float) -> float:
    return float(np.mean((np.asarray(est) - ideal) ** 2))


def rmse(est: np.ndarray, ideal: float) -> float:
    return float(np.sqrt(mse(est, ideal)))


def abs_error(est: np.ndarray | float, ideal: float) -> np.ndarray:
    return np.abs(np.asarray(est) - ideal)


def mae(est: np.ndarray, ideal: float) -> float:
    return float(np.mean(abs_error(est, ideal)))
