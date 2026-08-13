import json
import glob
import os
from collections import defaultdict

files = glob.glob('replays/*.json')

for fpath in files:
    with open(fpath, 'r') as f:
        data = json.load(f)
    
    steps = data.get('steps', [])
    if not steps: continue
    final_step = steps[-1]
    scores = [final_step[i].get('reward', 0) for i in range(2)]
    winner = 0 if scores[0] > scores[1] else 1
    
    buys = defaultdict(int)
    sells = defaultdict(int)
    seeds = defaultdict(int)
    animals = defaultdict(int)
    hands = 0
    
    for step_idx, step in enumerate(steps):
        if step_idx == 0: continue
        action = step[winner].get('action', {})
        market = action.get('market', [])
        
        for cmd in market:
            op = cmd[0]
            if op == 'BUY_PRODUCT':
                buys[cmd[1]] += cmd[2]
            elif op == 'SELL':
                sells[cmd[1]] += cmd[2]
            elif op == 'BUY_SEED':
                seeds[cmd[1]] += cmd[2]
            elif op == 'BUY_ANIMAL':
                animals[cmd[1]] += cmd[2]
            elif op == 'HIRE':
                hands += 1

    print(f"\nReplay {os.path.basename(fpath)} | Winner {winner} | Score: {scores[winner]}")
    print(f"  Hands Hired: {hands}")
    print(f"  Animals Bought: {dict(animals)}")
    print(f"  Seeds Bought: {dict(seeds)}")
    print(f"  Products Bought: {dict(buys)}")
    print(f"  Products Sold: {dict(sells)}")

