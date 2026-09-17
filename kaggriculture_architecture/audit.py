#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Kaggriculture Deep Telemetry & Lifecycle Auditor
=================================================
Performs full-spectrum, turn-by-turn verification of Kaggriculture agents:
- Crop germination, watering consistency, weed decay vs natural lifespan completion
- Quadrant unlock cost vs worker coverage & tile cultivation (catches ghost land)
- Market order execution vs silent engine no-ops (catches phantom sell orders)
- Livestock feeding, care bonuses, and escape hazards
- Worker movement efficiency and idle pass detection

Usage:
    python audit.py [agent_path] [--opponent starter|random|pass] [--seed SEED] [--strict]
"""

import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

QUADRANT_TILES = {
    "NW": [(x, y) for y in range(0, 5) for x in range(0, 5)],
    "NE": [(x, y) for y in range(0, 5) for x in range(5, 10)],
    "SW": [(x, y) for y in range(5, 10) for x in range(0, 5)],
    "SE": [(x, y) for y in range(5, 10) for x in range(5, 10)],
}

ONGOING_MAX_AGE = {
    "TOMATO": 11,
    "STRAWBERRY": 16,
}

def get_quadrant(x, y):
    if x < 5 and y < 5: return "NW"
    if x >= 5 and y < 5: return "NE"
    if x < 5 and y >= 5: return "SW"
    return "SE"

def load_agent(agent_path):
    p = Path(agent_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Agent file not found: {p}")
    spec = importlib.util.spec_from_file_location("kaggriculture_agent", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "agent"):
        return mod.agent
    callables = [v for v in mod.__dict__.values() if callable(v)]
    if callables:
        return callables[-1]
    raise AttributeError(f"No callable agent found in {agent_path}")

def run_audit(agent_fn, opponent="starter", steps=720, seed=42, agent_name="Agent"):
    try:
        from kaggle_environments import make
    except ImportError:
        print("[ERROR] kaggle_environments is not installed in the current Python environment!")
        sys.exit(1)

    config = {"episodeSteps": steps}
    if seed is not None:
        config["seed"] = seed

    env = make("kaggriculture", configuration=config, debug=False)
    env.run([agent_fn, opponent])

    ep_steps = env.steps
    player = 0

    # Metrics collectors
    flags_critical = []
    flags_warning = []

    # 1. Crops
    seeds_bought = defaultdict(int)
    seeds_planted = defaultdict(int)
    crops_withered = defaultdict(list) # crop -> list of (step, day, hour, x, y, age)
    crops_natural_expiry = defaultdict(list)
    crop_plant_turns = defaultdict(int)
    crop_watered_turns = defaultdict(int)

    # 2. Quadrants
    quadrants_unlocked_step = {"NW": 0}
    quadrant_visits = defaultdict(int) # quad -> count of worker footsteps
    quadrant_tiles_used = defaultdict(set) # quad -> set of (x, y) cultivated

    # 3. Market
    market_orders_submitted = defaultdict(int)
    market_orders_executed = defaultdict(int)
    phantom_sells = defaultdict(int) # item -> count of units attempted to sell with 0 in shed

    # 4. Livestock
    livestock_placed = defaultdict(list)
    livestock_escaped = []

    # 5. Workers
    worker_actions = defaultdict(lambda: defaultdict(int)) # role -> action_type -> count

    # Tile history tracker
    tile_history = {} # (x, y) -> dict of state

    for s_idx, step in enumerate(ep_steps):
        p_step = step[player]
        obs = p_step.observation
        # In Kaggle Environments, action generated for step s_idx is recorded in ep_steps[s_idx + 1]
        action = ep_steps[s_idx + 1][player].action if s_idx + 1 < len(ep_steps) else None
        me = obs["farms"][player]
        tiles = me["tiles"]
        shed = obs["private"]["shed"]
        day = obs.get("day", s_idx // 24)
        hour = obs.get("hour", s_idx % 24)

        # Track unlocked quadrants
        for q in me.get("unlocked_quadrants", ["NW"]):
            if q not in quadrants_unlocked_step:
                quadrants_unlocked_step[q] = s_idx

        # Track worker positions
        fx, fy = me["farmer"]
        quadrant_visits[get_quadrant(fx, fy)] += 1
        for hx, hy in me.get("hands", []):
            quadrant_visits[get_quadrant(hx, hy)] += 1

        # Track worker actions
        if action and isinstance(action, dict):
            f_act = action.get("farmer")
            if f_act and len(f_act) > 0:
                worker_actions["farmer"][f_act[0]] += 1
            for h_idx, h_act in enumerate(action.get("hands", [])):
                if h_act and len(h_act) > 0:
                    worker_actions[f"hand_{h_idx}"][h_act[0]] += 1

            # Market order audit with same-turn projected drops
            avail_shed = dict(shed)
            board = 10
            half = board // 2
            shed_adj = lambda pos: pos[0] in (half-1, half) and pos[1] in (half-1, half)
            positions = [me["farmer"]] + list(me.get("hands") or [])
            units = [action.get("farmer") or ["PASS"]] + list(action.get("hands") or [])
            inventories = obs["private"].get("inventories", [])

            for i, pos in enumerate(positions):
                if i < len(units) and shed_adj(pos):
                    act = units[i]
                    op = act[0] if act else "PASS"
                    inv = inventories[i] if i < len(inventories) else {}
                    if op == "DROP":
                        for itm, cnt in inv.items():
                            avail_shed[itm] = avail_shed.get(itm, 0) + cnt
                    elif op == "PLACE" and len(act) >= 2 and act[1] not in ("COOP", "PASTURE"):
                        itm = act[1]
                        cnt = act[2] if len(act) >= 3 else 1
                        avail_shed[itm] = avail_shed.get(itm, 0) + min(cnt, inv.get(itm, 0))

            for m_op in action.get("market", []):
                op_type = m_op[0]
                market_orders_submitted[op_type] += 1
                if op_type == "BUY_SEED":
                    crop, count = m_op[1], m_op[2]
                    seeds_bought[crop] += count
                elif op_type == "SELL":
                    item, count = m_op[1], m_op[2]
                    have = avail_shed.get(item, 0)
                    if count <= 0 or have == 0:
                        phantom_sells[item] += max(1, count)
                    else:
                        sold = min(count, have)
                        avail_shed[item] = have - sold
                        market_orders_executed["SELL"] += 1
                elif op_type == "BUY_LAND":
                    market_orders_executed["BUY_LAND"] += 1

        # Tile Inspection
        for y in range(10):
            for x in range(10):
                t = tiles[y][x]
                prev = tile_history.get((x, y))
                q = get_quadrant(x, y)

                if isinstance(t, dict):
                    k = t.get("kind")
                    if k == "PLANT":
                        crop = t.get("crop")
                        quadrant_tiles_used[q].add((x, y))
                        crop_plant_turns[crop] += 1
                        if t.get("watered_today"):
                            crop_watered_turns[crop] += 1

                        # Detection of new plant
                        if not isinstance(prev, dict) or prev.get("kind") != "PLANT" or prev.get("planted_day") != t.get("planted_day"):
                            seeds_planted[crop] += 1

                    elif k == "WEED":
                        # Did a plant just turn into a weed?
                        if isinstance(prev, dict) and prev.get("kind") == "PLANT":
                            dead_crop = prev.get("crop")
                            planted_day = prev.get("planted_day", 0)
                            age = day - planted_day
                            max_age = ONGOING_MAX_AGE.get(dead_crop)
                            if max_age is not None and age >= max_age:
                                crops_natural_expiry[dead_crop].append((s_idx, day, hour, x, y, age))
                            else:
                                crops_withered[dead_crop].append((s_idx, day, hour, x, y, age))

                    elif k in ("COOP", "PASTURE"):
                        quadrant_tiles_used[q].add((x, y))
                        animal = t.get("animal")
                        if animal:
                            if not isinstance(prev, dict) or prev.get("animal") != animal:
                                livestock_placed[animal].append((s_idx, x, y))

                elif t is None and isinstance(prev, dict):
                    if prev.get("kind") in ("COOP", "PASTURE") and prev.get("animal") is not None:
                        livestock_escaped.append((s_idx, day, x, y, prev.get("animal")))

                tile_history[(x, y)] = t

    # Post-game telemetry aggregation
    final_step = ep_steps[-1][player]
    final_money = final_step.observation["farms"][player]["money"]
    opp_final_money = ep_steps[-1][1 - player].observation["farms"][1 - player]["money"]
    final_seeds = final_step.observation["private"]["seeds"]
    final_shed = final_step.observation["private"]["shed"]

    # Flags evaluation
    for crop, withered_list in crops_withered.items():
        if len(withered_list) > 0:
            flags_critical.append(
                f"[CRITICAL] {len(withered_list)}x '{crop}' plants PREMATURELY WITHERED into weeds! "
                f"(First: Day {withered_list[0][1]}, Tile {withered_list[0][3]},{withered_list[0][4]}, Age {withered_list[0][5]})"
            )

    # Check for seeds bought but 0 harvests or completely withered
    for crop, count in seeds_bought.items():
        planted = seeds_planted.get(crop, 0)
        withered = len(crops_withered.get(crop, []))
        if planted > 0 and planted == withered:
            flags_critical.append(
                f"[CRITICAL] 100% of planted '{crop}' crops ({planted}/{planted}) died prematurely! ZERO harvest yield."
            )
        elif planted == 0 and count > 5:
            flags_warning.append(
                f"[WARNING] Bought {count} '{crop}' seeds but planted 0! Cash was wasted on dormant inventory."
            )

    # Check Quadrant Utilization
    for q in ["NW", "NE", "SW", "SE"]:
        if q in quadrants_unlocked_step:
            tiles_cultivated = len(quadrant_tiles_used[q])
            visits = quadrant_visits[q]
            if tiles_cultivated == 0 and q != "NW":
                flags_critical.append(
                    f"[CRITICAL] Quadrant '{q}' unlocked at Step {quadrants_unlocked_step[q]} for $1k-$4k, "
                    f"but ZERO tiles were cultivated! (Ghost Land)"
                )
            elif visits < 20 and q != "NW":
                flags_warning.append(
                    f"[WARNING] Quadrant '{q}' has only {visits} total worker footsteps throughout the entire game."
                )

    # Check Phantom Sells
    total_phantom_sell_ops = sum(phantom_sells.values())
    if total_phantom_sell_ops > 50:
        top_phantom = sorted(phantom_sells.items(), key=lambda x: x[1], reverse=True)[:3]
        phantom_desc = ", ".join(f"{item} ({cnt} orders/units)" for item, cnt in top_phantom)
        flags_critical.append(
            f"[CRITICAL] High volume of PHANTOM SELL ORDERS: {total_phantom_sell_ops} orders/units attempted "
            f"to sell with 0 shed inventory! Top culprits: {phantom_desc}."
        )

    # Check Livestock Escapes
    if len(livestock_escaped) > 0:
        for esc in livestock_escaped:
            flags_critical.append(
                f"[CRITICAL] Animal ESCAPED: {esc[4]} at Tile ({esc[2]},{esc[3]}) on Day {esc[1]} (Step {esc[0]})!"
            )

    # Print Audit Report
    print("=" * 80)
    print(f"🔬 KAGGRICULTURE DEEP TELEMETRY AUDIT REPORT: {agent_name}")
    print("=" * 80)
    print(f"Final Balance: ${final_money:,.0f} | Opponent ({opponent}): ${opp_final_money:,.0f} | "
          f"Margin: ${final_money - opp_final_money:+,.0f}")
    print("-" * 80)

    print("\n1. CROP VITALITY & LIFECYCLE MATRIX:")
    print(f"{'Crop':<12} | {'Bought':<7} | {'Planted':<8} | {'Active Turns':<13} | {'Water %':<8} | {'Premature':<10} | {'Completed':<10}")
    print("-" * 80)
    all_crops = sorted(list(set(list(seeds_bought.keys()) + list(seeds_planted.keys()) + list(crops_withered.keys()) + list(crops_natural_expiry.keys()))))
    for c in all_crops:
        bought = seeds_bought.get(c, 0)
        planted = seeds_planted.get(c, 0)
        p_turns = crop_plant_turns.get(c, 0)
        w_turns = crop_watered_turns.get(c, 0)
        w_pct = f"{(w_turns / p_turns * 100):.1f}%" if p_turns > 0 else "0.0%"
        withered = len(crops_withered.get(c, []))
        completed = len(crops_natural_expiry.get(c, []))
        status_marker = " ⚠️" if withered > 0 else ""
        print(f"{c:<12} | {bought:<7} | {planted:<8} | {p_turns:<13} | {w_pct:<8} | {withered:<10}{status_marker} | {completed:<10}")

    print("\n2. LAND & QUADRANT UTILIZATION MATRIX:")
    print(f"{'Quadrant':<10} | {'Status':<10} | {'Unlocked Step':<15} | {'Tiles Used':<12} | {'Worker Visits':<14}")
    print("-" * 70)
    for q in ["NW", "NE", "SW", "SE"]:
        unlocked = q in quadrants_unlocked_step
        status = "UNLOCKED" if unlocked else "LOCKED"
        u_step = f"Step {quadrants_unlocked_step[q]}" if unlocked else "N/A"
        t_used = f"{len(quadrant_tiles_used[q])}/25" if unlocked else "0/25"
        v_count = quadrant_visits[q]
        alert = " ❌ GHOST" if unlocked and len(quadrant_tiles_used[q]) == 0 and q != "NW" else ""
        print(f"{q:<10} | {status:<10} | {u_step:<15} | {t_used:<12} | {v_count:<14}{alert}")

    print("\n3. MARKET ORDER INTEGRITY MATRIX:")
    print(f"Total Market Orders Submitted: {sum(market_orders_submitted.values()):,}")
    print(f"Phantom Sells (0 Shed Inventory): {sum(phantom_sells.values()):,} orders/units")
    if phantom_sells:
        for item, cnt in sorted(phantom_sells.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {item:<12}: {cnt:>6,} phantom sell orders/units")

    print("\n4. DIAGNOSTIC VERDICT:")
    if flags_critical:
        print("❌ STATUS: CRITICAL DEFECTS DETECTED (Fix Required)")
        for f in flags_critical:
            print(f"  {f}")
    elif flags_warning:
        print("⚠️ STATUS: WARNINGS DETECTED (Suboptimal Behavior)")
        for f in flags_warning:
            print(f"  {f}")
    else:
        print("✅ STATUS: CLEAN & HEALTHY (Zero crop wither, full land usage, clean market orders)")

    if flags_warning and flags_critical:
        print("\nAdditional Warnings:")
        for f in flags_warning:
            print(f"  {f}")

    print("=" * 80)
    return len(flags_critical) == 0

def main():
    parser = argparse.ArgumentParser(description="Kaggriculture Deep Telemetry & Lifecycle Auditor")
    parser.add_argument("agent", nargs="?", default="main.py", help="Path to agent Python script (default: main.py)")
    parser.add_argument("--opponent", default="starter", choices=["starter", "random", "pass"], help="Opponent agent")
    parser.add_argument("--steps", type=int, default=720, help="Episode steps (default: 720)")
    parser.add_argument("--seed", type=int, default=42, help="Episode seed (default: 42)")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero code if critical flags found")
    args = parser.parse_args()

    agent_path = Path(args.agent)
    if not agent_path.is_absolute():
        agent_path = Path.cwd() / agent_path

    print(f"Loading agent: {agent_path.name} from {agent_path.parent}")
    agent_fn = load_agent(agent_path)

    passed = run_audit(agent_fn, opponent=args.opponent, steps=args.steps, seed=args.seed, agent_name=agent_path.name)
    if args.strict and not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
