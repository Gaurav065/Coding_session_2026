import os
import json
import glob
from collections import defaultdict
import csv

folders = [
    (r'C:\Users\GauravPatel\Downloads\lost_matches', 'lost_matches'),
    (r'C:\Users\GauravPatel\Downloads\lost_matches_20th_aug', 'lost_matches_20th_aug'),
    (r'C:\Users\GauravPatel\Downloads\lost_matches_21th_august_multi_route_agent_failiures', 'lost_matches_21_aug_failures'),
    (r'C:\Users\GauravPatel\Downloads\top_replays\p1', 'top_replays_p1'),
    (r'C:\Users\GauravPatel\Downloads\top_replays\p2', 'top_replays_p2'),
    (r'C:\Users\GauravPatel\Downloads\top_replays\p3', 'top_replays_p3'),
]

os.makedirs(r'C:\Coding\analysis', exist_ok=True)

all_matches = []

for folder_path, category in folders:
    json_files = glob.glob(os.path.join(folder_path, '*.json'))
    for file_path in json_files:
        match_id = os.path.splitext(os.path.basename(file_path))[0]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            continue

        steps = data.get('steps', [])
        if not steps:
            continue

        p0_final = steps[-1][0].get('reward', 0)
        p1_final = steps[-1][1].get('reward', 0)
        
        # Track statistics across steps
        match_record = {
            'match_id': match_id,
            'category': category,
            'p0_final_reward': p0_final,
            'p1_final_reward': p1_final,
            'winner': 0 if p0_final > p1_final else (1 if p1_final > p0_final else -1),
            'margin': abs(p0_final - p1_final),
            'shops_unlocked': [],
            'p0_quad_unlock_step': {},
            'p1_quad_unlock_step': {},
            'p0_crops_planted': defaultdict(int),
            'p1_crops_planted': defaultdict(int),
            'p0_animals_built': defaultdict(int),
            'p1_animals_built': defaultdict(int),
            'p0_action_counts': defaultdict(int),
            'p1_action_counts': defaultdict(int),
            'p0_sells': defaultdict(int),
            'p1_sells': defaultdict(int),
            'p0_fertilizer_collected': 0,
            'p1_fertilizer_collected': 0,
            'p0_hires_total': 0,
            'p1_hires_total': 0,
            'p0_max_hands_day': 0,
            'p1_max_hands_day': 0,
            'market_prices_end': {},
            'market_inventory_end': {},
            'p0_desync_detected': False,
            'p1_desync_detected': False,
        }

        prev_p0_quads = set(['NW'])
        prev_p1_quads = set(['NW'])
        
        for step_idx, step_pair in enumerate(steps):
            p0_step = step_pair[0]
            p1_step = step_pair[1]
            obs0 = p0_step.get('observation', {})
            act0 = p0_step.get('action', {}) or {}
            obs1 = p1_step.get('observation', {})
            act1 = p1_step.get('action', {}) or {}
            
            # Shops
            town_shops = obs0.get('town', {}).get('unlocked_shops', [])
            if len(town_shops) > len(match_record['shops_unlocked']):
                match_record['shops_unlocked'] = list(town_shops)

            # Farms state
            farms = obs0.get('farms', [])
            if len(farms) >= 2:
                # Quads
                p0_quads = set(farms[0].get('unlocked_quadrants', []))
                for q in p0_quads - prev_p0_quads:
                    match_record['p0_quad_unlock_step'][q] = step_idx
                prev_p0_quads = p0_quads

                p1_quads = set(farms[1].get('unlocked_quadrants', []))
                for q in p1_quads - prev_p1_quads:
                    match_record['p1_quad_unlock_step'][q] = step_idx
                prev_p1_quads = p1_quads

            # Actions P0
            p0_farmer_act = act0.get('farmer', [])
            p0_hands_act = act0.get('hands', [])
            p0_market_act = act0.get('market', [])

            p1_farmer_act = act1.get('farmer', [])
            p1_hands_act = act1.get('hands', [])
            p1_market_act = act1.get('market', [])

            # Count farmer & hands actions
            all_act0 = [p0_farmer_act] + (p0_hands_act if isinstance(p0_hands_act, list) else [])
            for a in all_act0:
                if isinstance(a, list) and len(a) > 0:
                    op = a[0]
                    match_record['p0_action_counts'][op] += 1
                    if op == 'PLANT' and len(a) > 1:
                        match_record['p0_crops_planted'][a[1]] += 1
                    elif op in ('BUILD_COOP', 'BUILD_PASTURE'):
                        match_record['p0_animals_built'][op] += 1
                    elif op == 'COLLECT_FERTILIZER':
                        match_record['p0_fertilizer_collected'] += 1

            all_act1 = [p1_farmer_act] + (p1_hands_act if isinstance(p1_hands_act, list) else [])
            for a in all_act1:
                if isinstance(a, list) and len(a) > 0:
                    op = a[0]
                    match_record['p1_action_counts'][op] += 1
                    if op == 'PLANT' and len(a) > 1:
                        match_record['p1_crops_planted'][a[1]] += 1
                    elif op in ('BUILD_COOP', 'BUILD_PASTURE'):
                        match_record['p1_animals_built'][op] += 1
                    elif op == 'COLLECT_FERTILIZER':
                        match_record['p1_fertilizer_collected'] += 1

            # Market orders
            for m in p0_market_act:
                if isinstance(m, list) and len(m) > 0:
                    op = m[0]
                    if op == 'SELL' and len(m) > 2:
                        prod = m[1]
                        qty = int(m[2]) if str(m[2]).isdigit() else 1
                        match_record['p0_sells'][prod] += qty
                    elif op == 'HIRE':
                        match_record['p0_hires_total'] += 1

            for m in p1_market_act:
                if isinstance(m, list) and len(m) > 0:
                    op = m[0]
                    if op == 'SELL' and len(m) > 2:
                        prod = m[1]
                        qty = int(m[2]) if str(m[2]).isdigit() else 1
                        match_record['p1_sells'][prod] += qty
                    elif op == 'HIRE':
                        match_record['p1_hires_total'] += 1

            # Check final step market prices
            if step_idx == len(steps) - 1:
                match_record['market_prices_end'] = obs0.get('market', {}).get('prices', {})
                match_record['market_inventory_end'] = obs0.get('market', {}).get('inventory', {})

        # Desync detection: if score < 35,000
        if p0_final < 35000:
            match_record['p0_desync_detected'] = True
        if p1_final < 35000:
            match_record['p1_desync_detected'] = True

        all_matches.append(match_record)

print(f"Successfully processed {len(all_matches)} matches.")

# Save detailed JSON
with open(r'C:\Coding\analysis\replays_detailed_dataset.json', 'w', encoding='utf-8') as f:
    json.dump(all_matches, f, indent=2)

# Save CSV summary
csv_file = r'C:\Coding\analysis\replays_summary.csv'
fieldnames = [
    'match_id', 'category', 'p0_final_reward', 'p1_final_reward', 'winner', 'margin',
    'p0_quads_unlocked', 'p1_quads_unlocked',
    'p0_wheat_planted', 'p0_carrot_planted', 'p0_tomato_planted', 'p0_strawberry_planted', 'p0_melon_planted',
    'p1_wheat_planted', 'p1_carrot_planted', 'p1_tomato_planted', 'p1_strawberry_planted', 'p1_melon_planted',
    'p0_fertilizer_collected', 'p1_fertilizer_collected',
    'p0_total_hires', 'p1_total_hires',
    'p0_wheat_sold', 'p0_carrot_sold', 'p0_tomato_sold', 'p0_strawberry_sold', 'p0_melon_sold',
    'p0_egg_sold', 'p0_milk_sold', 'p0_wool_sold', 'p0_fertilizer_sold',
    'p1_wheat_sold', 'p1_carrot_sold', 'p1_tomato_sold', 'p1_strawberry_sold', 'p1_melon_sold',
    'p1_egg_sold', 'p1_milk_sold', 'p1_wool_sold', 'p1_fertilizer_sold',
    'p0_desync', 'p1_desync', 'shops_unlocked_count', 'shops_list'
]

with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for m in all_matches:
        row = {
            'match_id': m['match_id'],
            'category': m['category'],
            'p0_final_reward': m['p0_final_reward'],
            'p1_final_reward': m['p1_final_reward'],
            'winner': m['winner'],
            'margin': m['margin'],
            'p0_quads_unlocked': len(m['p0_quad_unlock_step']) + 1,
            'p1_quads_unlocked': len(m['p1_quad_unlock_step']) + 1,
            'p0_wheat_planted': m['p0_crops_planted'].get('WHEAT', 0),
            'p0_carrot_planted': m['p0_crops_planted'].get('CARROT', 0),
            'p0_tomato_planted': m['p0_crops_planted'].get('TOMATO', 0),
            'p0_strawberry_planted': m['p0_crops_planted'].get('STRAWBERRY', 0),
            'p0_melon_planted': m['p0_crops_planted'].get('MELON', 0),
            'p1_wheat_planted': m['p1_crops_planted'].get('WHEAT', 0),
            'p1_carrot_planted': m['p1_crops_planted'].get('CARROT', 0),
            'p1_tomato_planted': m['p1_crops_planted'].get('TOMATO', 0),
            'p1_strawberry_planted': m['p1_crops_planted'].get('STRAWBERRY', 0),
            'p1_melon_planted': m['p1_crops_planted'].get('MELON', 0),
            'p0_fertilizer_collected': m['p0_fertilizer_collected'],
            'p1_fertilizer_collected': m['p1_fertilizer_collected'],
            'p0_total_hires': m['p0_hires_total'],
            'p1_total_hires': m['p1_hires_total'],
            'p0_wheat_sold': m['p0_sells'].get('WHEAT', 0),
            'p0_carrot_sold': m['p0_sells'].get('CARROT', 0),
            'p0_tomato_sold': m['p0_sells'].get('TOMATO', 0),
            'p0_strawberry_sold': m['p0_sells'].get('STRAWBERRY', 0),
            'p0_melon_sold': m['p0_sells'].get('MELON', 0),
            'p0_egg_sold': m['p0_sells'].get('EGG', 0),
            'p0_milk_sold': m['p0_sells'].get('MILK', 0),
            'p0_wool_sold': m['p0_sells'].get('WOOL', 0),
            'p0_fertilizer_sold': m['p0_sells'].get('FERTILIZER', 0),
            'p1_wheat_sold': m['p1_sells'].get('WHEAT', 0),
            'p1_carrot_sold': m['p1_sells'].get('CARROT', 0),
            'p1_tomato_sold': m['p1_sells'].get('TOMATO', 0),
            'p1_strawberry_sold': m['p1_sells'].get('STRAWBERRY', 0),
            'p1_melon_sold': m['p1_sells'].get('MELON', 0),
            'p1_egg_sold': m['p1_sells'].get('EGG', 0),
            'p1_milk_sold': m['p1_sells'].get('MILK', 0),
            'p1_wool_sold': m['p1_sells'].get('WOOL', 0),
            'p1_fertilizer_sold': m['p1_sells'].get('FERTILIZER', 0),
            'p0_desync': m['p0_desync_detected'],
            'p1_desync': m['p1_desync_detected'],
            'shops_unlocked_count': len(m['shops_unlocked']),
            'shops_list': '|'.join(m['shops_unlocked']),
        }
        writer.writerow(row)

print("CSV and JSON exports complete.")
