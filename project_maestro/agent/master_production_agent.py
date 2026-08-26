"""Master Production Agent (Bug-Free Grandmaster Architecture)

Fixes:
1. CRITICAL: Never return early from market orders — worker harvesting/care actions MUST execute on Days 28-29.
2. Cow/Sheep caps control BUYING targets, not active maintenance/care of existing animals.
3. Clean pasture coordinates (META_COW_PASTURES has 10 exact valid tiles, META_SHEEP_PASTURES has 4).
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
from project_maestro.agent.weed_handler import WeedHandler

class MasterProductionAgent(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early: Optional[int] = None, seed: Optional[int] = None):
        default_params = {
            "cow_cap_base": 10,
            "sheep_cap": 4,
            "goose_cap": 0,
            "strawberry_target": 22,
            "melon_seed_target": 10,
            "crew_mid": 10,
            "crew_late": 12,
            "enable_3b": True,
            "feed_protection": True
        }
        merged = {**default_params, **(params or {})}
        derived_kw = compute_optimal_steering_kw(seed) if (kw_early is None and seed is not None) else kw_early
        super().__init__(params=merged, kw_early=derived_kw, seed=seed)
        
        self.perception = OpponentPerceptionEngine()
        self.weed_handler = WeedHandler()
        self.cow_pastures = list(META_COW_PASTURES)
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
        unlocked_quads = set(me.get("unlocked_quadrants", ["NW"]))

        # 1. Opponent Sensing
        self.perception.update(obs, player)

        # 2. Dynamic Livestock Cap Adjustment (Early Game Only)
        if day < 18:
            s_yarn = town_shops.count("YARN_STORE")
            s_dairy = sum(1 for s in town_shops if s in ("SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "PIZZA_SHOP"))
            if s_yarn >= 2:
                self.params["cow_cap_base"] = 4
                self.params["sheep_cap"] = 10
            elif s_dairy >= 2:
                self.params["cow_cap_base"] = 10
                self.params["sheep_cap"] = 4
            else:
                self.params["cow_cap_base"] = 10
                self.params["sheep_cap"] = 4

        # 3. Dynamic Labor Crew
        if day == 0:
            crew_target = 4
        elif day < 4:
            crew_target = 5
        elif day >= 27:
            crew_target = 10
        elif "SW" in unlocked_quads or day >= 8:
            crew_target = 12 if me["money"] >= 4000 else 10
        elif "NE" in unlocked_quads or day >= 4:
            crew_target = 9
        else:
            crew_target = 5

        self.params["crew_mid"] = crew_target
        self.params["crew_late"] = crew_target

        # 4. Core Dispatch (Worker movement, harvesting, feeding, care)
        action_dict = super().__call__(obs)

        # 5. Progressive Day 28+ Shed Liquidation (WITHOUT skipping worker actions!)
        market_orders = list(action_dict.get("market", []))

        if day >= 28:
            flush_orders = []
            for item in ["MILK", "WOOL", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]:
                qty = shed.get(item, 0)
                if qty > 0 and len(flush_orders) < 10:
                    flush_orders.append(["SELL", item, min(qty, 10)])
            if flush_orders:
                market_orders = flush_orders[:10]
        else:
            # Synchronized Pulse Selling at step % 4 == 3
            if step % 4 == 3:
                for item in ["WOOL", "MILK", "STRAWBERRY"]:
                    qty = shed.get(item, 0)
                    if qty > 0 and len(market_orders) < 10:
                        market_orders.append(["SELL", item, min(qty, 4)])

            # High-Frequency Fertilizer Liquidation
            fert_qty = shed.get("FERTILIZER", 0)
            if fert_qty >= 4 and len(market_orders) < 10:
                market_orders.append(["SELL", "FERTILIZER", min(fert_qty, 4)])

        action_dict["market"] = market_orders[:10]
        return action_dict
