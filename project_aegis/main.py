"""Project Aegis: Master Competitive Agent for Kaggriculture

Architecture:
- Mathematically optimized base tapes with multi-route town shop selection.
- Dynamic Opponent Shed Forensics & Front-Running (The Predator).
- Scaled Continuous Trickle-Selling, Liquidity Guard & Hard Pressure Valve (The River).
- Zero In-Memory Tape Mutation via Pure Debt Accounting.
- Non-Spatial Signature Spoofing (The Ghost Protocol).
- Weed Repair and Feed Rescue Execution Guards.
- Unscripted Farmhand Coordination (Scavenger Overlay).
- Guaranteed Terminal Liquidation (Steps 716-720).
- Universal Exception Safety Wrapper.
"""

import copy
from typing import Dict, Any, List

from project_aegis.core import (
    PureDebtManager,
    execute_terminal_liquidation,
    safe_agent_fallback,
    MAX_MARKET_ORDERS,
)
from project_aegis.predator import PredatorEngine, OpponentShedEstimator
from project_aegis.river import RiverEngine
from project_aegis.guards import weed_repair_overlay, feed_rescue_guard
from project_aegis.ghost import (
    apply_ghost_signature_spoof,
    scavenger_farmhand_overlay,
    schedule_auxiliary_farmhand_hire,
    OpportunisticCropManager,
)
from project_aegis.tape_loader import select_active_tape, get_lookahead_scheduled_sells


class AegisAgentState:
    def __init__(self):
        self.debt_mgr = PureDebtManager()
        self.shed_estimator = OpponentShedEstimator()
        self.predator = PredatorEngine(self.shed_estimator)
        self.river = RiverEngine()
        self.last_step = -1

    def reset_if_new_game(self, step: int):
        if step == 0 or step < self.last_step:
            self.debt_mgr.reset_if_new_game(step)
            self.shed_estimator.reset_if_new_game(step)
            self.river = RiverEngine()
        self.last_step = step


_AEGIS_STATES: Dict[int, AegisAgentState] = {}

def _get_seat_state(obs: Dict[str, Any]) -> AegisAgentState:
    seat = obs.get("player", 0) if isinstance(obs, dict) else 0
    if seat not in _AEGIS_STATES:
        _AEGIS_STATES[seat] = AegisAgentState()
    return _AEGIS_STATES[seat]


def _aegis_core_step(obs: Dict[str, Any]) -> Dict[str, Any]:
    step = obs.get("step", 0)
    state = _get_seat_state(obs)
    state.reset_if_new_game(step)

    # 1. Update forensic model of opponent
    state.predator.update(obs)

    # 2. Select active base route (adapting to Town Shop rolls)
    active_tape = select_active_tape(obs)

    # 3. Retrieve base action for this step
    if step < len(active_tape):
        raw_tape_action = copy.deepcopy(active_tape[step])
    else:
        raw_tape_action = {"farmer": ["PASS"], "hands": [], "market": []}

    # 4. Weed Repair Guard (dynamically clear random weeds on action tiles)
    action = weed_repair_overlay(raw_tape_action, obs, step)

    # 5. Feed Rescue Guard (emergency wheat feed buy if animals unfed at hour 18+)
    action = feed_rescue_guard(action, obs, step)

    # 6. Apply Pure Debt Repayment (intercepts scheduled sales to repay prior front-runs)
    action = state.debt_mgr.apply_repayment(action, step)

    # 7. Process tape market orders through River
    processed_market = state.river.process_tape_orders(action.get("market", []), step)

    # 8. Evaluate Predator front-running opportunities
    lookahead_sells = get_lookahead_scheduled_sells(active_tape, step, lookahead_steps=96)
    frontrun_orders = state.predator.evaluate_frontrun_opportunities(
        obs, processed_market, state.debt_mgr, lookahead_sells
    )

    # 9. Generate scaled trickle sales & enforce Liquidity Guard
    future_slice = active_tape[step: min(len(active_tape), step + 10)]
    initial_market = processed_market + frontrun_orders
    action["market"] = state.river.generate_trickle_orders(obs, initial_market, future_slice)

    # 10. Apply Ghost Protocol signature spoofing on Step 0
    action = apply_ghost_signature_spoof(obs, action)

    # 11. Schedule auxiliary scavenger farmhand on morning Hour 0
    scarcity_active = OpportunisticCropManager.detect_scarcity_opportunity(obs) is not None
    action = schedule_auxiliary_farmhand_hire(action, obs, scarcity_active=scarcity_active)

    # 12. Scavenge unscripted farmhands for weeds, fertilizer, and scarcity/Wave-2 crops
    action = scavenger_farmhand_overlay(action, obs, active_tape=active_tape, step=step)

    # 12. Align hands count strictly to live hands
    player = obs.get("player", 0) if isinstance(obs, dict) else 0
    farms = obs.get("farms", []) if isinstance(obs, dict) else []
    my_farm = farms[player] if len(farms) > player and isinstance(farms[player], dict) else {}
    live_hands_count = len(my_farm.get("hands", []) or [])
    action["hands"] = (action.get("hands", []) or [])[:live_hands_count]

    # 13. Execute terminal liquidation in the final turns
    action = execute_terminal_liquidation(obs, action, step)

    # Truncate market orders at max 10
    action["market"] = action.get("market", [])[:MAX_MARKET_ORDERS]

    return action


def agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    try:
        return _aegis_core_step(obs)
    except Exception:
        return safe_agent_fallback(obs)
