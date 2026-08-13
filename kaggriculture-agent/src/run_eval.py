import subprocess
import glob
import re
import os

replays = glob.glob('../replays/*.json')
results = []
total_wins = 0
total_games = 0

for replay in replays:
    print(f"Testing against {replay} (10 rounds)...")
    
    # We must pass the replay path to replay_agent.py via env variable
    env = os.environ.copy()
    env['REPLAY_PATH'] = replay
    
    cmd = ['python', 'test.py', '-n', '10', '-o', 'replay_agent.py']
    
    # Run the test
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = proc.stdout
    
    # Parse output:
    match = re.search(r'wins\s+(\d+)/(\d+)', out)
    if match:
        wins = int(match.group(1))
        games = int(match.group(2))
        total_wins += wins
        total_games += games
        
        # Get mean score
        mean_match = re.search(r'mean\s+(\d+)', out)
        mean_score = mean_match.group(1) if mean_match else "N/A"
        
        res_str = f"vs {replay.split('/')[-1]}: {wins}/{games} wins | Mean Score: {mean_score}"
        print(res_str)
        results.append(res_str)
    else:
        print(f"Failed to parse output for {replay}")
        print(out)

print("\n--- FINAL RESULTS ---")
for r in results:
    print(r)
print(f"\nOverall Win Rate: {total_wins}/{total_games} ({(total_wins/max(1, total_games))*100:.1f}%)")
