import os
import json
import glob
from collections import Counter, defaultdict

replays_dir = r"C:\Users\GauravPatel\Downloads\top_player"
replay_files = glob.glob(os.path.join(replays_dir, "*.json"))

target_player = "Ryo Hasegawa"

print(f"Total replays found: {len(replay_files)}")

ryo_matches = []
route_signatures = defaultdict(list)

for rf in replay_files:
    try:
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        info = data.get("info", {})
        team_names = info.get("TeamNames", ["", ""])
        
        if target_player not in team_names:
            continue
        
        seat = 0 if team_names[0] == target_player else 1
        opp_seat = 1 - seat
        opp_name = team_names[opp_seat]
        
        steps = data.get("steps", [])
        if not steps or len(steps) < 720:
            continue
        
        last_step = steps[-1]
        ryo_reward = last_step[seat].get("reward", 0)
        opp_reward = last_step[opp_seat].get("reward", 0)
        
        # Extract Ryo's action sequence for all 720 turns
        ryo_actions = []
        for s in steps:
            # step[seat]['action'] is what Ryo submitted
            action = s[seat].get("action")
            if action is None:
                action = {"farmer": ["PASS"], "hands": [], "market": []}
            ryo_actions.append(action)
        
        # Town shop sequence (revealed on steps 72, 144, 216, 288, 360, 432, 504, 576)
        obs_144 = steps[144][0].get("observation", {})
        shops = obs_144.get("town", {}).get("unlocked_shops", [])
        shop_key = tuple(shops[:3])
        
        # Route key based on Day 0-6 behavior
        # Let's inspect Ryo's animal counts at turn 144 (Day 6)
        farm_144 = steps[144][seat].get("observation", {}).get("farms", [{}, {}])[seat]
        tiles_144 = farm_144.get("tiles", [])
        cows_144 = sum(1 for r in tiles_144 for t in r if isinstance(t, dict) and t.get("animal") == "COW")
        sheep_144 = sum(1 for r in tiles_144 for t in r if isinstance(t, dict) and t.get("animal") == "SHEEP")
        quads_144 = farm_144.get("unlocked_quadrants", [])
        
        route_sig = f"Cows_{cows_144}_Sheep_{sheep_144}_Quads_{len(quads_144)}"
        
        match_info = {
            "file": os.path.basename(rf),
            "seat": seat,
            "opp_name": opp_name,
            "ryo_reward": ryo_reward,
            "opp_reward": opp_reward,
            "win": ryo_reward > opp_reward,
            "margin": ryo_reward - opp_reward,
            "shop_key": shop_key,
            "route_sig": route_sig,
            "actions": ryo_actions
        }
        ryo_matches.append(match_info)
        route_signatures[route_sig].append(match_info)
        
    except Exception as e:
        print(f"Error processing {rf}: {e}")

print(f"\nSuccessfully extracted {len(ryo_matches)} matches of {target_player}!")

wins = sum(1 for m in ryo_matches if m["win"])
avg_score = sum(m["ryo_reward"] for m in ryo_matches) / len(ryo_matches) if ryo_matches else 0
peak_score = max(m["ryo_reward"] for m in ryo_matches) if ryo_matches else 0
avg_margin = sum(m["margin"] for m in ryo_matches) / len(ryo_matches) if ryo_matches else 0

print(f"=== {target_player.upper()} MACRO BENCHMARK ===")
print(f"  Total Games: {len(ryo_matches)}")
print(f"  Win Rate:    {wins/len(ryo_matches)*100:.1f}% ({wins}W - {len(ryo_matches)-wins}L)")
print(f"  Avg Score:   ${avg_score:,.1f}")
print(f"  Peak Score:  ${peak_score:,.1f}")
print(f"  Avg Margin:  +${avg_margin:,.1f}")

print("\n=== ROUTE DISTRIBUTION OF RYO HASEGAWA ===")
for r_sig, matches in route_signatures.items():
    r_wins = sum(1 for m in matches if m["win"])
    r_avg = sum(m["ryo_reward"] for m in matches) / len(matches)
    print(f"  Route: {r_sig:<25} | Games: {len(matches):2d} | Win Rate: {r_wins/len(matches)*100:5.1f}% | Avg Score: ${r_avg:>10,.1f}")

# Save extracted match dataset
summary_data = []
for m in ryo_matches:
    summary_data.append({
        "file": m["file"],
        "seat": m["seat"],
        "opp_name": m["opp_name"],
        "ryo_reward": m["ryo_reward"],
        "opp_reward": m["opp_reward"],
        "margin": m["margin"],
        "shop_key": m["shop_key"],
        "route_sig": m["route_sig"]
    })

os.makedirs(r"C:\Coding\project_doppelganger", exist_ok=True)
with open(r"C:\Coding\project_doppelganger\ryo_matches_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary_data, f, indent=2)

print("\nSaved summary to project_doppelganger/ryo_matches_summary.json")
