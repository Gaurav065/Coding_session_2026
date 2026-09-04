import json
import os
import pandas as pd

df = pd.read_csv('trajectory_threads.csv')
df = df.sort_values('Final_Score', ascending=False)
df = df.drop_duplicates(subset=['Replay']) # Only take the winner of each replay

# Select top 25 replays to give us a huge diversity of routes
top_replays = df.head(25)

tapes = []

for idx, row in top_replays.iterrows():
    replay_file = os.path.join("our_replays", row['Replay'])
    p = row['Player']
    
    with open(replay_file, 'r', encoding='utf-8') as f:
        r = json.load(f)
        
    actions = []
    for step_num in range(len(r['steps'])):
        step_data = r['steps'][step_num]
        action = step_data[p].get('action')
        
        # If action is None (e.g. disconnected or missing), we insert a dummy
        if action is None:
            action = {"farmer": ["PASS"], "hands": [], "market": []}
            
        actions.append(action)
        
    tapes.append({
        "score": row['Final_Score'],
        "shops": row['Shops'].split(', '),
        "actions": actions
    })

print(f"Extracted {len(tapes)} God Tapes. Total size: ~{sum(len(t['actions']) for t in tapes)} steps.")

# Save to a highly compressed JSON format
with open("multi_route_tapes.json", "w") as f:
    json.dump(tapes, f)

print("Saved to multi_route_tapes.json")
