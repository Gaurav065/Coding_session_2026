import json
import sys

sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')
from decoded_agent import agent as decoded_agent

replay_path = r"C:\Users\GauravPatel\Downloads\top_player\94401941.json"

with open(replay_path, "r", encoding="utf-8") as f:
    data = json.load(f)

team_names = data.get("info", {}).get("TeamNames", ["", ""])
seat = 0 if team_names[0] == "Ryo Hasegawa" else 1

steps = data.get("steps", [])

match_count = 0
diff_count = 0
diffs = []

for step_idx in range(len(steps) - 1):
    obs = steps[step_idx][seat].get("observation", {})
    actual_action = steps[step_idx][seat].get("action")
    
    # Run decoded_agent on this exact observation
    predicted_action = decoded_agent(obs)
    
    # Compare
    is_exact = (actual_action == predicted_action)
    if is_exact:
        match_count += 1
    else:
        diff_count += 1
        diffs.append((step_idx, actual_action, predicted_action))

print(f"Total Steps Compared: {len(steps)-1}")
print(f"Exact Matches: {match_count} / {len(steps)-1} ({match_count/(len(steps)-1)*100:.2f}%)")
print(f"Differences:   {diff_count} / {len(steps)-1}")

print("\nFirst 10 Differences:")
for s, act, pred in diffs[:10]:
    print(f"  Step {s:03d} (Day {s//24:02d} Hr {s%24:02d}):")
    print(f"    Ryo Actual:    {act}")
    print(f"    Decoded Pred:  {pred}")
