"""Common estimator types and the method registry (extensible to PEC, CDR, ...)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MitigationError(RuntimeError):
    """A mitigation step produced a scientifically invalid result; never silently ignored."""


class IllConditionedCalibrationError(MitigationError):
    pass


@dataclass
class Estimate:
    value: float
    stderr: float
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MethodSpec:
    name: str
    readout: bool
    zne: bool
    extrapolation: str | None = None


METHODS: dict[str, MethodSpec] = {
    "baseline": MethodSpec("baseline", False, False),
    "readout": MethodSpec("readout", True, False),
    "zne_linear": MethodSpec("zne_linear", False, True, "linear"),
    "zne_richardson": MethodSpec("zne_richardson", False, True, "richardson"),
    "combined_linear": MethodSpec("combined_linear", True, True, "linear"),
    "combined_richardson": MethodSpec("combined_richardson", True, True, "richardson"),
}
