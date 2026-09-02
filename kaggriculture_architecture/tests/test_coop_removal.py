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

# Agent with BUILD_COOP suppressed to PASS
def agent_no_coop(obs, configuration=None):
    action = copy.deepcopy(e777_agent(obs, configuration))
    farmer = action.get("farmer", [])
    if farmer and len(farmer) > 0 and farmer[0] == "BUILD_COOP":
        action["farmer"] = ["PASS"]
    hands = action.get("hands", [])
    for i, h in enumerate(hands):
        if h and len(h) > 0 and h[0] == "BUILD_COOP":
            hands[i] = ["PASS"]
    action["hands"] = hands
    return action

# Agent with BUILD_COOP converted to BUILD_PASTURE
def agent_coop_to_pasture(obs, configuration=None):
    action = copy.deepcopy(e777_agent(obs, configuration))
    farmer = action.get("farmer", [])
    if farmer and len(farmer) > 0 and farmer[0] == "BUILD_COOP":
        action["farmer"] = ["BUILD_PASTURE"]
    hands = action.get("hands", [])
    for i, h in enumerate(hands):
        if h and len(h) > 0 and h[0] == "BUILD_COOP":
            hands[i] = ["BUILD_PASTURE"]
    action["hands"] = hands
    return action

print("="*75)
print("BENCHMARK: Default e777 vs e777 (No Coop / PASS) vs e777 (Coop -> Pasture)")
print("="*75)

for s in [42, 7, 1234, 555, 100, 202]:
    # 1. Match: Default e777 vs e777_no_coop (Seat 0: Default, Seat 1: No Coop)
    env1 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
    env1.run([e777_agent, agent_no_coop])
    r_def_0 = env1.steps[-1][0].reward
    r_nocoop_1 = env1.steps[-1][1].reward
    
    # Reverse seats (Seat 0: No Coop, Seat 1: Default)
    env2 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
    env2.run([agent_no_coop, e777_agent])
    r_nocoop_0 = env2.steps[-1][0].reward
    r_def_1 = env2.steps[-1][1].reward
    
    adv_nocoop = ((r_nocoop_0 - r_def_1) + (r_nocoop_1 - r_def_0)) / 2.0
    
    # 2. Match: Default e777 vs coop_to_pasture
    env3 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
    env3.run([e777_agent, agent_coop_to_pasture])
    r_def_p_0 = env3.steps[-1][0].reward
    r_past_1 = env3.steps[-1][1].reward
    
    env4 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
    env4.run([agent_coop_to_pasture, e777_agent])
    r_past_0 = env4.steps[-1][0].reward
    r_def_p_1 = env4.steps[-1][1].reward
    
    adv_pasture = ((r_past_0 - r_def_p_0) + (r_past_1 - r_def_p_1)) / 2.0
    
    print(f"Seed {s:<5} | Default: ${r_def_0:,.0f} | NoCoop Adv: {adv_nocoop:+,.1f} | Pasture Adv: {adv_pasture:+,.1f}")
