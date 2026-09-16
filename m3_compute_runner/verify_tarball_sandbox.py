#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify extracted submission.tar.gz directly in multi-agent matches."""

import tarfile
import tempfile
import sys
from pathlib import Path
import kaggle_environments

def verify():
    tar_path = Path(__file__).resolve().parent.parent / "kaggriculture_architecture" / "submission.tar.gz"
    assert tar_path.exists(), f"Missing {tar_path}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(tmpdir)
        sys.path.insert(0, tmpdir)
        import main

        print("1. Match vs Starter (Seed 42)...")
        env1 = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
        env1.run([main.agent, "starter"])
        s1_us, s1_opp = env1.steps[-1][0]["reward"], env1.steps[-1][1]["reward"]
        print(f"   Score: Us = ${s1_us:,.0f} | Starter = ${s1_opp:,.0f}")
        assert s1_us > s1_opp * 10, "Should crush starter agent"

        print("2. Match vs Random (Seed 42)...")
        env2 = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
        env2.run([main.agent, "random"])
        s2_us, s2_opp = env2.steps[-1][0]["reward"], env2.steps[-1][1]["reward"]
        print(f"   Score: Us = ${s2_us:,.0f} | Random = ${s2_opp:,.0f}")
        assert s2_us > s2_opp * 10, "Should crush random agent"

        print("3. Match vs Pass (Seed 100 - Pizza 2+ SE Expansion)...")
        env3 = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 100})
        env3.run([main.agent, "pass"])
        s3_us, s3_opp = env3.steps[-1][0]["reward"], env3.steps[-1][1]["reward"]
        quads = env3.steps[-1][0]["observation"]["farms"][0]["unlocked_quadrants"]
        print(f"   Score: Us = ${s3_us:,.0f} | Pass = ${s3_opp:,.0f} | Quads = {quads}")
        assert len(quads) == 4, "Should unlock all 4 quadrants"

        print("\nAll sandbox tests PASSED! The submission tarball is flawless.")

if __name__ == "__main__":
    verify()
