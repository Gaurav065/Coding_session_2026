"""Unit tests for Project Aegis - Module 1: The Predator"""

import unittest
from project_aegis.core import PureDebtManager
from project_aegis.predator import (
    OpponentShedEstimator,
    PredatorEngine,
    PREDATOR_DUMP_THRESHOLDS,
)

class TestModule1Predator(unittest.TestCase):

    def test_opponent_harvest_and_shed_tracking(self):
        """Tests that visible tile yield changes and shed adjacency correctly increment estimated shed."""
        estimator = OpponentShedEstimator()
        estimator.reset_if_new_game(0)

        # Step 0: Opponent has 1 Cow with 4 yield units, standing at (0, 0)
        opp_farm_step0 = {
            "farmer": [0, 0],
            "hands": [],
            "tiles": [
                [{"kind": "PASTURE", "animal": "COW", "yield_units": 4, "fertilizer_available": True}] + [None] * 9
            ] + [[None] * 10 for _ in range(9)]
        }
        obs_step0 = {
            "step": 0,
            "hour": 0,
            "player": 0,
            "farms": [{}, opp_farm_step0]
        }
        estimator.update(obs_step0)
        self.assertEqual(estimator.get_estimated_volume("MILK"), 0)

        # Step 1: Opponent harvests cow (yield_units drops to 0) but still at (0, 0)
        opp_farm_step1 = {
            "farmer": [0, 0],
            "hands": [],
            "tiles": [
                [{"kind": "PASTURE", "animal": "COW", "yield_units": 0, "fertilizer_available": True}] + [None] * 9
            ] + [[None] * 10 for _ in range(9)]
        }
        obs_step1 = {
            "step": 1,
            "hour": 1,
            "player": 0,
            "farms": [{}, opp_farm_step1]
        }
        estimator.update(obs_step1)
        # Harvested 4 units into carried inventory, but not in shed yet
        self.assertEqual(estimator.carried_inventory["MILK"], 4)
        self.assertEqual(estimator.get_estimated_volume("MILK"), 0)

        # Step 2: Opponent moves adjacent to shed at (4, 4)
        opp_farm_step2 = {
            "farmer": [4, 4],
            "hands": [],
            "tiles": [
                [{"kind": "PASTURE", "animal": "COW", "yield_units": 0, "fertilizer_available": True}] + [None] * 9
            ] + [[None] * 10 for _ in range(9)]
        }
        obs_step2 = {
            "step": 2,
            "hour": 2,
            "player": 0,
            "farms": [{}, opp_farm_step2]
        }
        estimator.update(obs_step2)
        # Carried inventory transferred to estimated shed
        self.assertEqual(estimator.get_estimated_volume("MILK"), 4)
        self.assertEqual(estimator.carried_inventory["MILK"], 0)

    def test_predator_frontrun_trigger_and_debt_recording(self):
        """Tests that PredatorEngine detects imminent opponent dump and pulls forward sales into debt manager."""
        estimator = OpponentShedEstimator()
        # Set estimated opponent Milk to 8 (above threshold 6)
        estimator.estimated_shed["MILK"] = 8

        engine = PredatorEngine(estimator)
        debt_mgr = PureDebtManager()
        debt_mgr.reset_if_new_game(20)

        # Our own shed has 10 Milk
        obs = {
            "step": 20,
            "player": 0,
            "private": {
                "shed": {"MILK": 10}
            },
            "market": {
                "prices": {"MILK": 160},
                "inventory": {"MILK": 10000}
            }
        }

        # We have a scheduled sell of 10 Milk at step 25
        lookahead = {"MILK": (25, 10)}
        current_orders = [["BUY_SEED", "WHEAT", 2]]

        frontrun_orders = engine.evaluate_frontrun_opportunities(
            obs, current_orders, debt_mgr, lookahead
        )

        self.assertEqual(len(frontrun_orders), 1)
        self.assertEqual(frontrun_orders[0], ["SELL", "MILK", 5])  # 50% of scheduled 10
        # Verify debt was recorded against step 25 without tape mutation
        self.assertEqual(debt_mgr.due_step, 25)
        self.assertEqual(debt_mgr.due["MILK"], 5)

if __name__ == "__main__":
    unittest.main()
