import tarfile
import shutil
import os
import sys
import tempfile
import importlib.util
from kaggle_environments import make

def test_submission_tar():
    tar_path = r'C:\Coding\kaggriculture_architecture\submission\submission.tar.gz'
    assert os.path.exists(tar_path), "submission.tar.gz not found"
    
    extract_dir = os.path.join(tempfile.gettempdir(), 'kagg_canary_e777')
    shutil.rmtree(extract_dir, ignore_errors=True)
    os.makedirs(extract_dir, exist_ok=True)
    
    with tarfile.open(tar_path, 'r:gz') as tar:
        tar.extractall(extract_dir)
        
    main_py = os.path.join(extract_dir, 'main.py')
    assert os.path.exists(main_py), "main.py missing in extracted archive"
    
    # Load module dynamically as Kaggle worker does
    if extract_dir not in sys.path:
        sys.path.insert(0, extract_dir)
        
    spec = importlib.util.spec_from_file_location("main_submission_module", main_py)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agent_callable = module.agent
    
    print("="*75)
    print("CANARY VERIFICATION ON SUBMISSION.TAR.GZ")
    print("="*75)
    
    # Run test match for 720 steps
    for s in [42, 7, 1234, 555]:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent_callable, agent_callable])
        
        stat0 = env.steps[-1][0].status
        stat1 = env.steps[-1][1].status
        r0 = env.steps[-1][0].reward
        r1 = env.steps[-1][1].reward
        turns = len(env.steps)
        
        assert stat0 == "DONE" and stat1 == "DONE", f"Failed status: {stat0}, {stat1}"
        assert turns == 720, f"Turn mismatch: {turns}"
        
        print(f"Seed {s:<6} | Turns: {turns} | P0 Reward: ${r0:,.1f} ({stat0}) | P1 Reward: ${r1:,.1f} ({stat1}) | Symmetry Delta: {r0 - r1:+,.1f}")
        
    print("\nALL CANARY CHECKS PASSED FOR SUBMISSION.TAR.GZ!")

if __name__ == '__main__':
    test_submission_tar()
