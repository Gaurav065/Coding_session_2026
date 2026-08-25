import os
import json
import glob
from collections import Counter, defaultdict

replays_dir = r"C:\Users\GauravPatel\Downloads\top_player"
replay_files = glob.glob(os.path.join(replays_dir, "*.json"))

target_player = "Ryo Hasegawa"

route_matches = defaultdict(list)

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
        if not steps or len(steps) < 720:
            continue
        
        last_step = steps[-1]
        ryo_reward = last_step[seat].get("reward", 0)
        
        # Check animal counts at step 144
        farm_144 = steps[144][seat].get("observation", {}).get("farms", [{}, {}])[seat]
        tiles_144 = farm_144.get("tiles", [])
        cows_144 = sum(1 for r in tiles_144 for t in r if isinstance(t, dict) and t.get("animal") == "COW")
        sheep_144 = sum(1 for r in tiles_144 for t in r if isinstance(t, dict) and t.get("animal") == "SHEEP")
        quads_144 = farm_144.get("unlocked_quadrants", [])
        route_sig = f"Cows_{cows_144}_Sheep_{sheep_144}_Quads_{len(quads_144)}"
        
        obs_72 = steps[72][0].get("observation", {})
        shops_d3 = obs_72.get("town", {}).get("unlocked_shops", [])
        
        obs_144 = steps[144][0].get("observation", {})
        shops_d6 = obs_144.get("town", {}).get("unlocked_shops", [])
        
        # Extract actions
        actions = []
        for s in steps:
            act = s[seat].get("action")
            if act is None:
                act = {"farmer": ["PASS"], "hands": [], "market": []}
            actions.append(act)
            
        route_matches[route_sig].append({
            "file": os.path.basename(rf),
            "seat": seat,
            "reward": ryo_reward,
            "shops_d3": shops_d3,
            "shops_d6": shops_d6,
            "actions": actions
        })
    except Exception as e:
        print(f"Error: {e}")

print("=== ROUTE TRIGGER ANALYSIS FOR RYO HASEGAWA ===")
for r_sig, matches in route_matches.items():
    print(f"\n--- Route: {r_sig} (Count: {len(matches)}) ---")
    shop_patterns = Counter()
    for m in matches:
        s_tuple = tuple(m["shops_d6"])
        shop_patterns[s_tuple] += 1
    print("  Most common Day 6 Town Shops:")
    for s_pat, cnt in shop_patterns.most_common(5):
        print(f"    {cnt:2d} matches: {s_pat}")

# Build Consensus Tape for each route
consensus_tapes = {}
for r_sig, matches in route_matches.items():
    print(f"\nBuilding consensus tape for {r_sig} across {len(matches)} games...")
    consensus_actions = []
    
    for step in range(720):
        farmer_actions = Counter()
        hands_counts = Counter()
        market_actions = []
        
        for m in matches:
            act = m["actions"][step]
            farmer_str = json.dumps(act.get("farmer", ["PASS"]))
            farmer_actions[farmer_str] += 1
            hands_counts[len(act.get("hands", []))] += 1
        
        most_common_farmer = json.loads(farmer_actions.most_common(1)[0][0])
        most_common_hands_count = hands_counts.most_common(1)[0][0]
        
        # Find consensus hands
        hands_consensus = []
        for h_idx in range(most_common_hands_count):
            h_acts = Counter()
            for m in matches:
                h_list = m["actions"][step].get("hands", [])
                if h_idx < len(h_list):
                    h_acts[json.dumps(h_list[h_idx])] += 1
            if h_acts:
                hands_consensus.append(json.loads(h_acts.most_common(1)[0][0]))
            else:
                hands_consensus.append(["PASS"])
                
        # Find consensus market orders
        market_order_counts = Counter()
        for m in matches:
            m_list = m["actions"][step].get("market", [])
            for o in m_list:
                market_order_counts[json.dumps(o)] += 1
        
        # An order is in consensus if present in >= 50% of matches
        threshold = len(matches) * 0.4
        consensus_market = [json.loads(o_str) for o_str, cnt in market_order_counts.items() if cnt >= threshold]
        
        consensus_actions.append({
            "farmer": most_common_farmer,
            "hands": hands_consensus,
            "market": consensus_market
        })
        
    consensus_tapes[r_sig] = consensus_actions
    
    # Save consensus tape
    filename = f"ryo_consensus_{r_sig.lower()}.json"
    filepath = os.path.join(r"C:\Coding\project_doppelganger", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(consensus_actions, f)
    print(f"  Saved consensus tape to {filepath}")
