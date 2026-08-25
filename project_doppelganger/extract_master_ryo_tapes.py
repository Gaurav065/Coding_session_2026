import json
import glob
import os
from collections import Counter, defaultdict

replays_dir = r"C:\Users\GauravPatel\Downloads\top_player"
replay_files = glob.glob(os.path.join(replays_dir, "*.json"))

target_player = "Ryo Hasegawa"

route_replays = defaultdict(list)

for rf in replay_files:
    try:
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        info = data.get("info", {})
        team_names = info.get("TeamNames", ["", ""])
        if target_player not in team_names:
            continue
        
        seat = 0 if team_names[0] == target_player else 1
        steps = data.get("steps", [])
        if len(steps) < 720:
            continue
        
        last_step = steps[-1]
        reward = last_step[seat].get("reward", 0)
        
        # Check shops on day 3
        obs_72 = steps[72][0].get("observation", {})
        shops_d3 = obs_72.get("town", {}).get("unlocked_shops", [])
        is_yarn = len(shops_d3) >= 1 and shops_d3[0] == "YARN_STORE"
        
        route_name = "YARN_ROUTE" if is_yarn else "STANDARD_ROUTE"
        
        actions = [s[seat].get("action") or {"farmer": ["PASS"], "hands": [], "market": []} for s in steps]
        
        route_replays[route_name].append({
            "file": os.path.basename(rf),
            "seat": seat,
            "reward": reward,
            "actions": actions
        })
    except Exception as e:
        print(f"Error: {e}")

print(f"Standard Route Matches: {len(route_replays['STANDARD_ROUTE'])}")
print(f"Yarn Route Matches:     {len(route_replays['YARN_ROUTE'])}")

# Sort by reward descending to find the highest-scoring clean trajectories
route_replays['STANDARD_ROUTE'].sort(key=lambda x: x['reward'], reverse=True)
route_replays['YARN_ROUTE'].sort(key=lambda x: x['reward'], reverse=True)

print("\nTop 5 Standard Route Matches:")
for m in route_replays['STANDARD_ROUTE'][:5]:
    print(f"  {m['file']} | Seat {m['seat']} | Reward: ${m['reward']:,.0f}")

print("\nTop 5 Yarn Route Matches:")
for m in route_replays['YARN_ROUTE'][:5]:
    print(f"  {m['file']} | Seat {m['seat']} | Reward: ${m['reward']:,.0f}")

# For each route, extract the EXACT consensus actions from the top 10 matches
extracted_tapes = {}
for route_name, matches in route_replays.items():
    top_matches = matches[:15]
    print(f"\nExtracting high-fidelity consensus tape for {route_name} from top {len(top_matches)} matches...")
    
    clean_tape = []
    for step_idx in range(720):
        # Consensus farmer
        farmer_counts = Counter()
        for m in top_matches:
            f = m['actions'][step_idx].get('farmer', ['PASS'])
            farmer_counts[json.dumps(f)] += 1
        best_farmer = json.loads(farmer_counts.most_common(1)[0][0])
        
        # Max hands across top matches
        hands_counts = Counter()
        for m in top_matches:
            h_len = len(m['actions'][step_idx].get('hands', []))
            hands_counts[h_len] += 1
        best_hlen = hands_counts.most_common(1)[0][0]
        
        # Consensus per hand
        best_hands = []
        for hi in range(best_hlen):
            h_acts = Counter()
            for m in top_matches:
                hl = m['actions'][step_idx].get('hands', [])
                if hi < len(hl):
                    h_acts[json.dumps(hl[hi])] += 1
            if h_acts:
                best_hands.append(json.loads(h_acts.most_common(1)[0][0]))
            else:
                best_hands.append(['PASS'])
                
        # Consensus market orders
        # Include all orders that appear in at least 25% of top games
        order_counts = Counter()
        for m in top_matches:
            for o in m['actions'][step_idx].get('market', []):
                order_counts[json.dumps(o)] += 1
        
        best_market = []
        for o_str, cnt in order_counts.items():
            if cnt >= len(top_matches) * 0.25:
                best_market.append(json.loads(o_str))
                
        clean_tape.append({
            'farmer': best_farmer,
            'hands': best_hands,
            'market': best_market[:10]
        })
    
    extracted_tapes[route_name] = clean_tape
    
    # Save as JSON
    out_file = os.path.join(r"C:\Coding\project_doppelganger", f"ryo_{route_name.lower()}_master.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(clean_tape, f)
    print(f"Saved {out_file} (Length: {len(clean_tape)})")

print("\nExtraction complete!")
