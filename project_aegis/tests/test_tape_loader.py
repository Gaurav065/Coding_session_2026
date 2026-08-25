"""Unit tests for Project Aegis - Module 4: Tape Loader & Multi-Route Oracle"""

import unittest
from project_aegis.tape_loader import (
    get_base_tape,
    select_active_tape,
    get_lookahead_scheduled_sells,
)

class TestModule4TapeLoader(unittest.TestCase):

    def test_lazy_tape_loading_and_structure(self):
        """Tests that base tapes decompress correctly and contain 720 steps."""
        default_tape = get_base_tape("DEFAULT")
        self.assertGreaterEqual(len(default_tape), 700)
        self.assertIn("farmer", default_tape[0])
        self.assertIn("market", default_tape[0])

    def test_select_active_tape_yarn_detection(self):
        """Tests active route switching when YARN_STORE shops are rolled."""
        obs_default = {
            "town": {"unlocked_shops": ["BAKERY", "PIZZA_SHOP"]}
        }
        tape_default = select_active_tape(obs_default)
        self.assertEqual(len(tape_default), len(get_base_tape("DEFAULT")))

        obs_yarn = {
            "town": {"unlocked_shops": ["YARN_STORE", "BAKERY"]}
        }
        tape_yarn = select_active_tape(obs_yarn)
        self.assertEqual(len(tape_yarn), len(get_base_tape("YARN_FIRST")))

    def test_lookahead_scheduled_sells(self):
        """Tests that upcoming SELL orders are detected in the lookahead horizon."""
        mock_tape = [
            {"market": []},
            {"market": [["BUY_SEED", "WHEAT", 1]]},
            {"market": [["SELL", "MILK", 10]]},
            {"market": [["SELL", "WOOL", 5]]},
        ]

        scheduled = get_lookahead_scheduled_sells(mock_tape, current_step=0, lookahead_steps=3)
        self.assertIn("MILK", scheduled)
        self.assertEqual(scheduled["MILK"], (2, 10))
        self.assertIn("WOOL", scheduled)
        self.assertEqual(scheduled["WOOL"], (3, 5))

if __name__ == "__main__":
    unittest.main()
