"""Unit tests for Project Aegis - Module 2: The River"""

import unittest
from project_aegis.river import (
    RiverEngine,
    LiquidityGuard,
    SHED_FLUSH_THRESHOLD,
)

class TestModule2River(unittest.TestCase):

    def test_process_tape_orders(self):
        """Tests that in production phase, standalone bulk SELL orders are enqueued."""
        river = RiverEngine()
        tape_orders = [
            ["SELL", "WHEAT", 20],
            ["SELL", "MILK", 10],
        ]

        retained = river.process_tape_orders(tape_orders, step=300)
        self.assertEqual(retained, [])
        self.assertEqual(river.pending_sell_queue["WHEAT"], 20)
        self.assertEqual(river.pending_sell_queue["MILK"], 10)

    def test_liquidity_guard_forces_urgent_liquidation_on_cash_shortfall(self):
        """Tests that when bank balance is insufficient for upcoming BUY_LAND ($2000),
        LiquidityGuard immediately sells available shed produce to guarantee funds.
        """
        obs = {
            "player": 0,
            "farms": [{"money": 500.0, "unlocked_quadrants": ["NW", "NE"]}],
            "private": {
                "shed": {"MILK": 10, "WHEAT": 50}
            },
            "market": {
                "prices": {"MILK": 160, "WHEAT": 25}
            }
        }

        urgent_orders = LiquidityGuard.ensure_liquidity(
            obs,
            current_market_orders=[],
            needed_cash=2000.0
        )

        self.assertEqual(len(urgent_orders), 1)
        self.assertEqual(urgent_orders[0], ["SELL", "MILK", 10])

    def test_hard_shed_pressure_valve(self):
        """Tests that when shed inventory exceeds 75 items, RiverEngine flushes low-tier staples."""
        river = RiverEngine()
        obs = {
            "step": 300,
            "player": 0,
            "farms": [{"money": 3000.0, "unlocked_quadrants": ["NW"]}],
            "private": {
                "shed": {"WHEAT": 50, "FERTILIZER": 30}  # Total 80 > 75
            },
            "market": {
                "prices": {"WHEAT": 25, "FERTILIZER": 100}
            }
        }

        orders = river.generate_trickle_orders(
            obs,
            current_market_orders=[],
            future_tape_slice=[]
        )

        sold_items = {o[1] for o in orders if o[0] == "SELL"}
        self.assertTrue("FERTILIZER" in sold_items or "WHEAT" in sold_items)

    def test_price_floor_pause_guard(self):
        """Tests that trickle selling is paused for goods whose AMM price is depressed below 60% of base."""
        river = RiverEngine()
        river.pending_sell_queue["MILK"] = 10

        obs = {
            "step": 300,
            "player": 0,
            "farms": [{"money": 3000.0, "unlocked_quadrants": ["NW"]}],
            "private": {
                "shed": {"MILK": 10}
            },
            "market": {
                "prices": {"MILK": 50}  # Base 160 * 0.60 = 96 > 50 (depressed)
            }
        }

        orders = river.generate_trickle_orders(
            obs,
            current_market_orders=[],
            future_tape_slice=[]
        )

        milk_sells = [o for o in orders if o[0] == "SELL" and o[1] == "MILK"]
        self.assertEqual(len(milk_sells), 0)

if __name__ == "__main__":
    unittest.main()
