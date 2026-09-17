# SPDX-License-Identifier: Apache-2.0
"""Grandmaster Modular Apex Kaggriculture Agent Entrypoint."""

import sys
from pathlib import Path

_MODULAR_DIR = Path(__file__).resolve().parent / "modular_apex"
if str(_MODULAR_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULAR_DIR))

from modular_apex.main import agent

__all__ = ["agent"]

