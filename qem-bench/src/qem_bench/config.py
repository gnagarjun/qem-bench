"""YAML-driven, validated configuration for QEM-Bench."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"
METHOD_NAMES = (
    "baseline",
    "readout",
    "zne_linear",
    "zne_richardson",
    "combined_linear",
    "combined_richardson",
)


class ConfigError(ValueError):
    """Raised for missing or malformed configuration values."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NoiseSpec(Strict):
    """Phenomenological noise specification (not hardware-derived).

    p1/p2 are the Qiskit depolarizing parameters (lambda) of single/two-qubit gates.
    readout_p01 = P(read 1 | prepared 0); readout_p10 = P(read 0 | prepared 1).
    """

    name: str
    p1: float = Field(ge=0.0, le=4 / 3)
    p2: float = Field(ge=0.0, le=16 / 15)
    readout_p01: float = Field(ge=0.0, lt=1.0)
    readout_p10: float = Field(ge=0.0, lt=1.0)
    thermal: bool = False
    t1_us: float = Field(default=100.0, gt=0)
    t2_us: float = Field(default=80.0, gt=0)
    gate_time_1q_ns: float = Field(default=35.0, ge=0)
    gate_time_2q_ns: float = Field(default=300.0, ge=0)

    @model_validator(mode="after")
    def _physical(self) -> NoiseSpec:
        if self.readout_p01 + self.readout_p10 >= 1.0:
            raise ValueError("readout_p01 + readout_p10 must be < 1 (assignment matrix singular)")
        if self.thermal and self.t2_us > 2 * self.t1_us:
            raise ValueError("unphysical relaxation: T2 must satisfy T2 <= 2*T1")
        return self

    def scaled(self, gate: float = 1.0, readout: float = 1.0, name: str | None = None) -> NoiseSpec:
        data = self.model_dump()
        data.update(
            name=name or f"{self.name}_g{gate:g}_r{readout:g}",
            p1=self.p1 * gate,
            p2=self.p2 * gate,
            readout_p01=self.readout_p01 * readout,
            readout_p10=self.readout_p10 * readout,
        )
        return NoiseSpec(**data)


class InstanceSpec(Strict):
    family: Literal["bell", "ghz", "qaoa"]
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ZNESpec(Strict):
    scale_factors: tuple[float, ...] = (1.0, 3.0, 5.0)
    folding: Literal["global", "local"] = "global"
    allocation_equal_budget: Literal["equal", "proportional_gamma"] = "proportional_gamma"
    use_effective_scales: bool = True  # extrapolate in measured (error-mass) scale, not nominal

    @field_validator("scale_factors")
    @classmethod
    def _scales(cls, v: tuple[float, ...]) -> tuple[float, ...]:
        if len(v) < 2 or v[0] != 1.0 or any(b <= a for a, b in zip(v, v[1:], strict=False)):
            raise ValueError("scale_factors must start at 1.0, be strictly increasing, len>=2")
        return v


class ReadoutSpec(Strict):
    full_max_qubits: int = Field(default=3, ge=1, le=10)
    calibration_shots_equal_primary: Literal["match_primary"] | int = "match_primary"
    calibration_fraction_equal_budget: float = Field(default=0.2, gt=0.0, lt=1.0)
    physicality: Literal["none", "simplex"] = "none"
    condition_warning: float = Field(default=1e3, gt=1)
    condition_failure: float = Field(default=1e12, gt=1)


class NoiseRef(Strict):
    base: str
    gate_multiplier: float = Field(default=1.0, ge=0)
    readout_multiplier: float = Field(default=1.0, ge=0)
    label: str | None = None


class BlockSpec(Strict):
    name: str
    purpose: str
    instances: tuple[str, ...]
    noise: tuple[NoiseRef, ...]
    shots: tuple[int, ...]
    methods: tuple[str, ...] = METHOD_NAMES
    comparisons: tuple[Literal["A", "B"], ...] = ("A", "B")
    zne: ZNESpec = ZNESpec()
    repetitions: int | None = None
    sampling_mode: Literal["exact", "aer"] | None = None

    @field_validator("methods")
    @classmethod
    def _methods(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        bad = set(v) - set(METHOD_NAMES)
        if bad or "baseline" not in v:
            raise ValueError(f"unknown methods {bad} or baseline missing")
        return v

    @field_validator("shots")
    @classmethod
    def _shots(cls, v: tuple[int, ...]) -> tuple[int, ...]:
        if not v or any(s < 16 for s in v):
            raise ValueError("shot budgets must be >= 16")
        return v


class AnalysisSpec(Strict):
    confidence_level: float = Field(default=0.95, gt=0.5, lt=1.0)
    bootstrap_samples: int = Field(default=2000, ge=200)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    practical_threshold: float = Field(default=0.10, ge=0)


class ExperimentConfig(Strict):
    schema_version: str = SCHEMA_VERSION
    profile: str
    seed: int
    repetitions: int = Field(ge=2)
    sampling_mode: Literal["exact", "aer"] = "exact"
    optimization_level: int = Field(default=1, ge=0, le=3)
    noise_levels: dict[str, NoiseSpec]
    instances: dict[str, InstanceSpec]
    readout: ReadoutSpec = ReadoutSpec()
    blocks: tuple[BlockSpec, ...]
    analysis: AnalysisSpec = AnalysisSpec()

    @model_validator(mode="after")
    def _refs(self) -> ExperimentConfig:
        for b in self.blocks:
            for i in b.instances:
                if i not in self.instances:
                    raise ValueError(f"block {b.name}: unknown instance {i}")
            for n in b.noise:
                if n.base not in self.noise_levels:
                    raise ValueError(f"block {b.name}: unknown noise level {n.base}")
        return self

    def config_hash(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def resolve_noise(self, ref: NoiseRef) -> NoiseSpec:
        base = self.noise_levels[ref.base]
        if ref.gate_multiplier == 1.0 and ref.readout_multiplier == 1.0 and ref.label is None:
            return base
        return base.scaled(ref.gate_multiplier, ref.readout_multiplier, ref.label)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing configuration file: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ConfigError(f"malformed configuration file (expected mapping): {path}")
    return data


def load_config(profile: str, config_dir: str | Path = "configs") -> ExperimentConfig:
    """Merge default/noise/shots/circuits/experiments YAML files into one validated config."""
    d = Path(config_dir)
    default = _read_yaml(d / "default.yaml")
    noise = _read_yaml(d / "noise_models.yaml")
    shots = _read_yaml(d / "shot_budgets.yaml")
    circuits = _read_yaml(d / "circuits.yaml")
    experiments = _read_yaml(d / "experiments.yaml")
    profiles = experiments.get("profiles", {})
    if profile not in profiles:
        raise ConfigError(f"unknown profile '{profile}'; available: {sorted(profiles)}")
    prof = profiles[profile]
    budgets = shots.get("budgets", {})
    blocks = []
    for blk in prof.get("blocks", []):
        blk = dict(blk)
        if isinstance(blk.get("shots"), str):
            if blk["shots"] not in budgets:
                raise ConfigError(f"unknown shot budget set {blk['shots']}")
            blk["shots"] = budgets[blk["shots"]]
        blocks.append(blk)
    try:
        return ExperimentConfig.model_validate(dict(
            profile=profile,
            seed=prof.get("seed", default["project"]["seed"]),
            repetitions=prof.get("repetitions", default["execution"]["repetitions"]),
            sampling_mode=prof.get("sampling_mode", default["execution"]["sampling_mode"]),
            optimization_level=default["execution"]["optimization_level"],
            noise_levels={k: {"name": k, **v} for k, v in noise["levels"].items()},
            instances={k: {"name": k, **v} for k, v in circuits["instances"].items()},
            readout=default.get("readout", {}),
            analysis=default.get("analysis", {}),
            blocks=blocks,
        ))
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"missing configuration key: {exc}") from exc
