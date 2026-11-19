"""Reproducible, collision-free random streams based on numpy SeedSequence."""

from __future__ import annotations

import hashlib

import numpy as np


def stable_int(*parts: object) -> int:
    """Platform-independent 32-bit integer derived from arbitrary labels."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:4], "little")


def seed_sequence(root: int, *labels: object) -> np.random.SeedSequence:
    """Independent stream for a labelled experimental unit (e.g. condition, repetition)."""
    return np.random.SeedSequence(entropy=root, spawn_key=tuple(stable_int(x) for x in labels))


def rng_for(root: int, *labels: object) -> np.random.Generator:
    return np.random.default_rng(seed_sequence(root, *labels))


def int_seed(root: int, *labels: object) -> int:
    """32-bit seed for libraries that need an integer (e.g. Aer seed_simulator)."""
    return int(seed_sequence(root, *labels).generate_state(1)[0])
