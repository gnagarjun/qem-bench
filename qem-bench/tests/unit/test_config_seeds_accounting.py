import numpy as np
import pytest
import yaml
from pydantic import ValidationError
from qiskit.quantum_info import SparsePauliOp

from qem_bench.circuits.observables import diagonal_vector, measurement_basis
from qem_bench.config import ConfigError, NoiseSpec, ZNESpec, load_config
from qem_bench.execution.resource_tracker import plan_shots
from qem_bench.mitigation.base import METHODS
from qem_bench.seeds import int_seed, rng_for


@pytest.mark.parametrize("profile", ["smoke", "pilot", "standard", "full"])
def test_all_profiles_load(profile):
    cfg = load_config(profile, "configs")
    assert cfg.blocks and len(cfg.config_hash()) == 16


def test_unknown_profile(config_dir):
    with pytest.raises(ConfigError):
        load_config("nope", config_dir)


def test_missing_file(config_dir):
    (config_dir / "circuits.yaml").unlink()
    with pytest.raises(ConfigError):
        load_config("smoke", config_dir)


def test_malformed_values(config_dir):
    p = config_dir / "noise_models.yaml"
    d = yaml.safe_load(p.read_text())
    d["levels"]["moderate"]["p1"] = -0.1
    p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValidationError):
        load_config("smoke", config_dir)


def test_unknown_instance_reference(config_dir):
    p = config_dir / "experiments.yaml"
    d = yaml.safe_load(p.read_text())
    d["profiles"]["smoke"]["blocks"][0]["instances"] = ["does_not_exist"]
    p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValidationError):
        load_config("smoke", config_dir)


def test_noise_spec_physicality():
    with pytest.raises(ValidationError):
        NoiseSpec(name="x", p1=0, p2=0, readout_p01=0.6, readout_p10=0.5)
    with pytest.raises(ValidationError):
        NoiseSpec(name="x", p1=0, p2=0, readout_p01=0, readout_p10=0, thermal=True, t1_us=10, t2_us=30)


def test_scale_factor_validation():
    with pytest.raises(ValidationError):
        ZNESpec(scale_factors=(3.0, 5.0))
    with pytest.raises(ValidationError):
        ZNESpec(scale_factors=(1.0,))


def test_seeds_reproducible_and_distinct():
    a = rng_for(1, "blk", "inst", 0).random(5)
    b = rng_for(1, "blk", "inst", 0).random(5)
    c = rng_for(1, "blk", "inst", 1).random(5)
    np.testing.assert_array_equal(a, b)
    assert not np.allclose(a, c)
    seeds = {int_seed(7, "x", r) for r in range(1000)}
    assert len(seeds) == 1000


def test_diagonal_vector_and_basis():
    f = diagonal_vector(SparsePauliOp("ZI"))  # Z on qubit 1
    np.testing.assert_array_equal(f, [1, 1, -1, -1])
    assert measurement_basis(SparsePauliOp.from_list([("XI", 1), ("XX", 1)])) == "XX"
    with pytest.raises(ValueError):
        measurement_basis(SparsePauliOp.from_list([("XI", 1), ("ZI", 1)]))


def test_shot_plans_accounting():
    scales = (1.0, 3.0, 5.0)
    a = plan_shots(METHODS["combined_linear"], "A", 1000, 2, scales, 4)
    assert a.primary_shots == 1000 * 2 * 3 and a.calibration_shots == 4000 and a.total_shots == 10000
    base = plan_shots(METHODS["baseline"], "A", 1000, 2, scales, 4)
    assert base.total_shots == 2000 and base.calibration_shots == 0
    for m in METHODS.values():
        b = plan_shots(m, "B", 1000, 2, scales, 4)
        assert b.total_shots <= 2000 and b.total_shots >= 2000 * 0.98
    rich = plan_shots(METHODS["zne_richardson"], "B", 1000, 1, scales, 4)
    assert rich.shots_by_scale[1.0] > rich.shots_by_scale[5.0]  # |gamma| proportional allocation


def test_budget_too_small_raises():
    with pytest.raises(ValueError):
        plan_shots(METHODS["readout"], "B", 16, 1, (1.0, 3.0), 1, cal_fraction_b=0.999)
