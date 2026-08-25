import json
import sys
import copy

sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make
from project_aegis.main import agent as baseline_agent
from project_aegis.core import (
    PureDebtManager,
    execute_terminal_liquidation,
    safe_agent_fallback,
    MAX_MARKET_ORDERS,
)
from project_aegis.predator import PredatorEngine, OpponentShedEstimator
from project_aegis.river import RiverEngine
from project_aegis.ghost import apply_ghost_signature_spoof, OpportunisticCropManager
from project_aegis.guards import weed_repair_overlay, feed_rescue_guard
from project_aegis.tape_loader import select_active_tape, get_lookahead_scheduled_sells

# Wave-2 Melon Replanter Scavenger Overlay
def wave2_melon_scavenger_overlay(action, obs):
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

    # Detect scarcity opportunities:
    # 1. Tomato/Carrot predictive shop scarcity
    scarcity_crop = OpportunisticCropManager.detect_scarcity_opportunity(obs)
    
    # 2. Wave-2 Melon Replanter on Days 10-15 when money >= 600
    melon_opportunity = (10 <= day <= 15) and (money >= 600.0)
    
    target_crop = scarcity_crop if scarcity_crop else ("MELON" if melon_opportunity else None)
    
    microplot_tiles = []
    if target_crop:
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row or []):
                if (x, y) in {(4, 4), (5, 4), (4, 5), (5, 5)}:
                    continue
                quad = "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))
                if quad not in unlocked_quads:
                    continue
                if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == target_crop:
                    microplot_tiles.append((x, y))
                elif tile is None and len(microplot_tiles) < 4:
                    microplot_tiles.append((x, y))

    # Weeds & Fertilizer
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

        if not best_target:
            for wx, wy in weeds:
                d = abs(hx - wx) + abs(hy - wy)
                if d < best_dist:
                    best_dist = d
                    best_target = (wx, wy)
                    target_act = "DIG"

        if not best_target:
            for fx, fy in fertilizers:
                d = abs(hx - fx) + abs(hy - fy)
                if d < best_dist:
                    best_dist = d
                    best_target = (fx, fy)
                    target_act = "COLLECT_FERTILIZER"

        if best_target:
            tx, ty = best_target
            if best_dist == 0:
                if target_act == "PLANT":
                    if seeds.get(target_crop, 0) > 0:
                        tape_hands.append(["PLANT", target_crop])
                    else:
                        market = action.setdefault("market", [])
                        has_p = any(isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_SEED" and o[1] == target_crop for o in market)
                        if not has_p and len(market) < 10 and day <= 18:
                            market.append(["BUY_SEED", target_crop, 2])
                        tape_hands.append(["PASS"])
                else:
                    tape_hands.append([target_act])
                    if target_act == "DIG" and (tx, ty) in weeds:
                        weeds.remove((tx, ty))
                    elif target_act == "COLLECT_FERTILIZER" and (tx, ty) in fertilizers:
                        fertilizers.remove((tx, ty))
            else:
                if hx < tx: tape_hands.append(["EAST"])
                elif hx > tx: tape_hands.append(["WEST"])
                elif hy < ty: tape_hands.append(["SOUTH"])
                elif hy > ty: tape_hands.append(["NORTH"])
        else:
            tape_hands.append(["PASS"])

    action["hands"] = tape_hands
    return action

# Build Agent with Wave-2 Melon Replanter
_SIM_STATES = {}
def wave2_agent(obs):
    seat = obs.get("player", 0) if isinstance(obs, dict) else 0
    if seat not in _SIM_STATES:
        class State:
            def __init__(self):
                self.debt_mgr = PureDebtManager()
                self.shed_estimator = OpponentShedEstimator()
                self.predator = PredatorEngine(self.shed_estimator)
                self.river = RiverEngine()
                self.last_step = -1
        _SIM_STATES[seat] = State()
    st = _SIM_STATES[seat]
    step = obs.get("step", 0)
    if step == 0 or step < st.last_step:
        st.debt_mgr.reset_if_new_game(step)
        st.shed_estimator.reset_if_new_game(step)
        st.river = RiverEngine()
    st.last_step = step

    st.predator.update(obs)
    active_tape = select_active_tape(obs)
    if step < len(active_tape):
        raw_tape_action = copy.deepcopy(active_tape[step])
    else:
        raw_tape_action = {"farmer": ["PASS"], "hands": [], "market": []}

    action = weed_repair_overlay(raw_tape_action, obs, step)
    action = feed_rescue_guard(action, obs, step)
    action = st.debt_mgr.apply_repayment(action, step)
    processed_market = st.river.process_tape_orders(action.get("market", []), step)
    lookahead_sells = get_lookahead_scheduled_sells(active_tape, step, lookahead_steps=96)
    frontrun_orders = st.predator.evaluate_frontrun_opportunities(obs, processed_market, st.debt_mgr, lookahead_sells)
    future_slice = active_tape[step: min(len(active_tape), step + 10)]
    initial_market = processed_market + frontrun_orders
    action["market"] = st.river.generate_trickle_orders(obs, initial_market, future_slice)
    action = apply_ghost_signature_spoof(obs, action)
    action = wave2_melon_scavenger_overlay(action, obs)
    
    player = obs.get("player", 0) if isinstance(obs, dict) else 0
    farms = obs.get("farms", []) if isinstance(obs, dict) else []
    my_farm = farms[player] if len(farms) > player and isinstance(farms[player], dict) else {}
    live_hands_count = len(my_farm.get("hands", []) or [])
    action["hands"] = (action.get("hands", []) or [])[:live_hands_count]
    action = execute_terminal_liquidation(obs, action, step)
    action["market"] = action.get("market", [])[:MAX_MARKET_ORDERS]
    return action

test_seeds = [
    (1, "Farmers Mkt x2 + Bakery (Extreme Crop Demand)"),
    (7, "Smoothie + Ice Cream + Pizza (Triple Milk Surge)"),
    (13, "Yarn Store Day 3 (Wool 2x Surge)"),
    (24, "Smoothie + Pizza x2 (Triple Milk Surge)"),
    (55, "Pet Cafe x2 + Farmers Mkt (Carrots 24/day)"),
    (100, "Farmers Mkt + Bakery (Wheat/Egg/Carrot/Melon)"),
    (144, "Bakery + Brunch x2 (Extreme Wheat/Egg/Straw)"),
    (1024, "Bakery x2 + Yarn Day 9 (Wheat + Late Wool)"),
    (65536, "Bakery + Ice Cream x2 (Milk + Straw + Wheat)"),
    (88888, "Pizza + Ice Cream + Farmers Mkt (Milk + Tomato + Straw)"),
]

print("=" * 90)
print(f"{'Seed & Profile':<48} | {'Baseline Aegis':<15} | {'Wave-2 Melon Aegis':<18} | {'Delta':<10}")
print("=" * 90)

base_scores = []
wave2_scores = []

for seed, prof in test_seeds:
    # Baseline
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([baseline_agent, "starter"])
    p_base = env.steps[-1][0]["reward"]
    base_scores.append(p_base)

    # Wave-2
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([wave2_agent, "starter"])
    p_w2 = env.steps[-1][0]["reward"]
    wave2_scores.append(p_w2)

    delta = p_w2 - p_base
    print(f"Seed {seed:05d}: {prof[:38]:<38} | ${p_base:>12,.0f} | ${p_w2:>15,.0f} | {delta:>+9,.0f}")

print("=" * 90)
print(f"{'AVERAGE SCORE':<48} | ${sum(base_scores)/len(base_scores):>12,.0f} | ${sum(wave2_scores)/len(wave2_scores):>15,.0f} | +${(sum(wave2_scores)-sum(base_scores))/len(base_scores):>8,.0f}")
print(f"{'PEAK SCORE':<48} | ${max(base_scores):>12,.0f} | ${max(wave2_scores):>15,.0f} | +${max(wave2_scores)-max(base_scores):>8,.0f}")
print("=" * 90)
