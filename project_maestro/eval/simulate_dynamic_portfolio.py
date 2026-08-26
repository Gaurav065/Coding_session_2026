"""Dynamic Portfolio Simulation & Market Price Evolution Benchmark

Runs multi-seed tournament matches comparing the Dynamic Portfolio Agent against
the Dominant Tournament Meta, logging price evolution and crop revenue streams.
"""

import sys
import json
import time
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dynamic_portfolio_agent import DynamicPortfolioAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def simulate_portfolio_benchmark(num_seeds: int = 50):
    print(f'Starting Dynamic Portfolio Simulation across N={num_seeds} Diverse Seeds...\n')

    seeds = list(range(200, 200 + num_seeds))

    wins = 0
    our_scores = []
    opp_scores = []
    crop_revenues = defaultdict(list)
    price_mins = defaultdict(list)
    price_maxs = defaultdict(list)
    price_avgs = defaultdict(list)
    leftover_cash_values = []

    t0 = time.time()

    for s_idx, seed in enumerate(seeds):
        g = FastGame(seed=seed)
        agent0 = DynamicPortfolioAgent(seed=seed)
        agent1 = MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6, 'enable_3b': False}, seed=seed)

        match_crop_rev = defaultdict(float)
        match_prices = defaultdict(list)

        while not g.done:
            obs0 = g.get_observation(0)
            obs1 = g.get_observation(1)

            # Record prices
            for item, p in obs0["market"]["prices"].items():
                match_prices[item].append(p)

            act0 = agent0(obs0)
            act1 = agent1(obs1)

            # Record revenue
            for order in act0.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    item = order[1]
                    qty = int(order[2])
                    p = obs0["market"]["prices"].get(item, 0)
                    match_crop_rev[item] += (qty * p)

            g.step_game(act0, act1)

        f0_money = g.farms[0].money
        f1_money = g.farms[1].money

        our_scores.append(f0_money)
        opp_scores.append(f1_money)
        if f0_money > f1_money:
            wins += 1

        for item, rev in match_crop_rev.items():
            crop_revenues[item].append(rev)

        for item, p_list in match_prices.items():
            price_mins[item].append(min(p_list))
            price_maxs[item].append(max(p_list))
            price_avgs[item].append(np.mean(p_list))

        # Check leftover shed value
        final_p0 = g.farms[0]
        final_prices = g.get_observation(0)["market"]["prices"]
        leftover_val = sum(qty * final_prices.get(item, 0) for item, qty in final_p0.shed.items())
        leftover_cash_values.append(leftover_val)

        if (s_idx + 1) % 10 == 0 or (s_idx + 1) == num_seeds:
            print(f'Simulated {s_idx + 1}/{num_seeds} matches... Win Rate: {wins/(s_idx+1)*100:5.1f}% | Our Mean: ${np.mean(our_scores):,.0f} vs Opp: ${np.mean(opp_scores):,.0f}')

    elapsed = time.time() - t0
    wr = wins / num_seeds * 100
    mean_our = float(np.mean(our_scores))
    mean_opp = float(np.mean(opp_scores))
    p5_floor = float(np.percentile(our_scores, 5))
    mean_leftover = float(np.mean(leftover_cash_values))

    print('\n' + '=' * 95)
    print(f'DYNAMIC PORTFOLIO SIMULATION REPORT (N={num_seeds} Matches)')
    print('=' * 95)
    print(f'Win Rate vs Dominant Meta : {wr:5.1f}% ({wins}/{num_seeds} Wins)')
    print(f'Our Average Bank Balance  : ${mean_our:,.2f}')
    print(f'Opponent Average Balance  : ${mean_opp:,.2f}')
    print(f'Net Score Margin          : +${mean_our - mean_opp:,.2f}')
    print(f'p5 Risk Floor Protection  : ${p5_floor:,.2f}')
    print(f'Average Shed Leftover Cash: ${mean_leftover:,.2f} (Clean Endgame Flush)')
    print('=' * 95)

    print('\n1. REVENUE BREAKDOWN BY PRODUCT STREAM (Average per Match):')
    for item in ["STRAWBERRY", "MILK", "WOOL", "MELON", "WHEAT", "TOMATO", "CARROT", "FERTILIZER"]:
        rev_list = crop_revenues.get(item, [0])
        avg_rev = float(np.mean(rev_list)) if rev_list else 0.0
        pct = (avg_rev / mean_our * 100) if mean_our > 0 else 0
        print(f'   - {item:12s}: ${avg_rev:10,.2f} ({pct:4.1f}% of total portfolio revenue)')

    print('\n2. REALIZED PRICE EVOLUTION (Average across All Matches):')
    for item in ["STRAWBERRY", "MILK", "WOOL", "MELON", "WHEAT", "TOMATO", "CARROT"]:
        print(f'   - {item:12s}: Min ${np.mean(price_mins[item]):3.0f} | Max ${np.mean(price_maxs[item]):3.0f} | Average Realized ${np.mean(price_avgs[item]):3.0f}')
    print('=' * 95)

    out_file = 'project_maestro/data/dynamic_portfolio_simulation_report.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            'seeds': num_seeds,
            'win_rate': wr,
            'our_mean': mean_our,
            'opp_mean': mean_opp,
            'margin': mean_our - mean_opp,
            'p5_floor': p5_floor,
            'mean_leftover_shed_cash': mean_leftover,
            'crop_revenue_means': {k: float(np.mean(v)) for k, v in crop_revenues.items()}
        }, f, indent=2)
    print(f'\nDetailed simulation results saved to {out_file}')

if __name__ == '__main__':
    simulate_portfolio_benchmark(50)
