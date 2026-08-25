"""Instrument Realized Prices & Price Realization Ratio (§3c)

Runs 20-seed self-play on Official 20 seeds to measure:
1. Exact units sold per product.
2. Exact gross revenue generated per product.
3. Realized average sale price (Revenue / Units).
4. Base price ($I_0$).
5. Realization Ratio (Realized Price / Base Price).
6. Scarcity ceiling (Theoretical maximum price with below_target scarcity).
7. Glut floor (Price when market is flooded with above_target excess).
8. The dollar gap between our realization and achievable meta realization.
"""

import sys
import os
from collections import defaultdict
import numpy as np

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    make_spatial_dispatcher_agent, BASE_PRICES
)
from kaggle_environments.envs.kaggriculture.kaggriculture import MARKET_PARAMS, market_price

OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]


def compute_scarcity_and_glut_prices(product: str) -> tuple:
    """Compute base price, scarcity ceiling (inv = I0 - T), and glut price (inv = I0 + T)."""
    p_info = MARKET_PARAMS[product]
    base = p_info["base"]
    I0 = p_info["I0"]
    T = p_info["T"]
    
    scarcity_price = market_price(product, I0 - T, MARKET_PARAMS)
    glut_price = market_price(product, I0 + T, MARKET_PARAMS)
    return base, scarcity_price, glut_price


def instrument_agent_realization(seeds=OFFICIAL_20):
    print("=" * 115)
    print(f"INSTRUMENTING REALIZED SALES PRICES & REALIZATION RATIOS (OFFICIAL 20 SEEDS, SELF-PLAY)")
    print("=" * 115)

    total_units_sold = defaultdict(int)
    total_rev_earned = defaultdict(float)
    player_rewards = []

    for seed in seeds:
        a0 = make_spatial_dispatcher_agent(kw_early=10)
        a1 = make_spatial_dispatcher_agent(kw_early=10)
        game = FastGame(seed=seed)

        while not game.done:
            obs0 = game.get_observation(0)
            obs1 = game.get_observation(1)
            act0 = a0(obs0)
            act1 = a1(obs1)

            # Record pre-market states
            prices_before = dict(obs0["market"]["prices"])
            
            shed0_before = dict(game.farms[0].shed)
            shed1_before = dict(game.farms[1].shed)

            game.step_game(act0, act1)

            # Measure what sold from shed deltas
            for p_idx, (shed_bef, farm_after) in enumerate([(shed0_before, game.farms[0]), (shed1_before, game.farms[1])]):
                for prod in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]:
                    cur_shed = farm_after.shed.get(prod, 0)
                    bef_shed = shed_bef.get(prod, 0)
                    delta_shed = bef_shed - cur_shed
                    if delta_shed > 0:
                        p = prices_before.get(prod, BASE_PRICES.get(prod, 10))
                        rev = delta_shed * p
                        total_units_sold[prod] += delta_shed
                        total_rev_earned[prod] += rev

        player_rewards.append(game.farms[0].money)
        player_rewards.append(game.farms[1].money)

    mean_reward = np.mean(player_rewards)
    median_reward = np.median(player_rewards)
    print(f"\nMean Self-Play Reward:   ${mean_reward:,.2f} (Median: ${median_reward:,.2f})")
    print(f"Total Games Analyzed:     {len(seeds)} matches ({len(player_rewards)} player runs)\n")

    # Table Header
    print(f"{'PRODUCT':<12} | {'UNITS/GAME':>10} | {'BASE ($)':>8} | {'SCARCITY ($)':>12} | {'GLUT ($)':>8} | {'REALIZED ($)':>12} | {'RATIO (R/B)':>11} | {'TOTAL REV':>10} | {'STATUS'}")
    print("-" * 115)

    tot_base_val = 0.0
    tot_realized_rev = 0.0

    products = ["WHEAT", "STRAWBERRY", "MILK", "WOOL", "MELON", "FERTILIZER", "CARROT", "EGG", "TOMATO"]
    for prod in products:
        units = total_units_sold[prod] / len(player_rewards) # per player run
        rev = total_rev_earned[prod] / len(player_rewards)
        base, scarcity, glut = compute_scarcity_and_glut_prices(prod)
        
        realized_p = rev / units if units > 0 else base
        ratio = realized_p / base if base > 0 else 1.0

        base_val = units * base
        tot_base_val += base_val
        tot_realized_rev += rev

        # Assessment
        if ratio >= 1.20:
            status = "PREMIUM (Scarcity)"
        elif ratio >= 0.85:
            status = "NEAR BASE"
        else:
            status = "GLUT DUMP (Depressed)"

        print(f"{prod:<12} | {units:>10.1f} | ${base:>7} | ${scarcity:>11.1f} | ${glut:>7.1f} | ${realized_p:>11.2f} | {ratio:>10.2f}x | ${rev:>9,.1f} | {status}")

    print("-" * 115)
    overall_ratio = tot_realized_rev / tot_base_val if tot_base_val > 0 else 1.0
    print(f"{'TOTAL / OVERALL':<12} | {'':>10} | ${tot_base_val:>7,.0f} | {'':>12} | {'':>8} | {'':>12} | {overall_ratio:>10.2f}x | ${tot_realized_rev:>9,.1f} |")
    print("=" * 115)

if __name__ == "__main__":
    instrument_agent_realization()
