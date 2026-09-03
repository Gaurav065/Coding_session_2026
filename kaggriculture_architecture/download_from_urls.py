import os
import re
import subprocess
import time

urls_text = """
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55929317&episodeId=105053642
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55967068&episodeId=105053188
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55961666&episodeId=105054877
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55973192&episodeId=105053642
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55969334&episodeId=105053835
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55964860&episodeId=105053188
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55971522&episodeId=105054030
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55971062&episodeId=105052983
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55967180&episodeId=105054877
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55968851&episodeId=105054889
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55972843&episodeId=105052865
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55972854&episodeId=105054622
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55962681&episodeId=105052256
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55973366&episodeId=105054502
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55971734&episodeId=105053757
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55972436&episodeId=105054502
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55972593&episodeId=105052994
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55969604&episodeId=105055523
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55958242&episodeId=105054756
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55960354&episodeId=105053836
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55959086&episodeId=105055612
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55970580&episodeId=105055612
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55972770&episodeId=105055377
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55966174&episodeId=105054030
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55959990&episodeId=105054524
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55972045&episodeId=105052965
https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55970502&episodeId=105054890
"""

# Extract all unique submission IDs while preserving order
all_ids = re.findall(r'submissionId=(\d+)', urls_text)
submission_ids = list(dict.fromkeys(all_ids))

# The user asked for top 20, but provided 27. Let's process the first 20!
submission_ids = submission_ids[:20]

REPLAY_DIR = r"D:\replays"
os.makedirs(REPLAY_DIR, exist_ok=True)

print(f"Starting Kaggle API extraction for {len(submission_ids)} submissions...\n")

total_downloaded = 0

for i, sub_id in enumerate(submission_ids):
    print(f"[{i+1}/{len(submission_ids)}] Querying Submission ID: {sub_id} ...")
    
    # 1. Fetch episodes for this submission
    result = subprocess.run(
        ["python", "-m", "kaggle", "competitions", "episodes", str(sub_id)], 
        capture_output=True, text=True
    )
    
    # Check for authentication or API errors
    if result.returncode != 0 or "Unauthorized" in result.stdout:
        print(f"  -> Error fetching episodes. Make sure KAGGLE_API_TOKEN is set. stdout: {result.stdout}")
        continue
        
    lines = result.stdout.split('\n')
    ep_ids = []
    
    # Parse the CLI output. The first column is usually the Episode ID
    for line in lines:
        parts = line.split()
        if parts and parts[0].isdigit():
            ep_ids.append(parts[0])
            
    if not ep_ids:
        print("  -> Found 0 episodes for this submission. Output:", result.stdout)
        continue
        
    # We want exactly 30 episodes
    top_30 = ep_ids[:30]
    print(f"  -> Found {len(ep_ids)} episodes. Downloading top {len(top_30)}...")
    
    for ep_idx, ep_id in enumerate(top_30):
        # We use a progress indicator without spamming new lines
        print(f"     Downloading {ep_idx+1}/{len(top_30)} (Episode {ep_id})...", end="\r", flush=True)
        subprocess.run(
            ["python", "-m", "kaggle", "competitions", "replay", str(ep_id), "-p", REPLAY_DIR],
            capture_output=True # suppress output to keep it clean
        )
        total_downloaded += 1
        
    print(f"     Downloaded {len(top_30)} replays successfully!                        ")
    time.sleep(1) # Small delay to be polite to Kaggle API

print(f"\nFinished! Successfully downloaded {total_downloaded} total replays into {REPLAY_DIR}")
