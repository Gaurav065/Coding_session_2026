import tarfile
import os

def package():
    files_to_include = [
        ("submission_agent.py", "main.py"), # Rename entrypoint to main.py for Kaggle
        ("hrl_heuristic_agent.py", "hrl_heuristic_agent.py"),
        ("ppo_resnet_day30.pth", "ppo_resnet_day30.pth")
    ]
    
    out_file = "kaggle_submission.tar.gz"
    
    # Check if files exist
    for f, _ in files_to_include:
        if not os.path.exists(f):
            print(f"ERROR: Missing required file {f}!")
            print("Make sure your PPO script successfully generated ppo_resnet_day30.pth")
            return
            
    print(f"Packaging {out_file}...")
    with tarfile.open(out_file, "w:gz") as tar:
        for local_file, arcname in files_to_include:
            tar.add(local_file, arcname=arcname)
            print(f"Added {local_file} as {arcname}")
            
    print("\n✅ Packaging successful!")
    print(f"You can now upload '{out_file}' directly to Kaggle!")

if __name__ == "__main__":
    package()
