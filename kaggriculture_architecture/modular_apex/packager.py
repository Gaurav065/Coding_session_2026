# SPDX-License-Identifier: Apache-2.0
"""Packager, compiler, and validator for Modular Apex Kaggle submissions.

Compiles all modular components into a standalone single-file submission.py / main.py
with zero external dependencies and zero __file__ references, and validates sandbox execution.
"""

import base64
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
MODULAR_DIR = ROOT / "modular_apex"
TARGET_TAR = ROOT / "submission.tar.gz"
TARGET_SUBMISSION_PY = ROOT / "submission.py"
TARGET_MAIN_PY = ROOT / "main.py"

FILES_TO_PACK = [
    "config.py",
    "payload.py",
    "router.py",
    "chassis.py",
    "_guards_source.py",
    "guards.py",
    "main.py",
]


def compile_standalone_py():
    print("\n1. Compiling standalone single-file agent (submission.py / main.py)...")

    config_code = (MODULAR_DIR / "config.py").read_text(encoding="utf-8")
    chassis_code = (MODULAR_DIR / "chassis.py").read_text(encoding="utf-8")
    payload_code = (MODULAR_DIR / "payload.py").read_text(encoding="utf-8")
    router_code = (MODULAR_DIR / "router.py").read_text(encoding="utf-8")
    guards_source = (MODULAR_DIR / "_guards_source.py").read_bytes()

    compressed_guards = base64.b85encode(zlib.compress(guards_source, 9)).decode("ascii")

    # Clean router imports (remove try: from .config ... except ...)
    cleaned_router = []
    for line in router_code.splitlines():
        if line.startswith("from __future__"):
            continue
        if line.startswith("try:") or "import ROUTE_STEP" in line or "from config import" in line or line.startswith("except ImportError:"):
            continue
        cleaned_router.append(line)
    router_clean = "\n".join(cleaned_router).strip()

    # Clean payload imports (payload self-contained)
    cleaned_payload = []
    for line in payload_code.splitlines():
        if line.startswith("from __future__"):
            continue
        if line.startswith("import ") or line.startswith("from "):
            continue
        cleaned_payload.append(line)
    payload_clean = "\n".join(cleaned_payload).strip()

    # Clean chassis and config __future__ imports
    cleaned_config = "\n".join(l for l in config_code.splitlines() if not l.startswith("from __future__")).strip()
    cleaned_chassis = "\n".join(l for l in chassis_code.splitlines() if not l.startswith("from __future__")).strip()

    parts = [
        '# SPDX-License-Identifier: Apache-2.0',
        '"""Modular Apex: Grandmaster Single-File Kaggriculture Agent."""',
        'from __future__ import annotations\n',
        'import base64',
        'from collections import defaultdict, deque',
        'import copy',
        'import json',
        'import math',
        'import sys',
        'from typing import Any, Dict, List, Optional, Set, Tuple',
        'import zlib\n',
        '# ===========================================================================',
        '# 1. CONFIGURATION',
        '# ===========================================================================',
        cleaned_config,
        '\n# ===========================================================================',
        '# 2. CHASSIS ENGINE',
        '# ===========================================================================',
        cleaned_chassis,
        '\n# ===========================================================================',
        '# 3. STRATEGIC PAYLOAD ROUTES',
        '# ===========================================================================',
        payload_clean,
        '\n# ===========================================================================',
        '# 4. SCENARIO ROUTER',
        '# ===========================================================================',
        router_clean,
        '\n# ===========================================================================',
        '# 5. DEFENSIVE GUARDS WRAPPER',
        '# ===========================================================================',
        f"_GUARDS_SOURCE = zlib.decompress(base64.b85decode('{compressed_guards}')).decode('utf-8')",
        "_BYTECODE = compile(_GUARDS_SOURCE, '<guards_source>', 'exec')\n",
        'def wrap_apex_guards(_IMPL):',
        '    scope = dict(globals())',
        "    scope['_IMPL'] = _IMPL",
        '    exec(_BYTECODE, scope)',
        "    return scope['agent']",
        '\n# ===========================================================================',
        '# 6. MASTER AGENT INITIALIZATION',
        '# ===========================================================================',
        '_ROUTES = load_routes()',
        'for _tape in _ROUTES.values():',
        '    _tape[0] = dict(_tape[0], market=[list(o) for o in CLEAN_OPENING])\n',
        '_BASE_AGENT = make_agent(_ROUTES, router=router, **CHASSIS_SETTINGS)',
        'agent = wrap_apex_guards(_BASE_AGENT)\n',
    ]

    compiled_code = "\n".join(parts)

    assert "__file__" not in compiled_code, "CRITICAL ERROR: __file__ found in compiled script!"

    TARGET_SUBMISSION_PY.write_text(compiled_code, encoding="utf-8")
    TARGET_MAIN_PY.write_text(compiled_code, encoding="utf-8")

    sub_size = TARGET_SUBMISSION_PY.stat().st_size
    sub_sha = hashlib.sha256(TARGET_SUBMISSION_PY.read_bytes()).hexdigest()
    print(f"  + Generated: {TARGET_SUBMISSION_PY.name} ({sub_size:,} bytes)")
    print(f"  + Generated: {TARGET_MAIN_PY.name} ({TARGET_MAIN_PY.stat().st_size:,} bytes)")
    print(f"  + SHA256   : {sub_sha}")
    return compiled_code


def build_package():
    print("=" * 70)
    print("BUILDING MODULAR APEX KAGGLE SUBMISSION")
    print("=" * 70)

    # 1. Compile standalone single-file agent
    compile_standalone_py()

    # 2. Verify all required files exist
    print("\n2. Packaging modular tarball (submission.tar.gz)...")
    for fname in FILES_TO_PACK:
        fpath = MODULAR_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Required file {fpath} is missing!")
        print(f"  + {fname:<22} ({fpath.stat().st_size:,} bytes)")

    # 3. Create submission.tar.gz
    if TARGET_TAR.exists():
        TARGET_TAR.unlink()

    with tarfile.open(TARGET_TAR, "w:gz") as tar:
        for fname in FILES_TO_PACK:
            fpath = MODULAR_DIR / fname
            tar.add(fpath, arcname=fname)

    size = TARGET_TAR.stat().st_size
    sha256 = hashlib.sha256(TARGET_TAR.read_bytes()).hexdigest()
    print(f"Created: {TARGET_TAR.name} ({size:,} bytes)")
    print(f"SHA256 : {sha256}")

    # 4. Test execution in Kaggle sandbox emulation (without __file__)
    print("\n3. Validating single-file standalone execution (emulating Kaggle env)...")
    sandbox_env = {}
    exec(compile(TARGET_SUBMISSION_PY.read_text(encoding="utf-8"), "submission.py", "exec"), sandbox_env)

    assert "agent" in sandbox_env, "Callable 'agent' not found in execution scope!"
    agent_fn = sandbox_env["agent"]
    assert callable(agent_fn), "agent is not callable!"

    dummy_obs = {
        "step": 0, "day": 0, "hour": 0, "player": 0,
        "farms": [{"money": 200, "farmer": [4, 4], "hands": [], "tiles": [[None]*10 for _ in range(10)]},
                  {"money": 200, "farmer": [5, 5], "hands": [], "tiles": [[None]*10 for _ in range(10)]}],
        "private": {"shed": {}, "inventories": [{}]},
        "market": {"prices": {"WHEAT": 20, "CARROT": 30}, "inventory": {}},
        "town": {"unlocked_shops": []}
    }
    action = agent_fn(dummy_obs)
    assert isinstance(action, dict), f"Action must be dict, got {type(action)}"
    assert "market" in action, "Action missing 'market'"
    print("Single-file execution verified! Step 0 action generated cleanly:")
    print(f"  market: {action.get('market')}")
    print(f"  farmer: {action.get('farmer')}")

    print("\n" + "=" * 70)
    print("SUBMISSION IS 100% PRODUCTION READY FOR KAGGLE!")
    print("=" * 70)


if __name__ == "__main__":
    build_package()
