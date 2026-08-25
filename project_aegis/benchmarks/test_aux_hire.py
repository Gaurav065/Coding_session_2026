import json
import sys
import copy

sys.path.insert(0, r'C:\Coding')
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
from project_aegis.ghost import apply_ghost_signature_spoof, scavenger_farmhand_overlay, OpportunisticCropManager
from project_aegis.guards import weed_repair_overlay, feed_rescue_guard
from project_aegis.tape_loader import select_active_tape, get_lookahead_scheduled_sells

_AUX_STATES = {}
def aux_hire_agent(obs):
    seat = obs.get("player", 0) if isinstance(obs, dict) else 0
    if seat not in _AUX_STATES:
        class State:
            def __init__(self):
                self.debt_mgr = PureDebtManager()
                self.shed_estimator = OpponentShedEstimator()
                self.predator = PredatorEngine(self.shed_estimator)
                self.river = RiverEngine()
                self.last_step = -1
        _AUX_STATES[seat] = State()
    st = _AUX_STATES[seat]
    step = obs.get("step", 0)
    hour = obs.get("hour", 0)
    day = obs.get("day", 0)
    player = obs.get("player", 0)
    farms = obs.get("farms", [])
    my_farm = farms[player] if len(farms) > player else {}
    money = float(my_farm.get("money", 0.0) or 0.0)
    
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
    
    # Check if we should hire 1 extra auxiliary farmhand on hour 0 for days 4-22
    if hour == 0 and 4 <= day <= 22 and money >= 600.0:
        hires_today = my_farm.get("hires_today", 0)
        # only add HIRE if market has space
        if len(initial_market) < 10 and not any(isinstance(o, list) and o[0] == "HIRE" for o in initial_market):
            initial_market.append(["HIRE"])
            
    action["market"] = st.river.generate_trickle_orders(obs, initial_market, future_slice)
    action = apply_ghost_signature_spoof(obs, action)
    action = scavenger_farmhand_overlay(action, obs)
    
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
print(f"{'Seed & Profile':<48} | {'Baseline Aegis':<15} | {'Aux-Hire Aegis':<18} | {'Delta':<10}")
print("=" * 90)

base_scores = []
aux_scores = []

for seed, prof in test_seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([baseline_agent, "starter"])
    p_base = env.steps[-1][0]["reward"]
    base_scores.append(p_base)

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([aux_hire_agent, "starter"])
    p_aux = env.steps[-1][0]["reward"]
    aux_scores.append(p_aux)

    delta = p_aux - p_base
    print(f"Seed {seed:05d}: {prof[:38]:<38} | ${p_base:>12,.0f} | ${p_aux:>15,.0f} | {delta:>+9,.0f}")

print("=" * 90)
print(f"{'AVERAGE SCORE':<48} | ${sum(base_scores)/len(base_scores):>12,.0f} | ${sum(aux_scores)/len(aux_scores):>15,.0f} | +${(sum(aux_scores)-sum(base_scores))/len(base_scores):>8,.0f}")
print(f"{'PEAK SCORE':<48} | ${max(base_scores):>12,.0f} | ${max(aux_scores):>15,.0f} | +${max(aux_scores)-max(base_scores):>8,.0f}")
print("=" * 90)
