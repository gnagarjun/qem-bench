import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "configs"
    shutil.copytree(ROOT / "configs", d)
    return d


@pytest.fixture
def moderate():
    from qem_bench.config import NoiseSpec
    return NoiseSpec(name="m", p1=0.002, p2=0.015, readout_p01=0.016, readout_p10=0.024)


@pytest.fixture
def ideal_spec():
    from qem_bench.config import NoiseSpec
    return NoiseSpec(name="ideal", p1=0, p2=0, readout_p01=0, readout_p10=0)
