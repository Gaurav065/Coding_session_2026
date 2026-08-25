import json
import os
import time
from collections import defaultdict

base_downloads = r'C:\Users\GauravPatel\Downloads\aegis_latest'
now = time.time()

# Gather all files modified today (past 2 hours)
new_files = []
for root, dirs, files in os.walk(base_downloads):
    for f in files:
        if f.endswith('.json'):
            p = os.path.join(root, f)
            mtime = os.path.getmtime(p)
            if now - mtime < 7200: # past 2 hours
                new_files.append((p, f))

print("=" * 80)
print(f"AUDITING {len(new_files)} NEW REPLAYS DOWNLOADED TODAY")
print("=" * 80)

wins = []
losses = []

for p, f in sorted(new_files):
    with open(p, 'r', encoding='utf-8') as fp:
        data = json.load(fp)

    info = data.get('info', {})
    teams = info.get('TeamNames', ['P0', 'P1'])
    steps = data['steps']
    p0_final = steps[-1][0]['reward']
    p1_final = steps[-1][1]['reward']
    shops = steps[-1][0]['observation']['town']['unlocked_shops']

    my_seat = 1 if teams[1] == 'Shadow Recon' else 0
    opp_seat = 1 - my_seat
    my_score = p1_final if my_seat == 1 else p0_final
    opp_score = p0_final if my_seat == 1 else p1_final
    opp_name = teams[opp_seat]
    episode_id = info.get('EpisodeId') or f

    margin = my_score - opp_score
    is_win = my_score > opp_score
    rec = {
        'file': f,
        'path': p,
        'id': episode_id,
        'my_seat': my_seat,
        'my_score': my_score,
        'opp_score': opp_score,
        'opp_name': opp_name,
        'margin': margin,
        'shops': shops,
        'steps': steps
    }
    if is_win:
        wins.append(rec)
    else:
        losses.append(rec)

print(f"\nSummary: {len(wins)} WINS, {len(losses)} LOSSES")
print("\n--- LOSSES FORENSIC LIST ---")
for l in losses:
    print(f"  LOSS [{l['file']}]: Shadow ({l['my_score']:,.0f}) vs {l['opp_name']} ({l['opp_score']:,.0f}) | Margin: {l['margin']:,.0f} | Shops: {l['shops']}")

print("\n--- WINS SUMMARY ---")
for w in wins:
    print(f"  WIN  [{w['file']}]: Shadow ({w['my_score']:,.0f}) vs {w['opp_name']} ({w['opp_score']:,.0f}) | Margin: +{w['margin']:,.0f}")
