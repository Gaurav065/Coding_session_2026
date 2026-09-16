# SPDX-License-Identifier: Apache-2.0
"""Packager and validator for Modular Apex Kaggle submissions."""

import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULAR_DIR = ROOT / "modular_apex"
TARGET_TAR = ROOT / "submission.tar.gz"

FILES_TO_PACK = [
    "config.py",
    "payload.py",
    "router.py",
    "chassis.py",
    "_guards_source.py",
    "guards.py",
    "main.py",
]

def build_package():
    print("=" * 70)
    print("BUILDING MODULAR APEX KAGGLE SUBMISSION PACKAGE")
    print("=" * 70)

    # 1. Verify all required files exist
    for fname in FILES_TO_PACK:
        fpath = MODULAR_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Required file {fpath} is missing!")
        print(f"  + {fname:<22} ({fpath.stat().st_size:,} bytes)")

    # 2. Create submission.tar.gz
    if TARGET_TAR.exists():
        TARGET_TAR.unlink()

    with tarfile.open(TARGET_TAR, "w:gz") as tar:
        for fname in FILES_TO_PACK:
            fpath = MODULAR_DIR / fname
            # Archive directly at root level inside the tarball
            tar.add(fpath, arcname=fname)

    size = TARGET_TAR.stat().st_size
    sha256 = hashlib.sha256(TARGET_TAR.read_bytes()).hexdigest()
    print(f"\nCreated: {TARGET_TAR.name} ({size:,} bytes)")
    print(f"SHA256 : {sha256}")

    # 3. Test unpacking and Kaggle callable loader
    print("\nValidating package in isolated sandbox...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with tarfile.open(TARGET_TAR, "r:gz") as tar:
            tar.extractall(tmp_path)

        # Emulate Kaggle agent loader
        sys.path.insert(0, str(tmp_path))
        import main
        callables = [v for v in main.__dict__.values() if callable(v)]
        last_callable = callables[-1] if callables else None

        assert last_callable is not None, "Kaggle loader failed: no callable found in main.py!"
        assert last_callable.__name__ == "agent", f"Expected 'agent', got '{last_callable.__name__}'"

        # Execute dummy step 0
        dummy_obs = {
            "step": 0, "day": 0, "hour": 0, "player": 0,
            "farms": [{"money": 200, "farmer": [4, 4], "hands": [], "tiles": [[None]*10 for _ in range(10)]},
                      {"money": 200, "farmer": [5, 5], "hands": [], "tiles": [[None]*10 for _ in range(10)]}],
            "private": {"shed": {}, "inventories": [{}]},
            "market": {"prices": {"WHEAT": 20, "CARROT": 30}, "inventory": {}},
            "town": {"unlocked_shops": []}
        }
        action = last_callable(dummy_obs)
        assert isinstance(action, dict), f"Action must be dict, got {type(action)}"
        assert "market" in action, "Action missing 'market'"
        print("Sandbox execution verified! Step 0 action generated cleanly:")
        print(f"  market: {action.get('market')}")
        print(f"  farmer: {action.get('farmer')}")

    print("\nPackage is 100% PRODUCTION READY for Kaggle submission!")
    print("=" * 70)
    return TARGET_TAR, sha256

if __name__ == "__main__":
    build_package()
