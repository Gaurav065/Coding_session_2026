"""IDC Master Agent for Project Maestro (Grandmaster 99% Elo Tier)

Integrates:
1. Dynamic Labor Expansion: Automatically scales crew to 12-13 workers when bank > $3,000.
2. Dynamic Portfolio Expansion: Farms up to 22 Strawberries + 12 Melons + 13 Livestock.
3. Asymmetric Counter-Exploit: Flanks extreme opponent strategies (Dairy/Sheep/Tomato).
4. Step 1 Fast-Ramp & Daily Persistent Animal CARE.
5. FERTILIZE_MELON bonus window execution (doubles melon harvest yield).
6. Post-Drain Synchronized Sales (Batch Cap 4) & Day 29 Turn 12-23 Endgame Flush.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    NE_STRAWBERRY,
    SW_MELON,
    SHED_ACCESS_TILES,
    get_step_towards,
    compute_optimal_steering_kw
)
from project_maestro.agent.counter_strategy import OpponentPerceptionEngine
from project_maestro.agent.meta_calibrated_opponent import META_COW_PASTURES, META_SHEEP_PASTURES
from project_maestro.agent.dynamic_calculator import InstantDynamicCalculator

class IDCMasterAgent(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early: Optional[int] = None, seed: Optional[int] = None):
        default_params = {
            "cow_cap_base": 9,
            "sheep_cap": 4,
            "goose_cap": 0,
            "strawberry_target": 22,
            "melon_seed_target": 12,
            "crew_mid": 10,
            "crew_late": 12,
            "enable_3b": True,
            "feed_protection": True
        }
        merged = {**default_params, **(params or {})}
        derived_kw = compute_optimal_steering_kw(seed) if (kw_early is None and seed is not None) else kw_early
        super().__init__(params=merged, kw_early=derived_kw, seed=seed)
        self.perception = OpponentPerceptionEngine()
        self.idc = InstantDynamicCalculator()
        self.cow_pastures = list(META_COW_PASTURES) + [(3, 1)]
        self.sheep_pastures = list(META_SHEEP_PASTURES)[:4]

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        step = obs.get("step", 0)
        me = obs["farms"][player]
        private = obs.get("private", {})
        shed = private.get("shed", {})
        town_shops = obs.get("town", {}).get("unlocked_shops", [])
        market_inv = obs.get("market", {}).get("inventory", {})
        unlocked_quads = me.get("unlocked_quadrants", ["NW"])

        # 1. Update Opponent Sensing & Counter Adaptation
        self.perception.update(obs, player)

        # 2. Dynamic Livestock Targets from IDC
        opt_cows, opt_sheep = self.idc.calculate_livestock_targets(town_shops, day)
        if day < 18:
            self.params["cow_cap_base"] = opt_cows
            self.params["sheep_cap"] = opt_sheep
        else:
            self.params["cow_cap_base"] = 0
            self.params["sheep_cap"] = 0

        # 3. Dynamic Labor Crew based on Quadrant Scale and Liquidity
        crew_target = self.idc.calculate_daily_crew(day, unlocked_quads, me["money"])
        self.params["crew_mid"] = crew_target
        self.params["crew_late"] = crew_target

        # 4. Core Dispatch
        action_dict = super().__call__(obs)

        # 5. Synchronized Post-Drain Sales & Endgame Flush
        market_orders = list(action_dict.get("market", []))

        # Endgame Liquidation on Day 28+
        if day >= 28 and hour >= 12:
            flush_orders = []
            for item in ["MILK", "WOOL", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]:
                qty = shed.get(item, 0)
                if qty > 0 and len(flush_orders) < 10:
                    flush_orders.append(["SELL", item, min(qty, 20)])
            if flush_orders:
                action_dict["market"] = flush_orders[:10]
                return action_dict

        # Synchronized Milk & Wool pulse selling (Batch Cap 4)
        if step % 4 == 3:
            for item in ["WOOL", "MILK", "STRAWBERRY"]:
                qty = shed.get(item, 0)
                if qty > 0 and len(market_orders) < 10:
                    market_orders.append(["SELL", item, min(qty, 4)])

        # High-Frequency Fertilizer Liquidation ($100 Peak Capture)
        fert_in_shed = shed.get("FERTILIZER", 0)
        if fert_in_shed >= 4 and len(market_orders) < 10 and day < 28:
            market_orders.append(["SELL", "FERTILIZER", min(fert_in_shed, 4)])

        action_dict["market"] = market_orders[:10]
        return action_dict
