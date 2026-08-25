"""Unit tests for Project Aegis - Module 3: Ghost Protocol & Safe Scavenger Coordination"""

import unittest
from project_aegis.ghost import (
    apply_ghost_signature_spoof,
    scavenger_farmhand_overlay,
    schedule_auxiliary_farmhand_hire,
)

class TestModule3Ghost(unittest.TestCase):

    def test_ghost_spoof_on_step_0(self):
        """Tests that ghost spoof adds a harmless Carrot seed buy on Step 0 when funds are plentiful."""
        obs = {
            "step": 0,
            "player": 0,
            "farms": [{"money": 3000.0}]
        }
        action = {"farmer": ["PASS"], "market": [["BUY_SEED", "WHEAT", 1]]}
        spoofed = apply_ghost_signature_spoof(obs, action)
        self.assertEqual(len(spoofed["market"]), 2)
        self.assertEqual(spoofed["market"][1], ["BUY_SEED", "CARROT", 1])

        obs_1 = {
            "step": 1,
            "player": 0,
            "farms": [{"money": 2900.0}]
        }
        action_1 = {"farmer": ["PASS"], "market": []}
        spoofed_1 = apply_ghost_signature_spoof(obs_1, action_1)
        self.assertEqual(spoofed_1["market"], [])

    def test_scavenger_farmhand_weed_routing(self):
        """Tests that unscripted hands are routed toward weeds and issue DIG."""
        tiles = [[None] * 10 for _ in range(10)]
        tiles[1][0] = {"kind": "WEED"}

        obs = {
            "player": 0,
            "farms": [
                {
                    "farmer": [4, 4],
                    "hands": [[0, 0]],
                    "tiles": tiles,
                    "unlocked_quadrants": ["NW"],
                    "money": 1000.0
                }
            ]
        }

        action = {"farmer": ["PASS"], "hands": []}
        res = scavenger_farmhand_overlay(action, obs)

        self.assertEqual(len(res["hands"]), 1)
        self.assertEqual(res["hands"][0], ["SOUTH"])

        obs["farms"][0]["hands"] = [[0, 1]]
        action_on_weed = {"farmer": ["PASS"], "hands": []}
        res_dig = scavenger_farmhand_overlay(action_on_weed, obs)
        self.assertEqual(res_dig["hands"][0], ["DIG"])

    def test_scavenger_farmhand_fertilizer_collection(self):
        """Tests that unscripted hands collect available fertilizer from coops/pastures."""
        tiles = [[None] * 10 for _ in range(10)]
        tiles[0][1] = {"kind": "PASTURE", "animal": "COW", "fertilizer_available": True}

        obs = {
            "player": 0,
            "farms": [
                {
                    "farmer": [4, 4],
                    "hands": [[1, 0]],
                    "tiles": tiles,
                    "unlocked_quadrants": ["NW"],
                    "money": 1000.0
                }
            ]
        }
        action = {"farmer": ["PASS"], "hands": []}
        res = scavenger_farmhand_overlay(action, obs)
        self.assertEqual(res["hands"][0], ["COLLECT_FERTILIZER"])

    def test_scavenger_never_plants_on_empty_tiles(self):
        """CRITICAL INVARIANT TEST: Verifies that unscripted hands NEVER issue PLANT on empty tiles,
        protecting 100% of future scheduled base tape pastures and crops.
        """
        tiles = [[None] * 10 for _ in range(10)]
        obs = {
            "day": 10,
            "player": 0,
            "farms": [
                {
                    "farmer": [4, 4],
                    "hands": [[2, 2]],
                    "tiles": tiles,
                    "unlocked_quadrants": ["NW", "NE", "SW"],
                    "money": 5000.0
                }
            ],
            "private": {
                "seeds": {"MELON": 12, "TOMATO": 10, "CARROT": 10}
            }
        }
        action = {"farmer": ["PASS"], "hands": []}
        res = scavenger_farmhand_overlay(action, obs)
        # Should NOT plant anything on empty tiles
        self.assertEqual(res["hands"][0], ["PASS"])

    def test_schedule_auxiliary_hire_disabled(self):
        """Verifies that schedule_auxiliary_farmhand_hire is a strict pass-through to preserve capex."""
        obs = {"day": 10, "hour": 0, "player": 0, "farms": [{"money": 5000.0}]}
        action = {"farmer": ["PASS"], "hands": [], "market": []}
        res = schedule_auxiliary_farmhand_hire(action, obs)
        self.assertEqual(res["market"], [])

if __name__ == "__main__":
    unittest.main()
