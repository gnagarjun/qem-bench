"""Environment capture for reproducibility metadata."""

from __future__ import annotations

import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

PACKAGES = ("qiskit", "qiskit-aer", "numpy", "scipy", "pandas", "matplotlib", "seaborn", "pydantic", "pyyaml", "pyarrow")


def _cpu() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _git() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5,
                              cwd=Path(__file__).parent).stdout.strip() or "unavailable"
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def environment_info() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for p in PACKAGES:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versions[p] = None
    import os
    return {"python": sys.version.split()[0], "platform": platform.platform(), "cpu": _cpu(),
            "cpu_count": os.cpu_count(), "packages": versions, "git_commit": _git(),
            "note": "wall-clock timings are machine-specific and not comparable across hosts"}
