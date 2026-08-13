import json
import glob
from collections import defaultdict

files = glob.glob('replays/*.json')

for fpath in files[:2]:
    with open(fpath, 'r') as f:
        data = json.load(f)
    
    steps = data.get('steps', [])
    if not steps: continue
    final_step = steps[-1]
    scores = [final_step[i].get('reward', 0) for i in range(2)]
    winner = 0 if scores[0] > scores[1] else 1
    
    actions = defaultdict(int)
    
    for step_idx, step in enumerate(steps):
        if step_idx == 0: continue
        action = step[winner].get('action', {})
        farmer_cmd = action.get('farmer', [])
        hands_cmds = action.get('hands', [])
        
        if farmer_cmd:
            actions[farmer_cmd[0]] += 1
            
        for h_cmd in hands_cmds:
            if h_cmd:
                actions[h_cmd[0]] += 1

    print(f"\nReplay {fpath} | Winner {winner} | Score {scores[winner]}")
    print(f"  Actions: {dict(actions)}")
