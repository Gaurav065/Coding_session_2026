import os
import json
import glob
from collections import defaultdict
import numpy as np

def run_deep_research():
    replay_files = glob.glob('replays/*.json') + glob.glob('project_maestro/replays/*.json')
    print(f'Deep mining {len(replay_files)} public replays...')

    players_data = []

    for rf in replay_files:
        try:
            with open(rf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            steps = data.get('steps', [])
            if len(steps) < 10:
                continue

            match_id = os.path.basename(rf).replace('.json', '')
            final_p0_score = steps[-1][0].get('reward', 0) or 0
            final_p1_score = steps[-1][1].get('reward', 0) or 0

            last_obs = steps[-1][0].get('observation', {})
            town_shops = last_obs.get('town', {}).get('unlocked_shops', [])

            for p_idx in [0, 1]:
                score = final_p0_score if p_idx == 0 else final_p1_score
                opp_score = final_p1_score if p_idx == 0 else final_p0_score
                is_winner = score > opp_score

                actions_taken = defaultdict(int)
                market_orders = defaultdict(int)
                land_unlock_steps = {}
                max_hands = 0
                crops_planted = defaultdict(int)
                animals_placed = defaultdict(int)
                structures_built = defaultdict(int)

                for step_idx, step_entry in enumerate(steps):
                    p_state = step_entry[p_idx]
                    act = p_state.get('action', {})
                    if not isinstance(act, dict):
                        continue

                    farmer_act = act.get('farmer', [])
                    if farmer_act:
                        op = farmer_act[0]
                        actions_taken[op] += 1
                        if op == 'PLANT' and len(farmer_act) > 1:
                            crops_planted[farmer_act[1]] += 1
                        elif op in ('BUILD_PASTURE', 'BUILD_COOP'):
                            structures_built[op] += 1
                        elif op == 'PLACE' and len(farmer_act) > 1 and farmer_act[1] in ('COW', 'SHEEP', 'GOOSE'):
                            animals_placed[farmer_act[1]] += 1

                    for h_act in act.get('hands', []):
                        if not h_act:
                            continue
                        hop = h_act[0]
                        actions_taken[hop] += 1
                        if hop == 'PLANT' and len(h_act) > 1:
                            crops_planted[h_act[1]] += 1
                        elif hop in ('BUILD_PASTURE', 'BUILD_COOP'):
                            structures_built[hop] += 1
                        elif hop == 'PLACE' and len(h_act) > 1 and hop[1] in ('COW', 'SHEEP', 'GOOSE'):
                            animals_placed[h_act[1]] += 1

                    for m_ord in act.get('market', []):
                        if not m_ord:
                            continue
                        mop = m_ord[0]
                        if mop == 'BUY_LAND':
                            quad_idx = len(land_unlock_steps) + 1
                            land_unlock_steps[f'QUAD_{quad_idx}'] = step_idx
                        elif mop == 'BUY_ANIMAL' and len(m_ord) > 1:
                            market_orders[f'BUY_{m_ord[1]}'] += (m_ord[2] if len(m_ord) > 2 else 1)
                        elif mop == 'BUY_SEED' and len(m_ord) > 1:
                            market_orders[f'BUY_SEED_{m_ord[1]}'] += (m_ord[2] if len(m_ord) > 2 else 1)
                        elif mop == 'SELL' and len(m_ord) > 1:
                            market_orders[f'SELL_{m_ord[1]}'] += (m_ord[2] if len(m_ord) > 2 else 1)
                        elif mop == 'HIRE':
                            market_orders['HIRE'] += 1

                    obs_farm = step_entry[p_idx].get('observation', {}).get('farms', [])
                    if obs_farm and len(obs_farm) > p_idx:
                        h_cnt = len(obs_farm[p_idx].get('hands', []))
                        max_hands = max(max_hands, h_cnt)

                cows = market_orders.get('BUY_COW', 0)
                sheep = market_orders.get('BUY_SHEEP', 0)
                geese = market_orders.get('BUY_GOOSE', 0)
                berries = crops_planted.get('STRAWBERRY', 0)
                melons = crops_planted.get('MELON', 0)
                wheat = crops_planted.get('WHEAT', 0)
                carrots = crops_planted.get('CARROT', 0)
                tomatoes = crops_planted.get('TOMATO', 0)

                if sheep >= 9 and cows <= 3:
                    archetype = 'Ahmad_Ali_Sheep_Rush'
                elif cows >= 8 and sheep <= 4:
                    archetype = 'Dominant_Dairy_Meta'
                elif cows >= 5 and sheep >= 5:
                    archetype = 'Balanced_Livestock_Hybrid'
                elif berries >= 25 and (cows + sheep) <= 8:
                    archetype = 'Strawberry_Crop_Engine'
                elif cows == 0 and sheep == 0 and geese == 0:
                    archetype = 'Pure_Crop_No_Animals'
                elif geese >= 3:
                    archetype = 'Goose_Egg_Experiment'
                else:
                    archetype = 'Diversified_Mixed_Farm'

                players_data.append({
                    'match_id': match_id,
                    'player_idx': p_idx,
                    'score': score,
                    'is_winner': is_winner,
                    'archetype': archetype,
                    'cows_bought': cows,
                    'sheep_bought': sheep,
                    'geese_bought': geese,
                    'strawberries_planted': berries,
                    'melons_planted': melons,
                    'wheat_planted': wheat,
                    'carrots_planted': carrots,
                    'tomatoes_planted': tomatoes,
                    'max_hands': max_hands,
                    'total_hires': market_orders.get('HIRE', 0),
                    'land_unlocks': land_unlock_steps,
                    'total_sales': {k.replace('SELL_', ''): v for k, v in market_orders.items() if k.startswith('SELL_')},
                    'town_shops': town_shops
                })
        except Exception as e:
            print(f'Error reading {rf}: {e}')

    print(f'Extracted full behavioral profiles for {len(players_data)} player-games!\n')

    arch_groups = defaultdict(list)
    for p in players_data:
        arch_groups[p['archetype']].append(p)

    print('=' * 105)
    print(f'{"Pathway Archetype":<30} | {"Count":<5} | {"WinRate":<8} | {"Mean Score":<12} | {"Median":<10} | {"Min":<8} | {"Max":<8}')
    print('-' * 105)
    for arch, plist in sorted(arch_groups.items(), key=lambda kv: -np.mean([x['score'] for x in kv[1]])):
        scores = [x['score'] for x in plist]
        wins = [x['is_winner'] for x in plist]
        wr = sum(wins) / len(wins) * 100
        mean_s = np.mean(scores)
        med_s = np.median(scores)
        min_s = np.min(scores)
        max_s = np.max(scores)
        print(f'{arch:<30} | {len(plist):<5} | {wr:6.1f}%  | ${mean_s:10.1f} | ${med_s:8.1f} | ${min_s:6.0f} | ${max_s:6.0f}')
    print('=' * 105)

    out_path = 'project_maestro/data/public_replay_archetypes_research.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'summary_by_archetype': {
                a: {
                    'count': len(l),
                    'mean_score': float(np.mean([x['score'] for x in l])),
                    'median_score': float(np.median([x['score'] for x in l])),
                    'min_score': float(np.min([x['score'] for x in l])),
                    'max_score': float(np.max([x['score'] for x in l])),
                    'win_rate': float(sum(x['is_winner'] for x in l) / len(l))
                } for a, l in arch_groups.items()
            },
            'players': players_data
        }, f, indent=2)
    print(f'\nDetailed research dataset saved to {out_path}')

if __name__ == '__main__':
    run_deep_research()
