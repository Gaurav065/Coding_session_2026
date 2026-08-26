"""Opponent Perception & Dynamic Niche Counter-Strategy Engine for Project Maestro

Monitors opponent farm state in real time, classifies their strategic archetype,
and dynamically adjusts our farm targets to maximize market asymmetry and uncontested profits.
"""

from typing import Dict, List, Any, Tuple, Optional

class OpponentPerceptionEngine:
    def __init__(self):
        self.opp_cows = 0
        self.opp_sheep = 0
        self.opp_geese = 0
        self.opp_berries = 0
        self.opp_quads = ["NW"]
        self.classified_archetype = "UNKNOWN"
        self.last_update_day = -1

    def update(self, obs: Dict[str, Any], player: int):
        day = obs.get("day", 0)
        if day == self.last_update_day:
            return
        self.last_update_day = day

        opp_idx = 1 - player
        opp_farm = obs["farms"][opp_idx]
        tiles = opp_farm.get("tiles", [])
        
        cows = 0
        sheep = 0
        geese = 0
        berries = 0

        for row in tiles:
            for t in row:
                if isinstance(t, dict):
                    kind = t.get("kind")
                    if kind == "PASTURE":
                        animal = t.get("animal")
                        if animal == "COW":
                            cows += 1
                        elif animal == "SHEEP":
                            sheep += 1
                    elif kind == "COOP":
                        geese += 1
                    elif kind == "PLANT":
                        if t.get("crop") == "STRAWBERRY":
                            berries += 1

        self.opp_cows = cows
        self.opp_sheep = sheep
        self.opp_geese = geese
        self.opp_berries = berries
        self.opp_quads = opp_farm.get("unlocked_quadrants", ["NW"])

        # Classify by Day 4+
        if day >= 4:
            if sheep >= 8:
                self.classified_archetype = "SHEEP_RUSH"
            elif cows >= 8 and sheep <= 4:
                self.classified_archetype = "DAIRY_HEAVY"
            elif cows >= 5 and sheep >= 5:
                self.classified_archetype = "BALANCED_LIVESTOCK"
            elif berries >= 15 and (cows + sheep) <= 4:
                self.classified_archetype = "CROP_STRAWBERRY_HEAVY"
            else:
                self.classified_archetype = "BALANCED_META"

    def compute_counter_portfolio(self, obs: Dict[str, Any], base_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically adjusts farm targets based on opponent footprint and unlocked shops.
        """
        params = dict(base_params)
        town_shops = obs.get("town", {}).get("unlocked_shops", [])
        has_yarn_store = "YARN_STORE" in town_shops
        has_smoothie = "SMOOTHIE_SHOP" in town_shops or "BRUNCH_SPOT" in town_shops or "ICE_CREAM_SHOP" in town_shops

        if self.classified_archetype == "DAIRY_HEAVY":
            if has_yarn_store:
                # Yarn store active -> shift to Wool monopoly
                params["cow_cap_base"] = 8
                params["sheep_cap"] = 8
                params["strawberry_target"] = 22
                params["melon_seed_target"] = 6
            else:
                # Opponent Dairy Heavy without Yarn -> Match Dairy, exceed on Strawberries & Melons
                params["cow_cap_base"] = 10
                params["sheep_cap"] = 4
                params["strawberry_target"] = 22
                params["melon_seed_target"] = 6
        elif self.classified_archetype == "SHEEP_RUSH":
            # Opponent is flooding Wool -> Counter by dominating Milk & Strawberries
            params["cow_cap_base"] = 11
            params["sheep_cap"] = 2
            params["strawberry_target"] = 24
            params["melon_seed_target"] = 4
        else:
            # Default Grandmaster Frontier
            params["cow_cap_base"] = 10 if has_smoothie else 9
            params["sheep_cap"] = 6 if has_yarn_store else 4
            params["strawberry_target"] = 22
            params["melon_seed_target"] = 6

        return params
