import sys
import os
import ast
import json

# Ensure C:\Coding is at front of sys.path
sys.path.insert(0, r'C:\Coding')

print("=" * 80)
print("COMPREHENSIVE CODEBASE & FUNCTION CALL VERIFICATION")
print("=" * 80)

# 1. AST Syntax & Import Check on main.py
main_file = r'C:\Coding\main.py'
print(f"\n[1/4] Checking AST syntax and compilation of {main_file}...")
with open(main_file, 'r', encoding='utf-8') as f:
    source = f.read()

try:
    tree = ast.parse(source, filename='main.py')
    print("  -> AST parse: SUCCESS (Valid Python 3 Syntax, No Syntax Errors)")
except SyntaxError as e:
    print(f"  -> AST parse: FAILED ({e})")
    sys.exit(1)

func_names = [f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)]
class_names = [c.name for c in ast.walk(tree) if isinstance(c, ast.ClassDef)]

print(f"  -> Functions defined ({len(func_names)}): {func_names[:10]}...")
print(f"  -> Classes defined ({len(class_names)}): {class_names}")

required_classes = ['PureDebtManager', 'OpponentShedEstimator', 'PredatorEngine', 'LiquidityGuard', 'RiverEngine', 'OpportunisticCropManager', 'AegisAgentState']
for rc in required_classes:
    assert rc in class_names, f"Missing class: {rc}"
print("  -> All core architectural classes verified present: PASS")

# 2. Direct Import and Function Verification
print("\n[2/4] Verifying Function Calls and Module Integration...")
import main as aegis_agent

assert hasattr(aegis_agent, 'agent'), "Missing agent(obs) entry point"
assert hasattr(aegis_agent, 'calculate_single_unit_price'), "Missing calculate_single_unit_price"
assert hasattr(aegis_agent, 'prioritize_and_dispatch_market'), "Missing prioritize_and_dispatch_market"
assert hasattr(aegis_agent, 'feed_rescue_guard'), "Missing feed_rescue_guard"
assert hasattr(aegis_agent, 'weed_repair_overlay'), "Missing weed_repair_overlay"
assert hasattr(aegis_agent, 'scavenger_farmhand_overlay'), "Missing scavenger_farmhand_overlay"

print("  -> All top-level function hooks verified callable: PASS")

# 3. Micro-Plot Scarcity Trigger Validation
print("\n[3/4] Validating Predictive Scarcity Trigger Logic...")
crop_mgr = aegis_agent.OpportunisticCropManager()

# Tomato test: 2 Pizza shops on Day 12
obs_tomato = {
    'day': 12,
    'player': 0,
    'farms': [{'money': 2000.0}],
    'town': {'unlocked_shops': ['PIZZA_SHOP', 'PIZZA_SHOP']},
    'market': {'prices': {'TOMATO': 70}}
}
t_res = crop_mgr.detect_scarcity_opportunity(obs_tomato)
print(f"  -> 2 Pizza Shops on Day 12 Trigger: {t_res} (Expected: TOMATO)")
assert t_res == "TOMATO", "Failed Tomato predictive trigger"

# Carrot test: 2 Pet Cafes on Day 6
obs_carrot = {
    'day': 6,
    'player': 0,
    'farms': [{'money': 2000.0}],
    'town': {'unlocked_shops': ['PET_CAFE', 'PET_CAFE']},
    'market': {'prices': {'CARROT': 35}}
}
c_res = crop_mgr.detect_scarcity_opportunity(obs_carrot)
print(f"  -> 2 Pet Cafes on Day 06 Trigger:   {c_res} (Expected: CARROT)")
assert c_res == "CARROT", "Failed Carrot predictive trigger"

# 4. Multi-Seed Simulation Benchmark against Starter
print("\n[4/4] Running 720-Step Full Game Simulations (5 Seeds)...")
from kaggle_environments import make

seeds = [1, 7, 13, 24, 42]
scores = []
margins = []

for seed in seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env.run([aegis_agent.agent, "starter"])
    steps = env.steps
    p0 = steps[-1][0]['reward']
    p1 = steps[-1][1]['reward']
    status = steps[-1][0]['status']
    margin = p0 - p1
    scores.append(p0)
    margins.append(margin)
    print(f"  Seed {seed:02d}: Aegis = {p0:>8,.0f} | Starter = {p1:>5,.0f} | Margin = {margin:>+8,.0f} | Status = {status}")
    assert status == "DONE", f"Game failed with status: {status}"

print("\n" + "=" * 80)
print(f"VERIFICATION SUMMARY: ALL CHECKS PASSED (100% GREEN)")
print(f"Average Score vs Starter: ${sum(scores)/len(scores):,.0f}")
print(f"Peak Score:               ${max(scores):,.0f}")
print(f"Average Victory Margin:   +${sum(margins)/len(margins):,.0f}")
print("=" * 80)
