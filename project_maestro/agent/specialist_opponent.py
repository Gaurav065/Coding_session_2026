"""Ahmad Ali Specialist Opponent (14 Sheep / 33 Melon / 0 Cow) — Project Maestro

Calibrated to the observed $125k winner build in live ladder match 99064717:
- Livestock: 14 Sheep, 0 Cows, 0 Geese
- Heavy daily wheat purchases (BUY_PRODUCT WHEAT) to keep 14 sheep fed and cared
- Crops: 33 Melons (SW/SE quadrants), ~17 Strawberry (NE quadrant), Carrot/Tomato replants
- Land unlocks: NE (Day 5-6), SW (Day 10), SE (Day 14)
- Sells: Wool ($200 base) and Melon ($250 base) capturing uncrowded ladder pricing.
"""

from typing import Dict, List, Tuple, Optional, Any
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    BASE_PRICES,
    ABOVE_TARGET,
    GLUT_RESISTANT,
    GLUT_PRONE,
    get_step_towards,
    dist,
    SHED_ACCESS_TILES,
    COW_PASTURES,
    SHEEP_PASTURES,
    GOOSE_COOPS,
    NW_WHEAT,
    NE_STRAWBERRY,
    NE_WHEAT,
    SW_MELON,
    SW_WHEAT
)

# 14 Sheep Pastures across NW quadrant
SPECIALIST_SHEEP_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4)
]  # 14 Sheep Pastures

# Melon plots across SW and SE quadrants
SPECIALIST_MELON_PLOTS = [
    (0, 6), (1, 6), (2, 6), (3, 6), (4, 6),
    (0, 7), (1, 7), (2, 7), (3, 7), (4, 7),
    (0, 8), (1, 8), (2, 8), (3, 8), (4, 8),
    (0, 9), (1, 9), (2, 9), (3, 9), (4, 9),
    (0, 5), (1, 5), (2, 5), (3, 5),
]

SPECIALIST_STRAWBERRY_PLOTS = [
    (5, 0), (6, 0), (7, 0), (8, 0), (9, 0),
    (5, 1), (6, 1), (7, 1), (8, 1), (9, 1),
    (5, 2), (6, 2), (7, 2), (8, 2), (9, 2),
    (5, 3), (6, 3), (7, 3)
]

SPECIALIST_DEFAULT_PARAMS = {
    "cow_cap_base": 0,           # 0 Cows
    "sheep_cap": 14,             # 14 Sheep
    "goose_cap": 0,              # 0 Geese
    "strawberry_target": 18,     # 18 Strawberry
    "melon_seed_target": 24,     # Heavy Melon focus
    "crew_mid": 9,
    "crew_late": 10,
    "cow_gate_day_early": 99,
    "cow_gate_day_mid": 99,
}


class SpecialistOpponent(MaestroFullPortfolioAgent):
    """Opponent agent mimicking Ahmad Ali's 14 Sheep / 33 Melon / 0 Cow build."""
    def __init__(self, params=None, kw_early: Optional[int] = 10, seed: Optional[int] = None):
        merged_params = {**SPECIALIST_DEFAULT_PARAMS, **(params or {})}
        super().__init__(params=merged_params, kw_early=kw_early, seed=seed)
        self.cow_pastures = []
        self.sheep_pastures = list(SPECIALIST_SHEEP_PASTURES)
        self.goose_coops = []
        self.sw_melon = list(SPECIALIST_MELON_PLOTS)
        self.ne_strawberry = list(SPECIALIST_STRAWBERRY_PLOTS)

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        # Day 0 Opening tailored to 5 Sheep + Feed
        day = obs["day"]
        hour = obs["hour"]
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        money = me["money"]
        shed = private.get("shed", {})
        shed_wheat = shed.get("WHEAT", 0)

        act = super().__call__(obs)

        if hour == 0 and day == 0:
            act["market"] = [
                ["HIRE"], ["HIRE"], ["HIRE"], ["HIRE"], ["HIRE"],
                ["BUY_SEED", "WHEAT", 10],
                ["BUY_PRODUCT", "WHEAT", 14],
                ["BUY_ANIMAL", "SHEEP", 4],
            ]

        # Heavy feed replenishment to maintain 14 sheep fed daily
        if day < 29 and shed_wheat < 14 and money >= 200:
            buy_feed = min(14 - shed_wheat, int(money // 25))
            if buy_feed > 0 and len(act["market"]) < 10:
                act["market"].append(["BUY_PRODUCT", "WHEAT", min(10, buy_feed)])

        # Melon seed purchases (up to 24-33 seeds)
        if "SW" in me.get("unlocked_quadrants", []) and private["seeds"].get("MELON", 0) < 12 and money >= 500 and day < 16:
            if len(act["market"]) < 10:
                act["market"].append(["BUY_SEED", "MELON", 8])

        return act


def make_specialist_opponent(params=None, seed: Optional[int] = None, kw_early: Optional[int] = 10):
    agent_instance = SpecialistOpponent(params=params, seed=seed, kw_early=kw_early)
    return lambda obs: agent_instance(obs)
