"""Unit tests for Project Aegis - Module 0: Core Architecture"""

import unittest
import copy
from project_aegis.core import (
    calculate_single_unit_price,
    simulate_sale_revenue,
    PureDebtManager,
    prioritize_and_dispatch_market,
    execute_terminal_liquidation,
    safe_agent_fallback,
    MARKET_PARAMS,
    MARKET_I0,
    PRICE_FLOOR,
    MAX_MARKET_ORDERS,
)

class TestModule0Core(unittest.TestCase):

    def test_amm_price_curve_exact_readme_values(self):
        """Validates that AMM price calculation matches the exact table published in README.md."""
        expected_benchmark_prices = {
            # At equilibrium I0 = 10,000
            ("WHEAT", 10000, 25),
            ("CARROT", 10000, 35),
            ("TOMATO", 10000, 60),
            ("STRAWBERRY", 10000, 120),
            ("MELON", 10000, 250),
            ("EGG", 10000, 50),
            ("MILK", 10000, 160),
            ("WOOL", 10000, 200),
            ("FERTILIZER", 10000, 100),

            # At I0 - T (Scarcity side)
            ("WHEAT", 10000 - 400, 45),
            ("CARROT", 10000 - 450, 42),
            ("TOMATO", 10000 - 200, 84),
            ("STRAWBERRY", 10000 - 100, 204),
            ("MELON", 10000 - 300, 300),
            ("EGG", 10000 - 332, 70),
            ("MILK", 10000 - 122, 256),
            ("WOOL", 10000 - 105, 240),
            ("FERTILIZER", 10000 - 200, 140),

            # At I0 + T (Glut side)
            ("WHEAT", 10000 + 400, 20),
            ("CARROT", 10000 + 450, 10),
            ("TOMATO", 10000 + 200, 24),
            ("STRAWBERRY", 10000 + 100, 1),
            ("MELON", 10000 + 300, 1),
            ("EGG", 10000 + 332, 40),
            ("MILK", 10000 + 122, 1),
            ("WOOL", 10000 + 105, 1),
            ("FERTILIZER", 10000 + 200, 60),

            # At I0 + 2T (Heavy Glut)
            ("WHEAT", 10000 + 800, 19),
            ("CARROT", 10000 + 900, 1),
            ("TOMATO", 10000 + 400, 9),
            ("STRAWBERRY", 10000 + 200, 1),
            ("MELON", 10000 + 600, 1),
            ("EGG", 10000 + 664, 39),
            ("MILK", 10000 + 244, 1),
            ("WOOL", 10000 + 210, 1),
            ("FERTILIZER", 10000 + 400, 20),
        }

        for item, inv, expected_price in expected_benchmark_prices:
            calculated = calculate_single_unit_price(item, inv)
            self.assertEqual(calculated, expected_price, f"Mismatch for {item} at inv={inv}: got {calculated}, expected {expected_price}")

    def test_simulate_sale_revenue(self):
        """Tests revenue calculation across multiple units and price floor enforcement."""
        rev, end_inv = simulate_sale_revenue("STRAWBERRY", 10000, 1)
        self.assertEqual(rev, 120.0)
        self.assertEqual(end_inv, 10001)

        rev_floor, end_inv_floor = simulate_sale_revenue("MELON", 15000, 5)
        self.assertEqual(rev_floor, 5.0)
        self.assertEqual(end_inv_floor, 15000)

    def test_pure_debt_manager_full_repayment(self):
        """Tests debt creation and exact repayment on due_step without modifying original tape structures."""
        debt_mgr = PureDebtManager()
        debt_mgr.reset_if_new_game(0)

        debt_mgr.record_debt(due_step=50, item="MILK", quantity=10)

        tape_action_49 = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 5]]}
        out_49 = debt_mgr.apply_repayment(copy.deepcopy(tape_action_49), 49)
        self.assertEqual(out_49["market"], [["SELL", "WHEAT", 5]])
        self.assertEqual(debt_mgr.due["MILK"], 10)

        tape_action_50 = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MILK", 20]]}
        out_50 = debt_mgr.apply_repayment(copy.deepcopy(tape_action_50), 50)
        self.assertEqual(out_50["market"], [["SELL", "MILK", 10]])
        self.assertEqual(debt_mgr.due, {})
        self.assertEqual(debt_mgr.due_step, -1)

        # Verify original tape dictionary was completely untouched
        self.assertEqual(tape_action_50["market"], [["SELL", "MILK", 20]])

    def test_pure_debt_manager_partial_repayment(self):
        """Tests debt repayment when scheduled tape order is smaller than debt."""
        debt_mgr = PureDebtManager()
        debt_mgr.reset_if_new_game(0)

        debt_mgr.record_debt(due_step=100, item="STRAWBERRY", quantity=15)

        tape_action_100 = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "STRAWBERRY", 10]]}
        out_100 = debt_mgr.apply_repayment(copy.deepcopy(tape_action_100), 100)
        self.assertEqual(out_100["market"], [])
        self.assertEqual(debt_mgr.due["STRAWBERRY"], 5)

    def test_priority_order_dispatcher(self):
        """Verifies strict 10-order limit and deterministic priority ordering."""
        raw_orders = [
            ["SELL", "WHEAT", 1],
            ["SELL", "FERTILIZER", 2],
            ["SELL", "MILK", 5],
            ["SELL", "STRAWBERRY", 3],
            ["SELL", "WOOL", 4],
            ["SELL", "CARROT", 1],
            ["SELL", "TOMATO", 1],
            ["SELL", "EGG", 2],
            ["BUY_PRODUCT", "WHEAT", 1],
            ["BUY_ANIMAL", "COW", 1],
            ["BUY_SEED", "WHEAT", 5],
            ["HIRE"],
            ["BUY_LAND"],
        ]

        dispatched = prioritize_and_dispatch_market(raw_orders)
        self.assertEqual(len(dispatched), MAX_MARKET_ORDERS)
        self.assertEqual(dispatched[0], ["BUY_LAND"])
        self.assertEqual(dispatched[1], ["HIRE"])
        self.assertEqual(dispatched[2], ["BUY_SEED", "WHEAT", 5])
        self.assertEqual(dispatched[3], ["BUY_ANIMAL", "COW", 1])
        self.assertEqual(dispatched[4], ["BUY_PRODUCT", "WHEAT", 1])

    def test_terminal_liquidation(self):
        """Tests terminal liquidation behavior on step 715 vs step 716."""
        obs = {
            "private": {
                "shed": {"WHEAT": 50, "MILK": 10, "FERTILIZER": 20}
            }
        }

        act_715 = {"farmer": ["PASS"], "market": [["SELL", "WHEAT", 5]]}
        res_715 = execute_terminal_liquidation(obs, copy.deepcopy(act_715), 715)
        self.assertEqual(res_715["market"], [["SELL", "WHEAT", 5]])

        act_716 = {"farmer": ["PASS"], "market": []}
        res_716 = execute_terminal_liquidation(obs, copy.deepcopy(act_716), 716)
        sold_items = {o[1]: o[2] for o in res_716["market"] if o[0] == "SELL"}
        self.assertEqual(sold_items.get("WHEAT"), 50)
        self.assertEqual(sold_items.get("MILK"), 10)
        self.assertEqual(sold_items.get("FERTILIZER"), 20)

    def test_safe_agent_fallback(self):
        """Tests that safe_agent_fallback creates legal actions matching active hands count."""
        obs_single = {"player": 0, "farms": [{"hands": []}, {}]}
        res_single = safe_agent_fallback(obs_single)
        self.assertEqual(res_single["farmer"], ["PASS"])
        self.assertEqual(res_single["hands"], [])
        self.assertEqual(res_single["market"], [])

        obs_multi = {"player": 0, "farms": [{"hands": [[4, 4], [5, 4], [4, 5]]}, {}]}
        res_multi = safe_agent_fallback(obs_multi)
        self.assertEqual(res_multi["farmer"], ["PASS"])
        self.assertEqual(len(res_multi["hands"]), 3)
        self.assertEqual(res_multi["hands"], [["PASS"], ["PASS"], ["PASS"]])

if __name__ == "__main__":
    unittest.main()
