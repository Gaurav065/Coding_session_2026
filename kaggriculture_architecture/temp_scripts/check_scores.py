import json

replay_path = r"C:\Users\GauravPatel\Downloads\104735474.json"
with open(replay_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

steps = data.get("steps", [])

scores_0 = []
scores_1 = []

for step_idx, step_data in enumerate(steps):
    scores_0.append(step_data[0].get('reward', 0))
    scores_1.append(step_data[1].get('reward', 0))

print("Scores at Day 10 (step 240):", scores_0[240], "vs", scores_1[240])
print("Scores at Day 20 (step 480):", scores_0[480], "vs", scores_1[480])
print("Scores at Day 30 (step 719):", scores_0[-1], "vs", scores_1[-1])

# Find when the difference started growing
diff = [scores_1[i] - scores_0[i] for i in range(len(scores_0))]
max_diff = max(diff)
min_diff = min(diff)
print(f"Max lead for Agent 1: {max_diff}")
print(f"Max lead for Agent 0: {-min_diff}")

# Print scores every 100 steps
for i in range(0, 720, 100):
    print(f"Step {i:3d}: A0 {scores_0[i]:.1f} | A1 {scores_1[i]:.1f}")
