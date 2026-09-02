import os
import json
import glob

replay_dir = r'C:\Users\GauravPatel\Downloads\new_data_replays_31st_aug'
replay_files = glob.glob(os.path.join(replay_dir, "*.json"))
print(f"Total replay files: {len(replay_files)}")

sample_files = replay_files[:15]
for rf in sample_files:
    try:
        with open(rf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        steps = data.get("steps", [])
        if not steps:
            continue
        p0_rew = steps[-1][0].get("reward")
        p1_rew = steps[-1][1].get("reward")
        p0_stat = steps[-1][0].get("status")
        p1_stat = steps[-1][1].get("status")
        agents = data.get("agents", ["?", "?"])
        print(f"{os.path.basename(rf):<25} | P0: {p0_rew:>8.1f} ({p0_stat}) vs P1: {p1_rew:>8.1f} ({p1_stat}) | Agents: {agents}")
    except Exception as e:
        print(f"Error {rf}: {e}")
