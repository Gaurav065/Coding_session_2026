import os
import json
import glob
from collections import defaultdict
import numpy as np

def analyze_top_tier_episodes():
    files = glob.glob('kaggle_top_tier_data/*.json')
    print(f'Found {len(files)} top-tier match replays in kaggle_top_tier_data/')

    records = []
    skipped = 0

    for idx, fpath in enumerate(files):
        if os.path.getsize(fpath) < 10000:
            skipped += 1
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            steps = data.get('steps', [])
            if len(steps) < 10:
                continue

            ep_id = os.path.basename(fpath).replace('.json', '')
            final_step = steps[-1]
            s0 = final_step[0].get('reward', 0) or 0
            s1 = final_step[1].get('reward', 0) or 0

            info = data.get('info', {})
            agents = data.get('agents', [])

            # Extract shop draws
            last_obs = final_step[0].get('observation', {})
            town_shops = last_obs.get('town', {}).get('unlocked_shops', [])

            for p_idx in [0, 1]:
                score = s0 if p_idx == 0 else s1
                opp_score = s1 if p_idx == 0 else s0
                is_win = score > opp_score

                # Count actions and market orders
                market_orders = defaultdict(int)
                crops_planted = defaultdict(int)
                land_unlocks = {}
                max_hands = 0

                for step_idx, st in enumerate(steps):
                    p_state = st[p_idx]
                    act = p_state.get('action', {})
                    if not isinstance(act, dict):
                        continue

                    # Farmer op
                    farmer_act = act.get('farmer', [])
                    if farmer_act and farmer_act[0] == 'PLANT' and len(farmer_act) > 1:
                        crops_planted[farmer_act[1]] += 1

                    # Hands ops
                    for ha in act.get('hands', []):
                        if ha and ha[0] == 'PLANT' and len(ha) > 1:
                            crops_planted[ha[1]] += 1

                    # Market ops
                    for mo in act.get('market', []):
                        if not mo:
                            continue
                        mop = mo[0]
                        if mop == 'BUY_LAND':
                            land_unlocks[f'QUAD_{len(land_unlocks)+1}'] = step_idx
                        elif mop == 'BUY_ANIMAL' and len(mo) > 1:
                            market_orders[f'BUY_{mo[1]}'] += (mo[2] if len(mo) > 2 else 1)
                        elif mop == 'BUY_SEED' and len(mo) > 1:
                            market_orders[f'BUY_SEED_{mo[1]}'] += (mo[2] if len(mo) > 2 else 1)
                        elif mop == 'SELL' and len(mo) > 1:
                            market_orders[f'SELL_{mo[1]}'] += (mo[2] if len(mo) > 2 else 1)
                        elif mop == 'HIRE':
                            market_orders['HIRE'] += 1

                    obs_farm = st[p_idx].get('observation', {}).get('farms', [])
                    if obs_farm and len(obs_farm) > p_idx:
                        max_hands = max(max_hands, len(obs_farm[p_idx].get('hands', [])))

                cows = market_orders.get('BUY_COW', 0)
                sheep = market_orders.get('BUY_SHEEP', 0)
                geese = market_orders.get('BUY_GOOSE', 0)
                berries = crops_planted.get('STRAWBERRY', 0)
                melons = crops_planted.get('MELON', 0)
                wheat = crops_planted.get('WHEAT', 0)
                carrots = crops_planted.get('CARROT', 0)
                tomatoes = crops_planted.get('TOMATO', 0)

                records.append({
                    'episode_id': ep_id,
                    'player_idx': p_idx,
                    'score': score,
                    'opp_score': opp_score,
                    'is_win': is_win,
                    'cows': cows,
                    'sheep': sheep,
                    'geese': geese,
                    'strawberries': berries,
                    'melons': melons,
                    'wheat': wheat,
                    'carrots': carrots,
                    'tomatoes': tomatoes,
                    'max_hands': max_hands,
                    'total_hires': market_orders.get('HIRE', 0),
                    'land_unlocks': land_unlocks,
                    'sales': {k.replace('SELL_', ''): v for k, v in market_orders.items() if k.startswith('SELL_')},
                    'shops': town_shops
                })

            if idx % 100 == 0:
                print(f'Processed {idx}/{len(files)} replays...')
        except Exception as e:
            continue

    print(f'Successfully parsed {len(records)} player-episodes (skipped {skipped} empty files).\n')

    # Top-Tier Winner vs Mid-Tier Winner Analysis
    # Filter for high-scoring elite games (Score >= $80,000)
    elite_players = [r for r in records if r['score'] >= 80000]
    all_winners = [r for r in records if r['is_win']]

    print('=' * 95)
    print(f'GRANDMASTER TIER BENCHMARK (Games with Score >= $80,000 | N={len(elite_players)})')
    print('=' * 95)
    print(f'Average Score          : ${np.mean([r["score"] for r in elite_players]):,.2f} (Max: ${max(r["score"] for r in elite_players):,.2f})')
    print(f'Average Cows Bought    : {np.mean([r["cows"] for r in elite_players]):.2f} (Median: {np.median([r["cows"] for r in elite_players]):.0f})')
    print(f'Average Sheep Bought   : {np.mean([r["sheep"] for r in elite_players]):.2f} (Median: {np.median([r["sheep"] for r in elite_players]):.0f})')
    print(f'Average Geese Bought   : {np.mean([r["geese"] for r in elite_players]):.2f}')
    print(f'Average Strawberries   : {np.mean([r["strawberries"] for r in elite_players]):.2f} (Median: {np.median([r["strawberries"] for r in elite_players]):.0f})')
    print(f'Average Melons Planted : {np.mean([r["melons"] for r in elite_players]):.2f}')
    print(f'Average Wheat Planted  : {np.mean([r["wheat"] for r in elite_players]):.2f}')
    print(f'Average Max Crew Size  : {np.mean([r["max_hands"] for r in elite_players]):.2f} hands')
    print(f'Average Total Hires    : {np.mean([r["total_hires"] for r in elite_players]):.2f}')

    # Cluster Top 10% Winning Strategies
    print('\n' + '=' * 95)
    print('TOP 5 WINNING STRATEGY CLUSTERS IN OFFICIAL KAGGLE DATASET:')
    print('=' * 95)

    def cluster_player(r):
        c, s, g, b = r['cows'], r['sheep'], r['geese'], r['strawberries']
        if s >= 9 and c <= 3:
            return 'Pure_Sheep_Rush (9-14 Sheep)'
        elif c >= 7 and s <= 4 and b >= 15:
            return 'Dairy_Plus_Strawberry_Engine (7-11 Cows, 15+ Straw)'
        elif c >= 7 and s <= 4 and b < 15:
            return 'Pure_Dairy_Heavy (8-12 Cows, low crops)'
        elif c >= 5 and s >= 5:
            return 'Balanced_Pasture_Hybrid (5-8 Cows, 5-8 Sheep)'
        elif b >= 25 and (c + s) <= 6:
            return 'Strawberry_Crop_Dominant (25+ Strawberries)'
        else:
            return 'Mixed_Generalist'

    clusters = defaultdict(list)
    for r in all_winners:
        clusters[cluster_player(r)].append(r)

    print(f'{"Cluster Name":<40} | {"Win Count":<9} | {"Mean Score":<12} | {"Median":<10} | {"Max Peak":<10}')
    print('-' * 95)
    for cname, clist in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        sc = [x['score'] for x in clist]
        print(f'{cname:<40} | {len(clist):<9} | ${np.mean(sc):10.1f} | ${np.median(sc):8.1f} | ${max(sc):8.0f}')

    out_file = 'project_maestro/data/top_tier_kaggle_dataset_analysis.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_episodes': len(records) // 2,
            'elite_players_count': len(elite_players),
            'clusters': {
                cn: {
                    'count': len(cl),
                    'mean_score': float(np.mean([x['score'] for x in cl])),
                    'median_score': float(np.median([x['score'] for x in cl])),
                    'max_score': float(max(x['score'] for x in cl))
                } for cn, cl in clusters.items()
            }
        }, f, indent=2)
    print(f'\nComplete top-tier dataset analysis saved to {out_file}')

if __name__ == '__main__':
    analyze_top_tier_episodes()
