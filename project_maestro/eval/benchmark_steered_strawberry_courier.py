"""Benchmark Dedicated Courier Strawberry Fertilization against Genuinely Steered Baseline

Evaluates:
Baseline: Production MaestroFullPortfolioAgent(seed=seed) [Seat 0] vs MaestroFullPortfolioAgent() [Seat 1]
Candidate: SteeredDedicatedCourierAgent(seed=seed) [Seat 0] vs MaestroFullPortfolioAgent() [Seat 1]

Both baseline and candidate run against the identical unsteered opponent (Kw=10), ensuring the
exact same shop steering trajectory and AMM conditions across all seeds.
"""

import sys
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent, make_spatial_dispatcher_agent,
    NW_WHEAT, NE_STRAWBERRY, SHED_ACCESS_TILES,
    get_step_towards, dist, compute_optimal_steering_kw
)

OFFICIAL_20_SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
STRAWBERRY_SHOPS = {"SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "FARMERS_MARKET", "BRUNCH_SPOT"}


class SteeredDedicatedCourierAgent(MaestroFullPortfolioAgent):
    """Production Agent with Integrated Day-0 Steering + 4-Shop Dedicated Courier."""
    def __init__(self, params=None, seed: int = None, kw_early: int = None):
        super().__init__(params, seed=seed, kw_early=kw_early)

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        day = obs["day"]
        hour = obs["hour"]
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        unlocked_quads = set(me.get("unlocked_quadrants", []))
        unlocked_shops = set(obs.get("town", {}).get("unlocked_shops", []))

        # Base agent logic (handles Day 0-2 shop steering, core farming, market orders)
        res = super().__call__(obs)

        shed = private.get("shed", {})
        shed_fert = shed.get("FERTILIZER", 0)
        shed_wheat = shed.get("WHEAT", 0)
        money = me.get("money", 0)

        # Economic Condition: Town MUST demand strawberries via the verified 4-shop set
        has_straw_drain = bool(unlocked_shops & STRAWBERRY_SHOPS)

        # Liquidity guard: require money >= $300 and shed_wheat >= 8
        can_reserve_fert = (
            has_straw_drain
            and money >= 300
            and shed_wheat >= 8
            and "NE" in unlocked_quads
            and 6 <= day <= 25
        )
        reserved_fert = 8 if can_reserve_fert else 0

        # Protect reserved fertilizer from market sell orders
        filtered_orders = []
        for order in res.get("market", []):
            if order[0] == "SELL" and order[1] == "FERTILIZER":
                sellable = max(0, shed_fert - reserved_fert)
                if sellable > 0:
                    filtered_orders.append(["SELL", "FERTILIZER", sellable])
            else:
                filtered_orders.append(order)
        res["market"] = filtered_orders

        # Courier dispatch logic on Hand 3 (Index 3 in all_units: [Farmer, Hand0, Hand1, Hand2])
        all_units = [me["farmer"]] + me.get("hands", [])
        if can_reserve_fert and len(all_units) > 3:
            u_idx = 3
            pos = tuple(all_units[u_idx])
            inv = private["inventories"][u_idx] if u_idx < len(private["inventories"]) else {}
            u_fert = inv.get("FERTILIZER", 0)

            # Find strawberry tiles that need fertilization
            straw_fert_needed = []
            for sx, sy in self.ne_strawberry:
                t = me["tiles"][sy][sx]
                if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "STRAWBERRY":
                    if t.get("fertilized_until_day", -1) <= day:
                        straw_fert_needed.append((sx, sy))

            farmer_act = res.get("farmer", ["PASS"])
            hands_acts = list(res.get("hands", []))
            all_acts = [farmer_act] + hands_acts
            curr_act = all_acts[u_idx]

            # Return-to-base curfew: hour >= 16 must return to (4,4) and drop inventory
            if hour >= 16:
                if pos in SHED_ACCESS_TILES:
                    if u_fert > 0 or sum(inv.values()) > inv.get("WHEAT", 0):
                        all_acts[u_idx] = ["DROP"]
                elif pos[0] >= 5 or pos[1] >= 5:
                    all_acts[u_idx] = [get_step_towards(pos, (4, 4))]

            # Midday Courier Departure Window: hours 8..13
            elif curr_act == ["PASS"] and 8 <= hour <= 13 and straw_fert_needed:
                if u_fert > 0:
                    best_target = min(straw_fert_needed, key=lambda p: dist(pos, p))
                    if pos == best_target:
                        all_acts[u_idx] = ["FERTILIZE"]
                    else:
                        all_acts[u_idx] = [get_step_towards(pos, best_target)]
                elif shed_fert > 0 and hour <= 11:
                    if pos in SHED_ACCESS_TILES:
                        all_acts[u_idx] = ["PICKUP", "FERTILIZER", min(2, shed_fert)]
                    else:
                        all_acts[u_idx] = [get_step_towards(pos, (4, 4))]

            res["farmer"] = all_acts[0]
            res["hands"] = all_acts[1:]

        return res


def run_match(p0, p1, seed: int) -> Tuple[float, float]:
    g = FastGame(seed=seed)
    while not g.done:
        act0 = p0(g.get_observation(0))
        act1 = p1(g.get_observation(1))
        g.step_game(act0, act1)
    return float(g.farms[0].money), float(g.farms[1].money)


def eval_suite(seeds: List[int], label: str = ""):
    print(f"\n--- Running Evaluation: {label} (N={len(seeds)} seeds) ---")
    base_scores = []
    courier_scores = []
    records = []

    for idx, seed in enumerate(seeds):
        # Baseline Match: Steered Production Agent vs Unsteered Opponent
        p0_b = make_spatial_dispatcher_agent(seed=seed)
        p1_b = make_spatial_dispatcher_agent()
        r0_b, r1_b = run_match(p0_b, p1_b, seed)
        b_avg = (r0_b + r1_b) / 2.0
        base_scores.append(b_avg)

        # Candidate Match: Steered Courier Agent vs Unsteered Opponent
        p0_c = SteeredDedicatedCourierAgent(seed=seed)
        p1_c = make_spatial_dispatcher_agent()
        r0_c, r1_c = run_match(p0_c, p1_c, seed)
        c_avg = (r0_c + r1_c) / 2.0
        courier_scores.append(c_avg)

        delta = c_avg - b_avg
        records.append((seed, b_avg, c_avg, delta))

        if len(seeds) > 20 and ((idx + 1) % 25 == 0 or (idx + 1) == len(seeds)):
            print(f"Processed {idx + 1:>3}/{len(seeds)} seeds...")

    base_arr = np.array(base_scores)
    courier_arr = np.array(courier_scores)
    diff_arr = courier_arr - base_arr

    mean_base = float(np.mean(base_arr))
    mean_courier = float(np.mean(courier_arr))
    mean_diff = float(np.mean(diff_arr))
    std_diff = float(np.std(diff_arr, ddof=1)) if len(seeds) > 1 else 0.0
    se_diff = std_diff / np.sqrt(len(seeds))
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=len(seeds) - 1)) if se_diff > 0 else 1.0

    wins = sum(1 for d in diff_arr if d > 0)
    losses = sum(1 for d in diff_arr if d < 0)
    ties = sum(1 for d in diff_arr if d == 0)

    print(f"Baseline Mean:  ${mean_base:,.2f}")
    print(f"Courier Mean:   ${mean_courier:,.2f} (Delta: ${mean_diff:>+,.2f})")
    print(f"SE of Delta:    ${se_diff:,.2f} (t = {t_stat:>+.2f}, p = {p_val:.4e})")
    print(f"Head-to-Head:   Courier won {wins}, Lost {losses}, Tied {ties}")
    if wins + losses > 0:
        print(f"Win Rate among Non-Ties: {wins/(wins+losses)*100:.1f}%")

    return records, mean_base, mean_courier, mean_diff, se_diff, t_stat, p_val


def main():
    print("=" * 95)
    print("=== DEDICATED-COURIER STRAWBERRY FERTILIZATION BENCHMARK (STEERED BASELINE) ===")
    print("=" * 95)

    rec_20, b20, c20, d20, se20, t20, p20 = eval_suite(OFFICIAL_20_SEEDS, "Official 20 Seeds")
    print(f"\n{'Seed':<6} | {'Baseline Standing':<18} | {'Active Courier':<18} | {'Delta':<10}")
    print("-" * 60)
    for s, b_avg, c_avg, delta in rec_20:
        print(f"{s:<6} | ${b_avg:>16,.2f} | ${c_avg:>16,.2f} | ${delta:>+9,.2f}")

    print("\n" + "=" * 95)
    rec_100, b100, c100, d100, se100, t100, p100 = eval_suite(list(range(10000, 10100)), "100 Disjoint Seeds (10000-10099)")

    print("\n" + "=" * 95)
    print("=== SUMMARY OF FINDINGS ===")
    print(f"Official 20 Seeds Delta:   ${d20:>+,.2f} (Baseline: ${b20:,.2f} -> Candidate: ${c20:,.2f}, t={t20:.2f}, p={p20:.4e})")
    print(f"100 Disjoint Seeds Delta:  ${d100:>+,.2f} (Baseline: ${b100:,.2f} -> Candidate: ${c100:,.2f}, t={t100:.2f}, p={p100:.4e})")
    print("=" * 95)


if __name__ == "__main__":
    main()
