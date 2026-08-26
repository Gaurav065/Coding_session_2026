"""170k+ God Pathway Explorer & Solo High-Ceiling Simulation Suite

Simulates solo/uncontested environments across hundreds of shop combinations
to discover and catalog all macro pathways that exceed $170,000+ final score.
"""

import sys
import json
import time
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any, Tuple

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

# Define 4 Major Macro Strategic Pathways
STRATEGIC_PATHWAYS = {
    "1. Quad_Dairy_Smoothie_Titan": {
        "cow_cap_base": 12,
        "sheep_cap": 2,
        "strawberry_target": 22,
        "melon_seed_target": 8,
        "crew_mid": 10,
        "crew_late": 12,
    },
    "2. Triple_Yarn_Wool_Syndicate": {
        "cow_cap_base": 4,
        "sheep_cap": 10,
        "strawberry_target": 20,
        "melon_seed_target": 8,
        "crew_mid": 10,
        "crew_late": 12,
    },
    "3. Balanced_Grandmaster_Metropolis": {
        "cow_cap_base": 9,
        "sheep_cap": 5,
        "strawberry_target": 22,
        "melon_seed_target": 8,
        "crew_mid": 10,
        "crew_late": 12,
    },
    "4. Maximized_Mega_Pasture_Dairy": {
        "cow_cap_base": 14,
        "sheep_cap": 0,
        "strawberry_target": 22,
        "melon_seed_target": 8,
        "crew_mid": 11,
        "crew_late": 13,
    }
}

def search_170k_pathways(num_seeds: int = 150):
    print(f'Starting Search for $170,000+ High-Ceiling Pathways across N={num_seeds} Diverse Shop Seeds...\n')

    god_pathways = []
    category_results = defaultdict(list)

    for path_name, params in STRATEGIC_PATHWAYS.items():
        print(f'Testing Macro Pathway: {path_name}...')
        path_scores = []

        for seed in range(500, 500 + num_seeds):
            g = FastGame(seed=seed)
            agent = MaestroFullPortfolioAgent(params=params, seed=seed)
            passive_opp = {"farmer": ["PASS"], "hands": [], "market": []}

            while not g.done:
                obs0 = g.get_observation(0)
                act0 = agent(obs0)
                g.step_game(act0, passive_opp)

            score = g.farms[0].money
            path_scores.append(score)
            unlocked_shops = list(g.unlocked_shops)

            if score >= 150000:
                god_pathways.append({
                    "pathway": path_name,
                    "seed": seed,
                    "score": round(score, 2),
                    "shops": unlocked_shops,
                    "tier": "MEGA_TIER ($170k+)" if score >= 170000 else "HIGH_TIER ($150k-$170k)"
                })

        mean_score = float(np.mean(path_scores))
        max_score = float(np.max(path_scores))
        p90_score = float(np.percentile(path_scores, 90))
        p10_score = float(np.percentile(path_scores, 10))

        category_results[path_name] = {
            "mean": mean_score,
            "max": max_score,
            "p90": p90_score,
            "p10": p10_score,
            "count_150k_plus": sum(1 for s in path_scores if s >= 150000),
            "count_170k_plus": sum(1 for s in path_scores if s >= 170000),
        }
        print(f'   -> Mean: ${mean_score:,.2f} | Max: ${max_score:,.2f} | P90: ${p90_score:,.2f} | $170k+ Matches: {category_results[path_name]["count_170k_plus"]}/{num_seeds}\n')

    # Sort God Pathways by score
    god_pathways.sort(key=lambda x: x["score"], reverse=True)

    print('=' * 105)
    print('TOP DISCOVERED $170k+ GOD PATHWAYS & SHOP COMBINATIONS')
    print('=' * 105)
    
    top_170k = [p for p in god_pathways if p["score"] >= 170000]
    for i, p in enumerate(top_170k[:15]):
        shops_str = ", ".join(p["shops"][:5]) + ("..." if len(p["shops"]) > 5 else "")
        print(f'{i+1:2d}. Score: ${p["score"]:10,.2f} | Pathway: {p["pathway"]}')
        print(f'    Shop Combination: [{shops_str}]\n')

    out_file = 'project_maestro/data/god_pathways_170k_report.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_tested_seeds": num_seeds,
            "pathway_stats": category_results,
            "total_170k_matches": len(top_170k),
            "top_records": god_pathways[:50]
        }, f, indent=2)

    print(f'Report saved to {out_file}')

if __name__ == '__main__':
    search_170k_pathways(150)
