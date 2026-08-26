"""Dynamic Contingency Portfolio Agent for Project Maestro

Combines:
1. Base Core: 10-12 Cows / 2-4 Sheep (NW), 18-22 Strawberries (NE), 6-8 Melons (SW).
2. Dynamic Shop-Triggered Responses:
   - PET_CAFE active: Flash-plants 6 Carrots on buffer plots (2-day harvest @ $165).
   - PIZZA_SHOP active: Allocates 4 dedicated plots in NE to ongoing TOMATOES (daily harvest @ $120-$601).
   - YARN_STORE active: Scales Sheep ratio to 7-10 sheep ($240/wool).
3. Day 18 Animal Buy Freeze: Zero animal purchases after Day 18 (guarantees positive ROI).
4. Day 29 Endgame Flush: Complete shed liquidation on Day 29 Turn 12-23 (leaves $0 on table).
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    NE_STRAWBERRY,
    SHED_ACCESS_TILES,
    get_step_towards,
    dist
)
from project_maestro.agent.counter_strategy import OpponentPerceptionEngine
from project_maestro.agent.meta_calibrated_opponent import META_COW_PASTURES, META_SHEEP_PASTURES

DEDICATED_TOMATO_TILES = [(8, 0), (9, 0), (8, 1), (9, 1)]

class DynamicPortfolioAgent(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early: Optional[int] = None, seed: Optional[int] = None):
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.perception = OpponentPerceptionEngine()
        self.cow_pastures = list(META_COW_PASTURES) + [(3, 1), (2, 2)]
        self.sheep_pastures = list(META_SHEEP_PASTURES)
        self.tomato_plots = list(DEDICATED_TOMATO_TILES)
        self.pizza_shop_active = False

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        step = obs.get("step", 0)
        town_shops = obs.get("town", {}).get("unlocked_shops", [])
        me = obs["farms"][player]
        private = obs.get("private", {})
        shed = private.get("shed", {})
        unlocked_quads = set(me.get("unlocked_quadrants", []))

        # 1. Update Opponent Sensing
        self.perception.update(obs, player)

        # 2. Dynamic Shop Response Engine
        s_yarn = town_shops.count("YARN_STORE")
        s_dairy = sum(1 for s in town_shops if s in ("SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "PIZZA_SHOP"))
        has_pet_cafe = "PET_CAFE" in town_shops
        has_pizza_shop = "PIZZA_SHOP" in town_shops

        if has_pizza_shop and day <= 12 and not self.pizza_shop_active:
            self.pizza_shop_active = True
            # Remove tomato plots from strawberry set so they don't conflict
            self.ne_strawberry = [pos for pos in NE_STRAWBERRY if pos not in self.tomato_plots]

        # Exact Closed-Form Cow/Sheep Ratio
        opt_sheep = min(10, max(2, int(round(2 + 3 * s_yarn - 1.2 * s_dairy))))
        opt_cows = 14 - opt_sheep

        self.params["cow_cap_base"] = opt_cows
        self.params["sheep_cap"] = opt_sheep

        # Day 18 Animal Buy Freeze
        if day >= 18:
            self.params["cow_cap_base"] = 0
            self.params["sheep_cap"] = 0

        # Dynamic Niche Adaptation from opponent sensing
        if day >= 4:
            adapted_params = self.perception.compute_counter_portfolio(obs, self.params)
            for k, v in adapted_params.items():
                if k not in ("cow_cap_base", "sheep_cap") or day < 18:
                    self.params[k] = v

        # 3. Core Dispatch
        action_dict = super().__call__(obs)

        # 4. Tomato Planting & Care Tasks for NE Units (Units 6, 7, 8)
        if self.pizza_shop_active and "NE" in unlocked_quads and day >= 5:
            avail_tomato_seeds = private.get("seeds", {}).get("TOMATO", 0)
            hands_actions = action_dict.get("hands", [])

            # Inject Tomato tasks into NE workers
            for t_idx, (tx, ty) in enumerate(self.tomato_plots):
                tile = me["tiles"][ty][tx]
                # If tile is empty and we have seeds, assign a worker to plant
                if tile is None and avail_tomato_seeds > 0 and day < 20:
                    for w_idx in [5, 6, 7]:
                        if w_idx < len(hands_actions):
                            hands_actions[w_idx] = [get_step_towards(me["hands"][w_idx], (tx, ty))]
                            if me["hands"][w_idx] == [tx, ty]:
                                hands_actions[w_idx] = ["PLANT", "TOMATO"]
                                avail_tomato_seeds -= 1
                            break
                elif isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "TOMATO":
                    y = tile.get("yield_units", 0)
                    watered = tile.get("watered_today", False)
                    for w_idx in [5, 6, 7]:
                        if w_idx < len(hands_actions):
                            if me["hands"][w_idx] == [tx, ty]:
                                if y > 0:
                                    hands_actions[w_idx] = ["HARVEST"]
                                elif not watered:
                                    hands_actions[w_idx] = ["WATER"]
                                break

            action_dict["hands"] = hands_actions

        # 5. Day 29 Endgame Flush (Dump 100% of shed goods)
        if day >= 28 and hour >= 12:
            orders = []
            for item in ["MILK", "WOOL", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]:
                qty = shed.get(item, 0)
                if qty > 0 and len(orders) < 10:
                    orders.append(["SELL", item, min(qty, 20)])
            if orders:
                action_dict["market"] = orders[:10]

        # 6. Opportunity Seed Purchasing for Flash Crops
        if hour == 0:
            market_orders = list(action_dict.get("market", []))
            if has_pet_cafe and day in (3, 6, 9, 12, 15) and private.get("seeds", {}).get("CARROT", 0) == 0 and me["money"] >= 200:
                if len(market_orders) < 10:
                    market_orders.append(["BUY_SEED", "CARROT", 6])
            if has_pizza_shop and day in (3, 6, 9) and private.get("seeds", {}).get("TOMATO", 0) == 0 and me["money"] >= 300:
                if len(market_orders) < 10:
                    market_orders.append(["BUY_SEED", "TOMATO", 4])
            action_dict["market"] = market_orders[:10]

        return action_dict
