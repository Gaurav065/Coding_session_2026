import sys
import os
import copy

sys.path.insert(0, r'C:\Coding')

import main as aegis_agent
from project_aegis.benchmarks.synthetic_multiwave_opponent import synthetic_multiwave_opponent
from kaggle_environments import make

print("=" * 80)
print("10-SEED ABLATION BENCHMARK: WAVE-2 & SCAVENGER OVERLAY (ON vs OFF)")
print("=" * 80)

seeds = [1, 7, 11, 13, 24, 42, 55, 100, 1024, 65536]
results = []

for seed in seeds:
    # 1. Run Feature ON
    env_on = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env_on.run([aegis_agent.agent, synthetic_multiwave_opponent])
    score_on = env_on.steps[-1][0]['reward']
    
    # 2. Run Feature OFF (Disable auxiliary hire and scavenger overlay)
    orig_schedule_hire = aegis_agent.schedule_auxiliary_farmhand_hire
    orig_scavenger = aegis_agent.scavenger_farmhand_overlay
    
    aegis_agent.schedule_auxiliary_farmhand_hire = lambda action, obs: action
    aegis_agent.scavenger_farmhand_overlay = lambda action, obs: action
    
    env_off = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env_off.run([aegis_agent.agent, synthetic_multiwave_opponent])
    score_off = env_off.steps[-1][0]['reward']
    
    # Restore original functions
    aegis_agent.schedule_auxiliary_farmhand_hire = orig_schedule_hire
    aegis_agent.scavenger_farmhand_overlay = orig_scavenger
    
    delta = score_on - score_off
    results.append({
        'seed': seed,
        'on': score_on,
        'off': score_off,
        'delta': delta
    })
    
    delta_str = f"+${delta:>8,.0f}" if delta >= 0 else f"-${abs(delta):>8,.0f}"
    print(f"Seed {seed:05d}: Feature ON = ${score_on:>8,.0f} | Feature OFF = ${score_off:>8,.0f} | Delta = {delta_str}")

print("\n" + "=" * 80)
avg_on = sum(r['on'] for r in results) / len(results)
avg_off = sum(r['off'] for r in results) / len(results)
avg_delta = sum(r['delta'] for r in results) / len(results)

print(f"ABLATION SUMMARY ACROSS {len(seeds)} SEEDS:")
print(f"  Average Score with Feature ON:   ${avg_on:,.0f}")
print(f"  Average Score with Feature OFF:  ${avg_off:,.0f}")
print(f"  Net Delta (Attributable Gain):   +${avg_delta:,.0f}")
print("=" * 80)
