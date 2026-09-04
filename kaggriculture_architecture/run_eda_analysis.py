import pandas as pd
import numpy as np

df = pd.read_csv("eda_metrics.csv")

# Identify the top 5 replays based on Final Net Worth (Day 30)
day_30 = df[df['Day'] == 30]
top_5_replays = day_30.sort_values(by='Net_Worth', ascending=False).head(5)['Replay_ID'].tolist()

print("# EDA: Grandmaster Trajectory Analysis")
print("\n## 1. The Global Averages (All Replays)")
avg_trajectory = df.groupby('Day')[['Liquid_Cash', 'Net_Worth', 'Hands_Hired', 'Farm_Size']].mean().reset_index()
print(avg_trajectory.to_markdown(index=False))

print("\n## 2. The 'Top 5' Elite Trajectory")
top_df = df[df['Replay_ID'].isin(top_5_replays)]
elite_trajectory = top_df.groupby('Day')[['Liquid_Cash', 'Net_Worth', 'Hands_Hired', 'Farm_Size']].mean().reset_index()
print(elite_trajectory.to_markdown(index=False))

print("\n## 3. The 3-Day Delta (What do the Elite do differently?)")
# Compare Day 3
print("\n### Day 3 Snapshot")
print("Average Replays: Farm Size =", avg_trajectory.loc[1, 'Farm_Size'], "| Hands =", avg_trajectory.loc[1, 'Hands_Hired'])
print("Elite Replays:   Farm Size =", elite_trajectory.loc[1, 'Farm_Size'], "| Hands =", elite_trajectory.loc[1, 'Hands_Hired'])

# Compare Day 12
print("\n### Day 12 Snapshot")
print("Average Replays: Farm Size =", avg_trajectory.loc[4, 'Farm_Size'], "| Hands =", avg_trajectory.loc[4, 'Hands_Hired'])
print("Elite Replays:   Farm Size =", elite_trajectory.loc[4, 'Farm_Size'], "| Hands =", elite_trajectory.loc[4, 'Hands_Hired'])

print("\n## 4. Specific Action Trace of the #1 Replay")
best_replay = top_5_replays[0]
best_df = df[df['Replay_ID'] == best_replay]
print(best_df[['Day', 'Liquid_Cash', 'Hands_Hired', 'Farm_Size', 'Planted_Crops', 'Animals', 'Shed_Inventory']].to_markdown(index=False))
