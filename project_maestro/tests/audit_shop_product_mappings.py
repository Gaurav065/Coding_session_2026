"""Systematic Codebase Audit of Shop and Product Mappings against kaggriculture.py:103-112"""

import sys
import unittest

sys.path.insert(0, r"C:\Coding")

from kaggle_environments.envs.kaggriculture.kaggriculture import (
    SHOPS as GROUND_TRUTH_SHOPS,
    MARKET_PARAMS as GROUND_TRUTH_MARKET_PARAMS,
    MARKET_I0,
)
from project_maestro.engine.fast_engine import SHOPS as FAST_ENGINE_SHOPS
from project_maestro.data.phase0_analysis import SHOPS_MAP as PHASE0_SHOPS
from project_maestro.oracle.price_model import SHOPS_MAP as ORACLE_SHOPS

class TestShopMappingsAudit(unittest.TestCase):
    def test_fast_engine_shops(self):
        self.assertEqual(FAST_ENGINE_SHOPS, GROUND_TRUTH_SHOPS, "fast_engine.py SHOPS must match ground truth")

    def test_phase0_shops(self):
        self.assertEqual(PHASE0_SHOPS, GROUND_TRUTH_SHOPS, "phase0_analysis.py SHOPS_MAP must match ground truth")

    def test_oracle_shops(self):
        self.assertEqual(ORACLE_SHOPS, GROUND_TRUTH_SHOPS, "price_model.py SHOPS_MAP must match ground truth")

    def test_product_subsets(self):
        # Derive exact product subsets from ground truth
        milk_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "MILK" in prods}
        straw_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "STRAWBERRY" in prods}
        wool_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "WOOL" in prods}
        egg_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "EGG" in prods}
        carrot_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "CARROT" in prods}
        tomato_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "TOMATO" in prods}
        wheat_shops = {s for s, prods in GROUND_TRUTH_SHOPS.items() if "WHEAT" in prods}

        self.assertEqual(milk_shops, {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"})
        self.assertEqual(straw_shops, {"SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "FARMERS_MARKET", "BRUNCH_SPOT"})
        self.assertEqual(wool_shops, {"YARN_STORE"})
        self.assertEqual(egg_shops, {"BAKERY", "BRUNCH_SPOT"})
        self.assertEqual(carrot_shops, {"PET_CAFE", "FARMERS_MARKET"})
        self.assertEqual(tomato_shops, {"PIZZA_SHOP", "FARMERS_MARKET"})
        self.assertEqual(wheat_shops, {"BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "ICE_CREAM_SHOP", "FARMERS_MARKET"})

    def test_market_params(self):
        for item, p in GROUND_TRUTH_MARKET_PARAMS.items():
            self.assertEqual(p["I0"], 10000)
            if item == "FERTILIZER":
                self.assertEqual(p["above_func"], "linear")
                self.assertEqual(p["above_target"], 0.40)
            elif item == "STRAWBERRY":
                self.assertEqual(p["above_func"], "linear")
                self.assertEqual(p["above_target"], 1.60)
            elif item == "MELON":
                self.assertEqual(p["above_func"], "sq")
                self.assertEqual(p["above_target"], 3.60)
            elif item == "WOOL":
                self.assertEqual(p["above_func"], "sq")
                self.assertEqual(p["above_target"], 3.20)


if __name__ == "__main__":
    unittest.main()
