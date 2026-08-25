import sys
import os
import copy
from collections import defaultdict

sys.path.insert(0, r'C:\Coding')

import main as aegis_agent
from project_aegis.benchmarks.synthetic_multiwave_opponent import synthetic_multiwave_opponent
from kaggle_environments import make

print("=" * 80)
print("VERIFYING ADDITIVE AUXILIARY HIRE & LIVE EXECUTION (DAYS 10-27)")
print("=" * 80)

# Run 1 detailed game with instrumentation
aux_hires_issued = 0
unscripted_hand_opportunities = 0
scavenger_actions = defaultdict(int)
harvested_melons_by_day = defaultdict(int)

orig_core_step = aegis_agent._aegis_core_step

def instrumented_step(obs):
    global aux_hires_issued, unscripted_hand_opportunities
    step = obs.get("step", 0)
    day = obs.get("day", 0)
    hour = obs.get("hour", 0)
    player = obs.get("player", 0)
    farm = obs.get("farms", [{}, {}])[player]
    live_hands = farm.get("hands", []) or []
    
    act = orig_core_step(obs)
    
    tape_hands = act.get("hands", []) or []
    
    # Check if 6th hire was queued at hour 0
    if hour == 0 and 10 <= day <= 26:
        market = act.get("market", []) or []
        hire_count = sum(1 for o in market if isinstance(o, list) and len(o) > 0 and o[0] == "HIRE")
        if hire_count >= 6:
            aux_hires_issued += 1
            
    # Check if unscripted hand exists
    active_tape = aegis_agent.select_active_tape(obs)
    raw_tape_hands = active_tape[step].get('hands', []) if step < len(active_tape) else []
    if len(raw_tape_hands) < len(live_hands):
        unscripted_hand_opportunities += (len(live_hands) - len(raw_tape_hands))
        for h_idx in range(len(raw_tape_hands), len(tape_hands)):
            h_act = tape_hands[h_idx][0] if len(tape_hands[h_idx]) > 0 else 'PASS'
            scavenger_actions[h_act] += 1
            if h_act == "HARVEST":
                harvested_melons_by_day[day] += 1
                
    return act

aegis_agent._aegis_core_step = instrumented_step

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 11}, debug=True)
env.run([aegis_agent.agent, synthetic_multiwave_opponent])

print(f"Game Trace (Seed 11):")
print(f"  Auxiliary Hires Issued:         {aux_hires_issued} days")
print(f"  Unscripted Hand Opportunities:  {unscripted_hand_opportunities} turns")
print(f"  Scavenger Hand Actions Executed:{dict(scavenger_actions)}")
print(f"  Harvest Actions by Day:         {dict(harvested_melons_by_day)}")
print(f"  Final Score: Aegis = ${env.steps[-1][0]['reward']:,.0f} | Opponent = ${env.steps[-1][1]['reward']:,.0f}")
print("=" * 80)
