import sys
import copy
import os
import importlib.util
from pathlib import Path
from kaggle_environments import make

root = Path(r'C:\Coding\kaggriculture_architecture\extracted_notebook_agent')
policy_path = root / "agents" / "e777a_apex_preemption.py"

if str(root / "agents") not in sys.path:
    sys.path.insert(0, str(root / "agents"))
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

spec = importlib.util.spec_from_file_location("e777_pol", str(policy_path))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
e777_agent = mod.agent

def _tile_at(farm, pos):
    if not pos:
        return None
    x, y = pos
    tiles = farm.get("tiles", [])
    if 0 <= y < len(tiles):
        row = tiles[y]
        if 0 <= x < len(row):
            return row[x]
    return None

# Agent with In-Place Opportunistic Yield (Harvest / Collect Fertilizer when PASS)
def agent_opportunistic(obs, configuration=None):
    action = copy.deepcopy(e777_agent(obs, configuration))
    seat = obs.get("player", 0)
    farms = obs.get("farms", [])
    if seat >= len(farms):
        return action
    farm = farms[seat]
    farmer_pos = farm.get("farmer")
    hands = farm.get("hands", [])
    
    # 1. Check farmer
    farmer_cmd = action.get("farmer", ["PASS"])
    if farmer_cmd == ["PASS"] and farmer_pos:
        tile = _tile_at(farm, farmer_pos)
        if isinstance(tile, dict):
            crop = tile.get("crop")
            # If crop is mature/ready, harvest
            if isinstance(crop, dict) and crop.get("stage") == crop.get("max_stage", 4):
                action["farmer"] = ["HARVEST"]
    
    # 2. Check hands
    hand_cmds = list(action.get("hands", []))
    for i, hpos in enumerate(hands):
        if i < len(hand_cmds) and hand_cmds[i] == ["PASS"] and hpos:
            tile = _tile_at(farm, hpos)
            if isinstance(tile, dict):
                crop = tile.get("crop")
                if isinstance(crop, dict) and crop.get("stage") == crop.get("max_stage", 4):
                    hand_cmds[i] = ["HARVEST"]
                elif tile.get("kind") == "PASTURE" and tile.get("fertilizer", 0) > 0:
                    hand_cmds[i] = ["COLLECT_FERTILIZER"]
                    
    action["hands"] = hand_cmds
    return action

print("="*75)
print("BENCHMARK: Baseline God Mode v3 (e777) vs Opportunistic In-Place Harvest (e778)")
print("="*75)

total_adv = 0
for s in [42, 7, 1234, 555, 100, 202]:
    # Match 1: P0=e777, P1=e778
    env1 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
    env1.run([e777_agent, agent_opportunistic])
    r_base_0 = env1.steps[-1][0].reward
    r_opp_1 = env1.steps[-1][1].reward
    
    # Match 2: P0=e778, P1=e777
    env2 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
    env2.run([agent_opportunistic, e777_agent])
    r_opp_0 = env2.steps[-1][0].reward
    r_base_1 = env2.steps[-1][1].reward
    
    adv = ((r_opp_0 - r_base_1) + (r_opp_1 - r_base_0)) / 2.0
    total_adv += adv
    
    p0_diff = r_opp_0 - r_base_1
    p1_diff = r_opp_1 - r_base_0
    print(f"Seed {s:<5} | Base: ${r_base_0:,.0f} vs Opp: ${r_opp_1:,.0f} | P0 Diff: {p0_diff:+,.1f} | P1 Diff: {p1_diff:+,.1f} | Net Adv: {adv:+,.1f}")

print(f"\nOverall Average Advantage across 6 Seeds: {total_adv / 6.0:+,.1f}")
