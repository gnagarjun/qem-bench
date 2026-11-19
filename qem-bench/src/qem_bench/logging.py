"""Package-wide logging configuration."""

from __future__ import annotations

import logging
import sys


def get_logger(name: str = "qem_bench") -> logging.Logger:
    logger = logging.getLogger(name)
    root = logging.getLogger("qem_bench")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logger
