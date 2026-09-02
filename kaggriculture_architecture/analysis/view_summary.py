import os
import json

path = r'C:\Coding\kaggriculture_architecture\replay_summary.json'
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print('Total parsed replays:', len(data))
    for r in data[:20]:
        print(f"{r['file']:<25} | P0: {r['p0_reward']:>8.1f} ({r['p0_status']:<4}) vs P1: {r['p1_reward']:>8.1f} ({r['p1_status']:<4})")
    print("...")
    for r in data[-10:]:
        print(f"{r['file']:<25} | P0: {r['p0_reward']:>8.1f} ({r['p0_status']:<4}) vs P1: {r['p1_reward']:>8.1f} ({r['p1_status']:<4})")
else:
    print('Not found yet')
