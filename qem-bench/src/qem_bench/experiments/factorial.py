"""Factorial and one-factor-at-a-time design helpers."""

from __future__ import annotations

import itertools
from typing import Any


def full_factorial(levels: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(levels)
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*(levels[k] for k in keys))]


def one_factor_at_a_time(center: dict[str, Any], sweeps: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Vary one factor at a time around `center`; the centre point is included once."""
    out = [dict(center)]
    for k, values in sweeps.items():
        for v in values:
            if v != center[k]:
                out.append({**center, k: v})
    return out
