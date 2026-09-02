"""Collision-safe loader for frozen E776."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_POLICY = _ROOT / "agents" / "e776a_engine_exact_latent_pasture.py"
_SPEC = importlib.util.spec_from_file_location("e776_packaged_policy", _POLICY)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load packaged E776 policy")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def policy(obs, configuration=None):
    return _MODULE.agent(obs, configuration)
