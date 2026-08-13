import os
import glob
import subprocess
import statistics
import time

def main():
    print("==================================================")
    print("   KAGGRICULTURE MASTER REPLAY BENCHMARK SUITE    ")
    print("==================================================")
    
    replays = glob.glob("replays/*.json")
    if not replays:
        print("No replays found in replays/ directory.")
        return
        
    print(f"Found {len(replays)} replay opponents. Booting test harness...\n")
    
    all_scores = []
    wins = 0
    total_matches = len(replays) * 3
    
    for replay_path in replays:
        print(f"--- Testing against Replay: {os.path.basename(replay_path)} ---")
        os.environ["REPLAY_PATH"] = os.path.abspath(replay_path)
        
        # Run test.py with 3 random seeds per opponent
        cmd = ["python", "test.py", "-n", "3", "-o", "src/replay_opponent.py"]
        
        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout
            
            # Print the individual match results
            for line in output.split('\n'):
                if "seed" in line and "me" in line:
                    print(line)
                    # Parse score
                    parts = line.split()
                    if len(parts) >= 6:
                        score = float(parts[3])
                        all_scores.append(score)
                        if "WIN" in line:
                            wins += 1
        except subprocess.CalledProcessError as e:
            print(f"Error testing {replay_path}: {e.stderr}")
            continue
            
    print("\n==================================================")
    print("               FINAL AGGREGATED STATS             ")
    print("==================================================")
    if all_scores:
        print("mean %.0f   median %.0f   min %.0f   max %.0f   wins %d/%d" % (
            statistics.mean(all_scores), statistics.median(all_scores),
            min(all_scores), max(all_scores), wins, total_matches
        ))
    else:
        print("No scores recorded.")

if __name__ == "__main__":
    main()
