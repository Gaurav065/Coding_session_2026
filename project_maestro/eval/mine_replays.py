import os, json, glob

replay_files = glob.glob('replays/*.json') + glob.glob('project_maestro/replays/*.json')
print(f'Found {len(replay_files)} public match replays')

results = []
for rf in replay_files:
    try:
        with open(rf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        steps = data.get('steps', [])
        if not steps: continue
        final_p0 = steps[-1][0].get('reward', 0) or 0
        final_p1 = steps[-1][1].get('reward', 0) or 0
        last_obs = steps[-1][0].get('observation', {})
        town = last_obs.get('town', {})
        shops = town.get('unlocked_shops', [])
        prices = last_obs.get('market', {}).get('prices', {})
        winner_score = max(final_p0, final_p1)
        winner_idx = 0 if final_p0 >= final_p1 else 1
        results.append({
            'file': os.path.basename(rf),
            'p0': final_p0,
            'p1': final_p1,
            'winner_score': winner_score,
            'shops': shops,
            'final_prices': prices
        })
    except Exception as e:
        pass

print(f'Successfully parsed {len(results)} matches')
scores = [r['winner_score'] for r in results]
if scores:
    print(f'Winner Score Mean:  | Max:  | Min: ')
    # Shop frequency count
    shop_freq = {}
    for r in results:
        for s in r['shops']:
            shop_freq[s] = shop_freq.get(s, 0) + 1
    print('Historical Shop Spawn Distribution across parsed games:')
    for s, cnt in sorted(shop_freq.items(), key=lambda kv: -kv[1]):
        print(f'  {s:<20}: {cnt} appearances')

with open('project_maestro/data/mined_public_matches.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print('Saved mined matches to project_maestro/data/mined_public_matches.json')