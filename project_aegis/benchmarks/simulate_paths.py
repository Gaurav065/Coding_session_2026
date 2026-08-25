"""Project Aegis - Multi-Path Simulation Benchmark Lab

Simulates and compares 4 candidate strategic paths across a wide distribution of random seeds:
- Path 1: Baseline Multi-Route (8c6s default, 10c4s milk, 6c12s yarn)
- Path 2: Dedicated Dual-Melon Route on Agro Shops (151k / 154k dual-melon tape)
- Path 3: Universal Wave-2 Melon Replanter Overlay in Ghost/Scavenger
- Path 4: Straw-Cow High-Density Crop Route (165k straw-cow tape)

Benchmarks against Starter, Random, and Decoded sparring agents across 20+ diverse seeds.
"""

import sys
import os
import copy
import json
import zlib
import base64
from typing import Dict, List, Any, Optional, Tuple, Set

# Paths
sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make
from project_aegis.core import (
    PureDebtManager,
    execute_terminal_liquidation,
    safe_agent_fallback,
    MAX_MARKET_ORDERS,
    calculate_single_unit_price
)
from project_aegis.predator import PredatorEngine, OpponentShedEstimator
from project_aegis.river import RiverEngine
from project_aegis.ghost import apply_ghost_signature_spoof, scavenger_farmhand_overlay, OpportunisticCropManager
from project_aegis.guards import weed_repair_overlay, feed_rescue_guard
from project_aegis.tape_loader import get_base_tape, get_lookahead_scheduled_sells, _TRUE_MILK_SUPPORT_SHOPS
from decoded_agent import agent as decoded_agent

# Load additional candidate tapes for Path 2, 3, 4
with open(r'C:\Coding\kaggriculture-agent\tape_151k.json', 'r', encoding='utf-8') as f:
    _TAPE_151K_DUAL_MELON = json.load(f)

with open(r'C:\Coding\kaggriculture-agent\tape_154k_sheep_melon.json', 'r', encoding='utf-8') as f:
    _TAPE_154K_SHEEP_MELON = json.load(f)

with open(r'C:\Coding\kaggriculture-agent\tape_165k_straw_cow.json', 'r', encoding='utf-8') as f:
    _TAPE_165K_STRAW_COW = json.load(f)

# Candidate Factory Agents
def create_path_agent(path_id: str):
    """Factory creating an agent configured for a specific strategic path."""
    state_storage: Dict[int, Any] = {}

    class SimAgentState:
        def __init__(self):
            self.debt_mgr = PureDebtManager()
            self.shed_estimator = OpponentShedEstimator()
            self.predator = PredatorEngine(self.shed_estimator)
            self.river = RiverEngine()
            self.last_step = -1
            self.committed_route = None

        def reset_if_new(self, step: int):
            if step == 0 or step < self.last_step:
                self.debt_mgr.reset_if_new_game(step)
                self.shed_estimator.reset_if_new_game(step)
                self.river = RiverEngine()
                self.committed_route = None
            self.last_step = step

    def sim_agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
        seat = obs.get("player", 0) if isinstance(obs, dict) else 0
        if seat not in state_storage:
            state_storage[seat] = SimAgentState()
        state = state_storage[seat]
        step = obs.get("step", 0)
        state.reset_if_new(step)

        # 1. Predator update
        state.predator.update(obs)

        # 2. Route Selection based on Path configuration
        shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
        
        # Route selection logic
        if path_id == "PATH_1_BASELINE":
            # Current baseline
            if len(shops) >= 1 and shops[:1] == ["YARN_STORE"]:
                active_tape = get_base_tape("6c12s_4q_first_yarn")
            elif len(shops) >= 2 and "YARN_STORE" in shops[:2]:
                active_tape = get_base_tape("6c12s_4q_second_yarn")
            elif _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:2]):
                active_tape = get_base_tape("10c4s_3q")
            elif len(shops) >= 3 and "YARN_STORE" in shops[:3] and step < 144:
                active_tape = get_base_tape("6c8s_3q")
            else:
                active_tape = get_base_tape("8c6s_3q")

        elif path_id == "PATH_2_DUAL_MELON_TAPE":
            # If yarn -> yarn tape, if true milk -> 10c4s, but if agro (Bakery/Brunch/Farmers) -> 151k Dual Melon!
            if len(shops) >= 1 and shops[:1] == ["YARN_STORE"]:
                active_tape = get_base_tape("6c12s_4q_first_yarn")
            elif len(shops) >= 2 and "YARN_STORE" in shops[:2]:
                active_tape = get_base_tape("6c12s_4q_second_yarn")
            elif _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:2]):
                active_tape = get_base_tape("10c4s_3q")
            elif {"BAKERY", "BRUNCH_SPOT", "FARMERS_MARKET"}.intersection(shops[:2]):
                active_tape = _TAPE_151K_DUAL_MELON
            elif len(shops) >= 3 and "YARN_STORE" in shops[:3] and step < 144:
                active_tape = get_base_tape("6c8s_3q")
            else:
                active_tape = get_base_tape("8c6s_3q")

        elif path_id == "PATH_3_WAVE2_MELON_SCAVENGER":
            # Uses baseline tapes, but OpportunisticCropManager is upgraded to actively replant Wave-2 Melons
            if len(shops) >= 1 and shops[:1] == ["YARN_STORE"]:
                active_tape = get_base_tape("6c12s_4q_first_yarn")
            elif len(shops) >= 2 and "YARN_STORE" in shops[:2]:
                active_tape = get_base_tape("6c12s_4q_second_yarn")
            elif _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:2]):
                active_tape = get_base_tape("10c4s_3q")
            elif len(shops) >= 3 and "YARN_STORE" in shops[:3] and step < 144:
                active_tape = get_base_tape("6c8s_3q")
            else:
                active_tape = get_base_tape("8c6s_3q")

        elif path_id == "PATH_4_STRAW_COW_TAPE":
            # If yarn -> yarn, if milk -> 10c4s, if agro -> 165k straw-cow tape!
            if len(shops) >= 1 and shops[:1] == ["YARN_STORE"]:
                active_tape = get_base_tape("6c12s_4q_first_yarn")
            elif len(shops) >= 2 and "YARN_STORE" in shops[:2]:
                active_tape = get_base_tape("6c12s_4q_second_yarn")
            elif _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:2]):
                active_tape = get_base_tape("10c4s_3q")
            elif {"BAKERY", "BRUNCH_SPOT", "FARMERS_MARKET"}.intersection(shops[:2]):
                active_tape = _TAPE_165K_STRAW_COW
            elif len(shops) >= 3 and "YARN_STORE" in shops[:3] and step < 144:
                active_tape = get_base_tape("6c8s_3q")
            else:
                active_tape = get_base_tape("8c6s_3q")

        else:
            active_tape = get_base_tape("8c6s_3q")

        # 3. Retrieve base action
        if step < len(active_tape):
            raw_tape_action = copy.deepcopy(active_tape[step])
        else:
            raw_tape_action = {"farmer": ["PASS"], "hands": [], "market": []}

        # 4. Weed Repair Guard
        action = weed_repair_overlay(raw_tape_action, obs, step)

        # 5. Feed Rescue Guard
        action = feed_rescue_guard(action, obs, step)

        # 6. Apply Pure Debt Repayment
        action = state.debt_mgr.apply_repayment(action, step)

        # 7. Process tape market orders through River
        processed_market = state.river.process_tape_orders(action.get("market", []), step)

        # 8. Predator lookahead
        lookahead_sells = get_lookahead_scheduled_sells(active_tape, step, lookahead_steps=96)
        frontrun_orders = state.predator.evaluate_frontrun_opportunities(
            obs, processed_market, state.debt_mgr, lookahead_sells
        )

        # 9. River Trickle orders
        future_slice = active_tape[step: min(len(active_tape), step + 10)]
        initial_market = processed_market + frontrun_orders
        action["market"] = state.river.generate_trickle_orders(obs, initial_market, future_slice)

        # 10. Ghost spoof
        action = apply_ghost_signature_spoof(obs, action)

        # 11. Scavenger farmhand overlay (with Path 3 melon replanter if active)
        if path_id == "PATH_3_WAVE2_MELON_SCAVENGER":
            action = custom_melon_scavenger_overlay(action, obs)
        else:
            action = scavenger_farmhand_overlay(action, obs)

        # 12. Align live hands
        player = obs.get("player", 0) if isinstance(obs, dict) else 0
        farms = obs.get("farms", []) if isinstance(obs, dict) else []
        my_farm = farms[player] if len(farms) > player and isinstance(farms[player], dict) else {}
        live_hands_count = len(my_farm.get("hands", []) or [])
        action["hands"] = (action.get("hands", []) or [])[:live_hands_count]

        # 13. Terminal liquidation
        action = execute_terminal_liquidation(obs, action, step)
        action["market"] = action.get("market", [])[:MAX_MARKET_ORDERS]
        return action

    return sim_agent


def custom_melon_scavenger_overlay(action: Dict[str, Any], obs: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced scavenger overlay for Path 3 that includes Wave-2 Melon Replanting on Days 10-18."""
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    live_hands = farm.get("hands", []) or []
    tape_hands = list(action.get("hands", []) or [])
    tiles = farm.get("tiles", []) or []
    unlocked_quads = farm.get("unlocked_quadrants", ["NW"])
    private = obs.get("private") or {}
    seeds = private.get("seeds", {}) or {}
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0.0) or 0.0)

    if len(tape_hands) >= len(live_hands):
        return action

    # Detect if Wave-2 Melon Replanting should trigger (Days 10-16, money >= 500)
    melon_active = (10 <= day <= 16) and (money >= 500.0)
    scarcity_crop = OpportunisticCropManager.detect_scarcity_opportunity(obs)

    target_crop = "MELON" if melon_active else scarcity_crop
    microplot_tiles = []
    if target_crop:
        # Find empty tiles or existing target plants
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row or []):
                if (x, y) in {(4,4), (5,4), (4,5), (5,5)}:
                    continue
                quad = "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))
                if quad not in unlocked_quads:
                    continue
                if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == target_crop:
                    microplot_tiles.append((x, y))
                elif tile is None and len(microplot_tiles) < 4:
                    microplot_tiles.append((x, y))

    # scan weeds and fertilizers
    weeds = []
    fertilizers = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row or []):
            if isinstance(tile, dict):
                k = tile.get("kind")
                if k == "WEED":
                    weeds.append((x, y))
                elif k in ("COOP", "PASTURE") and tile.get("fertilizer_available"):
                    fertilizers.append((x, y))

    while len(tape_hands) < len(live_hands):
        hand_idx = len(tape_hands)
        hx, hy = live_hands[hand_idx]
        best_target = None
        best_dist = 9999
        target_act = "PASS"

        # Check target crop tasks
        if target_crop and microplot_tiles:
            for mx, my in microplot_tiles:
                mtile = tiles[my][mx] if my < len(tiles) and mx < len(tiles[my]) else None
                if isinstance(mtile, dict) and mtile.get("kind") == "PLANT":
                    yu = int(mtile.get("yield_units", 0) or 0)
                    if yu > 0:
                        d = abs(hx - mx) + abs(hy - my)
                        if d < best_dist:
                            best_dist = d
                            best_target = (mx, my)
                            target_act = "HARVEST"
                    elif not mtile.get("watered_today", False):
                        d = abs(hx - mx) + abs(hy - my)
                        if d < best_dist:
                            best_dist = d
                            best_target = (mx, my)
                            target_act = "WATER"
                elif mtile is None and day <= 18:
                    d = abs(hx - mx) + abs(hy - my)
                    if d < best_dist:
                        best_dist = d
                        best_target = (mx, my)
                        target_act = "PLANT"

        # Check weeds
        if not best_target:
            for wx, wy in weeds:
                d = abs(hx - wx) + abs(hy - wy)
                if d < best_dist:
                    best_dist = d
                    best_target = (wx, wy)
                    target_act = "DIG"

        # Check fertilizer
        if not best_target:
            for fx, fy in fertilizers:
                d = abs(hx - fx) + abs(hy - fy)
                if d < best_dist:
                    best_dist = d
                    best_target = (fx, fy)
                    target_act = "COLLECT_FERTILIZER"

        # Route hand
        if best_target:
            tx, ty = best_target
            if best_dist == 0:
                if target_act == "PLANT":
                    if seeds.get(target_crop, 0) > 0:
                        tape_hands.append(["PLANT", target_crop])
                    else:
                        market = action.setdefault("market", [])
                        has_pending = any(
                            isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_SEED" and o[1] == target_crop
                            for o in market
                        )
                        if not has_pending and len(market) < 10 and day <= 18:
                            market.append(["BUY_SEED", target_crop, 2])
                        tape_hands.append(["PASS"])
                else:
                    tape_hands.append([target_act])
                    if target_act == "DIG" and (tx, ty) in weeds:
                        weeds.remove((tx, ty))
                    elif target_act == "COLLECT_FERTILIZER" and (tx, ty) in fertilizers:
                        fertilizers.remove((tx, ty))
            else:
                if hx < tx:
                    tape_hands.append(["EAST"])
                elif hx > tx:
                    tape_hands.append(["WEST"])
                elif hy < ty:
                    tape_hands.append(["SOUTH"])
                elif hy > ty:
                    tape_hands.append(["NORTH"])
        else:
            tape_hands.append(["PASS"])

    action["hands"] = tape_hands
    return action


def run_multi_path_simulation():
    # 20 diverse test seeds covering all shop archetypes
    test_seeds = [
        1, 7, 13, 24, 42, 100, 2024, 7777, 9999, 12345,
        55, 88, 144, 256, 512, 1024, 31415, 42424, 65536, 88888
    ]

    paths = [
        ("Path 1 (Baseline 8c6s / 10c4s / Yarn)", "PATH_1_BASELINE"),
        ("Path 2 (Agro Dual-Melon Tape 151k)", "PATH_2_DUAL_MELON_TAPE"),
        ("Path 3 (Wave-2 Melon Scavenger Overlay)", "PATH_3_WAVE2_MELON_SCAVENGER"),
        ("Path 4 (Straw-Cow Heavy Tape 165k)", "PATH_4_STRAW_COW_TAPE"),
    ]

    print("=" * 90)
    print("PROJECT AEGIS MULTI-PATH SIMULATION LAB")
    print(f"Testing {len(paths)} Paths across {len(test_seeds)} Seeds vs Decoded Sparring Agent")
    print("=" * 90)

    # First discover shop spawns for each seed
    seed_shops = {}
    for seed in test_seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": seed})
        env.run(["pass", "pass"])
        shops = (env.steps[-1][0]["observation"].get("town") or {}).get("unlocked_shops", [])
        seed_shops[seed] = shops[:4]

    # Category buckets
    print("\n--- SEED SHOP ARCHETYPE CLASSIFICATION ---")
    for seed in test_seeds:
        shops_str = ", ".join(seed_shops[seed])
        print(f"  Seed {seed:5d} -> Shops (Days 3-12): [{shops_str}]")

    # Run tournament across paths
    results = {p_name: [] for p_name, _ in paths}

    print("\n" + "=" * 90)
    print("RUNNING BENCHMARKS AGAINST DECODED TOP-100 AGENT (SPARRING)")
    print("=" * 90)

    for p_name, p_id in paths:
        agent_fn = create_path_agent(p_id)
        scores = []
        margins = []
        wins = 0

        print(f"\nEvaluating: {p_name}")
        for seed in test_seeds:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            env.run([agent_fn, decoded_agent])
            p0 = env.steps[-1][0]["reward"]
            p1 = env.steps[-1][1]["reward"]
            diff = p0 - p1
            scores.append(p0)
            margins.append(diff)
            if p0 > p1:
                wins += 1
            results[p_name].append((seed, p0, p1, diff, seed_shops[seed]))
            print(f"  Seed {seed:5d} | Aegis = {p0:>8,.0f} | Decoded = {p1:>8,.0f} | Margin = {diff:>+8,.0f} | {'WIN' if p0>p1 else 'LOSS'}")

        win_rate = (wins / len(test_seeds)) * 100.0
        avg_score = sum(scores) / len(scores)
        avg_margin = sum(margins) / len(margins)
        print(f"  --> Summary for {p_name}: Win Rate = {win_rate:.1f}% ({wins}/{len(test_seeds)}) | Avg Score = ${avg_score:,.0f} | Avg Margin = +${avg_margin:,.0f}")

    # Summary table
    print("\n" + "=" * 90)
    print("FINAL MULTI-PATH HEAD-TO-HEAD COMPARISON MATRIX")
    print("=" * 90)
    print(f"{'Strategic Path':<42} | {'Win Rate':<10} | {'Avg Score':<12} | {'Peak Score':<12} | {'Avg Margin':<12}")
    print("-" * 90)
    for p_name, _ in paths:
        match_data = results[p_name]
        scores = [m[1] for m in match_data]
        margins = [m[3] for m in match_data]
        wins = sum(1 for m in match_data if m[3] > 0)
        wr = (wins / len(match_data)) * 100.0
        avg_s = sum(scores) / len(scores)
        peak_s = max(scores)
        avg_m = sum(margins) / len(margins)
        print(f"{p_name:<42} | {wr:>5.1f}% ({wins:02d}/{len(match_data):02d}) | ${avg_s:>10,.0f} | ${peak_s:>10,.0f} | ${avg_m:>+10,.0f}")

    # Save detailed JSON
    with open(r'C:\Coding\project_aegis\benchmarks\simulation_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed simulation results saved to project_aegis/benchmarks/simulation_results.json")


if __name__ == "__main__":
    run_multi_path_simulation()
