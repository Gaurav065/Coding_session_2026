import tarfile
import zipfile
import tempfile
import os
import sys

def verify_archive(archive_path, archive_type="tar"):
    print("=" * 80)
    print(f"VERIFYING {archive_type.upper()} ARCHIVE: {archive_path}")
    print("=" * 80)
    
    if not os.path.exists(archive_path):
        print(f"FAIL: Archive does not exist at {archive_path}")
        return False
        
    size = os.path.getsize(archive_path)
    print(f"File size: {size:,} bytes")
    
    # 1. Inspect archive file list
    with tempfile.TemporaryDirectory() as tmpdir:
        if archive_type == "tar":
            with tarfile.open(archive_path, "r:gz") as tar:
                members = tar.getnames()
                print(f"Archive contents ({len(members)} entries): {members}")
                if "main.py" not in members:
                    print("FAIL: 'main.py' is NOT at the root of the tar.gz archive!")
                    return False
                tar.extractall(tmpdir)
        elif archive_type == "zip":
            with zipfile.ZipFile(archive_path, "r") as zipf:
                members = zipf.namelist()
                print(f"Archive contents ({len(members)} entries): {members}")
                if "main.py" not in members:
                    print("FAIL: 'main.py' is NOT at the root of the zip archive!")
                    return False
                zipf.extractall(tmpdir)
                
        extracted_main = os.path.join(tmpdir, "main.py")
        if not os.path.isfile(extracted_main):
            print("FAIL: Extracted main.py is missing!")
            return False
            
        with open(extracted_main, "r", encoding="utf-8") as f:
            content = f.read()
            
        print(f"Extracted main.py size: {len(content):,} bytes, lines: {len(content.splitlines())}")
        
        # Check agent definition
        if "def agent(" not in content:
            print("FAIL: 'def agent(' not found in extracted main.py!")
            return False
        print("OK: 'def agent(' found in main.py")
        
        # Check standard imports (no forbidden/unsupported modules)
        for forbidden in ["torch", "tensorflow", "sklearn", "scipy", "pandas", "numpy"]:
            if f"import {forbidden}" in content:
                print(f"WARNING: Found 3rd-party import '{forbidden}'")
                
        # 2. Run simulation in isolated python environment loading extracted main.py directly
        from kaggle_environments import make
        
        print("\nRunning game simulation with isolated main.py...")
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42, "runTimeout": 60})
        env.run([extracted_main, "starter"])
        
        p0_final = env.steps[-1][0]
        p1_final = env.steps[-1][1]
        
        print(f"Simulation result: Player 0 Reward = ${p0_final['reward']:,.0f} | Status = {p0_final['status']}")
        print(f"                   Player 1 Reward = ${p1_final['reward']:,.0f} | Status = {p1_final['status']}")
        
        if p0_final["status"] != "DONE":
            print(f"FAIL: Simulation finished with status {p0_final['status']} instead of DONE!")
            if p0_final.get("info"):
                print(f"Info/Error details: {p0_final['info']}")
            return False
            
        if p0_final["reward"] <= 0:
            print("FAIL: Reward is <= 0!")
            return False
            
    print(f"SUCCESS: {archive_type.upper()} archive verified 100% valid and ready for Kaggle deployment!")
    return True

if __name__ == "__main__":
    tar_path = r"C:\Coding\project_doppelganger\submission.tar.gz"
    zip_path = r"C:\Coding\project_doppelganger\submission.zip"
    
    tar_ok = verify_archive(tar_path, "tar")
    print()
    zip_ok = verify_archive(zip_path, "zip")
    
    print("\n" + "=" * 80)
    if tar_ok and zip_ok:
        print("ALL ARCHIVES (TAR.GZ AND ZIP) ARE 100% VERIFIED AND READY FOR KAGGLE DEPLOYMENT!")
    else:
        print("VERIFICATION FAILED ON ONE OR MORE ARCHIVES!")
    print("=" * 80)
