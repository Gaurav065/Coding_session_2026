"""Forensic Loss Analyzer — Deep Root Cause Diagnostic across 5 Strategies

Simulates matches across all 5 synthetic match-ups, filters for lost games,
and computes the exact financial and operational deltas that caused each loss.
"""

import sys
import json
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.idc_master_agent import IDCMasterAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

MATCHUPS = {
    "1. Dominant Dairy Meta (10C/4S)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s),
    "2. Tomato Meta Spam": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 6, "sheep_cap": 4, "strawberry_target": 0, "melon_seed_target": 0, "crew_mid": 12, "crew_late": 14
    }, seed=s),
    "3. All-In Cows & Melons (14C/20M)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 14, "sheep_cap": 0, "strawberry_target": 6, "melon_seed_target": 20, "crew_mid": 11, "crew_late": 13
    }, seed=s),
    "4. Balanced Pasture Hybrid (7C/7S)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 7, "sheep_cap": 7, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s),
    "5. All-In Sheep & Strawberries (14S/28Str)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 0, "sheep_cap": 14, "strawberry_target": 28, "melon_seed_target": 0, "crew_mid": 11, "crew_late": 13
    }, seed=s),
}

def analyze_losses(num_seeds: int = 40):
    print(f'Starting Deep Forensic Loss Analysis across 5 Strategies (N={num_seeds} Seeds each)...\n')

    loss_diagnostics = defaultdict(list)

    for matchup_name, make_opp in MATCHUPS.items():
        print(f'Diagnosing Losses for: {matchup_name}...')
        total_games = 0
        losses = 0

        for seed in range(600, 600 + num_seeds):
            g = FastGame(seed=seed)
            cand = IDCMasterAgent(seed=seed)
            opp = make_opp(seed)

            p0_revenue = defaultdict(float)
            p1_revenue = defaultdict(float)

            while not g.done:
                obs0 = g.get_observation(0)
                obs1 = g.get_observation(1)
                act0 = cand(obs0)
                act1 = opp(obs1)

                # Record sales revenue
                for order in act0.get("market", []):
                    if order and order[0] == "SELL" and len(order) >= 3:
                        p0_revenue[order[1]] += int(order[2]) * obs0["market"]["prices"].get(order[1], 0)
                for order in act1.get("market", []):
                    if order and order[0] == "SELL" and len(order) >= 3:
                        p1_revenue[order[1]] += int(order[2]) * obs1["market"]["prices"].get(order[1], 0)

                g.step_game(act0, act1)

            f0 = g.farms[0]
            f1 = g.farms[1]
            total_games += 1

            if f0.money <= f1.money:
                losses += 1
                delta_milk = p0_revenue["MILK"] - p1_revenue["MILK"]
                delta_wool = p0_revenue["WOOL"] - p1_revenue["WOOL"]
                delta_straw = p0_revenue["STRAWBERRY"] - p1_revenue["STRAWBERRY"]
                delta_melon = p0_revenue["MELON"] - p1_revenue["MELON"]
                delta_fert = p0_revenue["FERTILIZER"] - p1_revenue["FERTILIZER"]

                loss_diagnostics[matchup_name].append({
                    "seed": seed,
                    "score_margin": f0.money - f1.money,
                    "p0_score": f0.money,
                    "p1_score": f1.money,
                    "delta_milk": delta_milk,
                    "delta_wool": delta_wool,
                    "delta_straw": delta_straw,
                    "delta_melon": delta_melon,
                    "delta_fert": delta_fert,
                    "shops": list(g.unlocked_shops)
                })

        wr = ((total_games - losses) / total_games) * 100
        print(f'   -> Current Win Rate: {wr:5.1f}% | Loss Count: {losses}/{total_games}\n')

    print('=' * 115)
    print('DEEP FORENSIC LOSS AUTOPSY REPORT')
    print('=' * 115)

    summary_report = {}
    for matchup_name, diag_list in loss_diagnostics.items():
        if not diag_list:
            print(f'{matchup_name}: 0 Losses recorded! (100% Win Rate)\n')
            continue

        mean_loss_margin = np.mean([d["score_margin"] for d in diag_list])
        mean_d_milk = np.mean([d["delta_milk"] for d in diag_list])
        mean_d_wool = np.mean([d["delta_wool"] for d in diag_list])
        mean_d_straw = np.mean([d["delta_straw"] for d in diag_list])
        mean_d_melon = np.mean([d["delta_melon"] for d in diag_list])
        mean_d_fert = np.mean([d["delta_fert"] for d in diag_list])

        print(f'MATCHUP: {matchup_name} ({len(diag_list)} Losses analyzed)')
        print(f'  • Average Loss Deficit  : -${abs(mean_loss_margin):,.2f}')
        print(f'  • Milk Revenue Delta   : {"+" if mean_d_milk >= 0 else "-"}${abs(mean_d_milk):,.2f}')
        print(f'  • Wool Revenue Delta   : {"+" if mean_d_wool >= 0 else "-"}${abs(mean_d_wool):,.2f}')
        print(f'  • Strawberry Rev Delta : {"+" if mean_d_straw >= 0 else "-"}${abs(mean_d_straw):,.2f}')
        print(f'  • Melon Revenue Delta  : {"+" if mean_d_melon >= 0 else "-"}${abs(mean_d_melon):,.2f}')
        print(f'  • Fertilizer Rev Delta : {"+" if mean_d_fert >= 0 else "-"}${abs(mean_d_fert):,.2f}')
        print()

        summary_report[matchup_name] = {
            "losses": len(diag_list),
            "mean_loss_margin": round(float(mean_loss_margin), 2),
            "mean_d_milk": round(float(mean_d_milk), 2),
            "mean_d_wool": round(float(mean_d_wool), 2),
            "mean_d_straw": round(float(mean_d_straw), 2),
            "mean_d_melon": round(float(mean_d_melon), 2),
            "mean_d_fert": round(float(mean_d_fert), 2)
        }

    out_file = 'project_maestro/data/forensic_loss_autopsy_report.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(summary_report, f, indent=2)
    print(f'Report saved to {out_file}')

if __name__ == '__main__':
    analyze_losses(40)
