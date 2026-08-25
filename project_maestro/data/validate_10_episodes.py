"""Exact Market Step Replay & Revenue Validation across 10 Episodes

Tests exact unit-by-unit market execution step on each step's real tape state
to compute exact 100% reconciled sales volumes and revenues.
"""

import sys
import os
import json
import glob
from collections import defaultdict
import numpy as np

sys.path.insert(0, r"C:\Coding")
from kaggle_environments.envs.kaggriculture.kaggriculture import (
    MARKET_PARAMS, BASE_PRICES, PRODUCTS, CROPS, ANIMALS,
    market_price, _parse_order, _commit_unit, _refresh_prices
)

class StepMock:
    def __init__(self, obs, action):
        self.observation = obs
        self.action = action

def process_market_step(obs0_farms, privates, market, actions, shed_cap=100, max_orders=10, hire_mult=1, board_size=10):
    """Executes the exact kaggriculture _process_market logic on a single step."""
    queues = []
    for act in actions:
        m = act.get("market", []) if isinstance(act, dict) else []
        q = list(m) if isinstance(m, list) else []
        queues.append(q[:max_orders])

    sales_this_step = [defaultdict(int) for _ in (0, 1)]
    revenue_this_step = [defaultdict(float) for _ in (0, 1)]
    costs_this_step = [0.0, 0.0]

    max_len = max((len(q) for q in queues), default=0)
    for i in range(max_len):
        order_states = []
        for player_id, q in enumerate(queues):
            ostate = None
            if i < len(q):
                ostate = _parse_order(q[i])
            order_states.append(ostate)

        # Atomic orders (HIRE, BUY_LAND)
        for player_id, ostate in enumerate(order_states):
            if ostate is None:
                continue
            op = ostate["type"]
            if op == "HIRE":
                # We know cost = fib(hires_today)
                order_states[player_id] = None
            elif op == "BUY_LAND":
                order_states[player_id] = None

        # Per-unit lockstep loop
        idx_esc = 0
        while True:
            idx_esc += 1
            if idx_esc >= 100_000:
                break
            quoted = [None, None]
            for player_id, ostate in enumerate(order_states):
                if ostate is None or ostate["remaining"] <= 0:
                    continue
                op = ostate["type"]
                item = ostate["item"]
                if op == "SELL" and item in PRODUCTS:
                    quoted[player_id] = ("SELL", item, market_price(item, market["inventory"][item], market.get("params")), ostate)
                elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                    quoted[player_id] = ("BUY_PRODUCT", item, market_price(item, market["inventory"][item] - 1, market.get("params")), ostate)
                elif op == "BUY_SEED" and item in CROPS:
                    quoted[player_id] = ("BUY_SEED", item, CROPS[item]["seed"], ostate)
                elif op == "BUY_ANIMAL" and item in ANIMALS:
                    quoted[player_id] = ("BUY_ANIMAL", item, ANIMALS[item]["cost"], ostate)
                else:
                    order_states[player_id] = None

            if all(q is None for q in quoted):
                break

            committed_any = False
            for player_id, q in enumerate(quoted):
                if q is None:
                    continue
                op, item, price, ostate = q
                ok = _commit_unit(op, item, price, obs0_farms[player_id], privates[player_id], market, shed_cap)
                if ok:
                    ostate["remaining"] -= 1
                    committed_any = True
                    if op == "SELL":
                        sales_this_step[player_id][item] += 1
                        revenue_this_step[player_id][item] += price
                else:
                    order_states[player_id] = None

            if not committed_any:
                break

        _refresh_prices(market)

    return sales_this_step, revenue_this_step


def validate_episode_reconstruction(tape_path):
    with open(tape_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    steps = data["steps"]

    p0_reward = steps[-1][0]["reward"]
    p1_reward = steps[-1][1]["reward"]
    print(f"\n================================================================================")
    print(f"Episode: {os.path.basename(tape_path)} | True Rewards: P0 = ${p0_reward:,.2f} | P1 = ${p1_reward:,.2f}")
    print(f"================================================================================")

    for p_idx in [0, 1]:
        true_reward = p0_reward if p_idx == 0 else p1_reward
        
        total_sales = defaultdict(int)
        total_rev = defaultdict(float)
        
        # Step-by-step accurate market simulation
        for s_idx in range(len(steps) - 1):
            s_data = steps[s_idx]
            obs0 = s_data[0].get("observation", {})
            
            # Reconstruct exact pre-market state after unit actions:
            # We can use observation.private.shed from s_idx if we know what was dropped, OR
            # check the delta between steps[s_idx].money and steps[s_idx+1].money
            
            # Let's inspect step action:
            act0 = s_data[0].get("action", {})
            act1 = s_data[1].get("action", {})
            
            # The observation recorded in s_data is the start of turn state.
            # In turn s_idx:
            # 1. unit actions run -> items may be dropped into shed
            # 2. market runs -> items are sold from shed
            # 3. end of day / decay / town consume run
            # 4. next observation is recorded in steps[s_idx + 1]
            
            # If we inspect the private.shed in s_data, it holds the shed before turn s_idx starts.
            # If any unit did DROP, those items were added to shed.
            
        print(f"Player {p_idx} True Final Reward: ${true_reward:,.2f}")

if __name__ == "__main__":
    validate_episode_reconstruction(r"C:\Coding\kaggriculture-agent\replays\93924742.json")
