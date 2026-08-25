import sys
import os
import time
from collections import defaultdict

sys.path.insert(0, r'C:\Coding')

import main as aegis_agent
from project_aegis.benchmarks.synthetic_multiwave_opponent import synthetic_multiwave_opponent
from kaggle_environments import make

print("=" * 80)
print("COMPREHENSIVE BENCHMARK: AEGIS (WAVE-2 OVERLAY) VS SYNTHETIC MULTIWAVE OPPONENT")
print("=" * 80)

seeds = [1, 7, 13, 24, 42, 55, 100, 144, 1024, 65536]
results = []

for seed in seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env.run([aegis_agent.agent, synthetic_multiwave_opponent])
    
    steps = env.steps
    p0_score = steps[-1][0]['reward']
    p1_score = steps[-1][1]['reward']
    status = steps[-1][0]['status']
    margin = p0_score - p1_score
    win = (p0_score > p1_score)
    
    # Analyze Melon Extraction
    p0_melons = 0
    p1_melons = 0
    p0_melon_rev = 0
    p1_melon_rev = 0
    
    for s in steps:
        prices = s[0]['observation']['market']['prices']
        a0 = s[0].get('action') or {}
        a1 = s[1].get('action') or {}
        for m in a0.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL' and m[1] == 'MELON':
                q = int(m[2]) if str(m[2]).isdigit() else 1
                p0_melons += q
                p0_melon_rev += q * prices.get('MELON', 1)
        for m in a1.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL' and m[1] == 'MELON':
                q = int(m[2]) if str(m[2]).isdigit() else 1
                p1_melons += q
                p1_melon_rev += q * prices.get('MELON', 1)

    shops = steps[-1][0]['observation']['town']['unlocked_shops']
    
    res = {
        'seed': seed,
        'p0_score': p0_score,
        'p1_score': p1_score,
        'margin': margin,
        'win': win,
        'p0_melons': p0_melons,
        'p0_melon_rev': p0_melon_rev,
        'p1_melons': p1_melons,
        'p1_melon_rev': p1_melon_rev,
        'shops': shops
    }
    results.append(res)
    
    win_str = "WIN " if win else "LOSS"
    print(f"Seed {seed:05d} [{win_str}]: Aegis = ${p0_score:>8,.0f} | Opponent = ${p1_score:>8,.0f} | Margin = {margin:>+8,.0f} | Melons: Aegis={p0_melons} (${p0_melon_rev:,.0f}) vs Opp={p1_melons} (${p1_melon_rev:,.0f})")

print("\n" + "=" * 80)
total_wins = sum(1 for r in results if r['win'])
avg_score = sum(r['p0_score'] for r in results) / len(results)
avg_opp_score = sum(r['p1_score'] for r in results) / len(results)
avg_margin = sum(r['margin'] for r in results) / len(results)
avg_melons = sum(r['p0_melons'] for r in results) / len(results)
avg_melon_rev = sum(r['p0_melon_rev'] for r in results) / len(results)

print(f"BENCHMARK SUMMARY ACROSS {len(seeds)} SEEDS:")
print(f"  Win Rate:                   {total_wins}/{len(seeds)} ({total_wins/len(seeds)*100:.1f}%)")
print(f"  Average Aegis Score:        ${avg_score:,.0f}")
print(f"  Average Opponent Score:     ${avg_opp_score:,.0f}")
print(f"  Average Victory Margin:     +${avg_margin:,.0f}")
print(f"  Average Melons Extracted:   {avg_melons:.1f} units (${avg_melon_rev:,.0f} revenue)")
print("=" * 80)
