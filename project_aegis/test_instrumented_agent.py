import sys
import os
sys.path.insert(0, r'C:\Coding')

import main as aegis_agent
from kaggle_environments import make

print("=" * 80)
print("INSTRUMENTED RUN OF REBUILT MAIN.PY ACROSS 5 SEEDS")
print("=" * 80)

# Global counters for instrumentation
instrumentation = {
    'total_steps': 0,
    'auxiliary_hires_queued': 0,
    'unscripted_hand_opportunities': 0,
    'scavenger_actions': {'DIG': 0, 'COLLECT_FERTILIZER': 0, 'PLANT': 0, 'WATER': 0, 'HARVEST': 0, 'MOVE': 0, 'PASS': 0},
    'feed_rescue_fired': 0,
    'frontrun_fired': 0,
    'terminal_liquidation_orders': 0
}

# Wrap agent with instrumentation hooks
orig_core_step = aegis_agent._aegis_core_step

def instrumented_core_step(obs):
    instrumentation['total_steps'] += 1
    step = obs.get('step', 0)
    farm = obs.get('farms', [{}, {}])[obs.get('player', 0)]
    live_hands = farm.get('hands', []) or []
    
    act = orig_core_step(obs)
    
    tape_hands = act.get('hands', []) or []
    
    # Check if HIRE was queued
    for m in act.get('market', []) or []:
        if isinstance(m, list) and len(m) > 0 and m[0] == 'HIRE':
            if obs.get('hour', 0) == 0:
                instrumentation['auxiliary_hires_queued'] += 1
                
    # Check unscripted hands
    active_tape = aegis_agent.select_active_tape(obs)
    raw_tape_hands = active_tape[step].get('hands', []) if step < len(active_tape) else []
    if len(raw_tape_hands) < len(live_hands):
        instrumentation['unscripted_hand_opportunities'] += (len(live_hands) - len(raw_tape_hands))
        for h_idx in range(len(raw_tape_hands), len(tape_hands)):
            h_act = tape_hands[h_idx][0] if len(tape_hands[h_idx]) > 0 else 'PASS'
            if h_act in ('NORTH', 'SOUTH', 'EAST', 'WEST'):
                instrumentation['scavenger_actions']['MOVE'] += 1
            elif h_act in instrumentation['scavenger_actions']:
                instrumentation['scavenger_actions'][h_act] += 1
            else:
                instrumentation['scavenger_actions']['PASS'] += 1
                
    return act

aegis_agent._aegis_core_step = instrumented_core_step

seeds = [1, 7, 13, 24, 42]
scores = []

for seed in seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env.run([aegis_agent.agent, "starter"])
    steps = env.steps
    p0 = steps[-1][0]['reward']
    p1 = steps[-1][1]['reward']
    status = steps[-1][0]['status']
    scores.append(p0)
    print(f"Seed {seed:02d}: Aegis = ${p0:>8,.0f} | Starter = ${p1:>5,.0f} | Status = {status}")
    assert status == "DONE", f"Game failed with status {status}"

print("\n" + "=" * 80)
print("INSTRUMENTATION RESULTS (Across 3,600 Turns):")
print(f"  Total Steps Evaluated:            {instrumentation['total_steps']}")
print(f"  Auxiliary Hires Queued:           {instrumentation['auxiliary_hires_queued']}")
print(f"  Unscripted Hand Opportunities:    {instrumentation['unscripted_hand_opportunities']}")
print(f"  Scavenger Hand Actions Executed:  {dict(instrumentation['scavenger_actions'])}")
print(f"  Average Score:                    ${sum(scores)/len(scores):,.0f}")
print("=" * 80)
