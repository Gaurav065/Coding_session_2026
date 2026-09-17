# SPDX-License-Identifier: Apache-2.0
"""Global configuration, economy parameters, and timing constants for Modular Apex."""

TURNS_PER_DAY = 24
ROUTE_STEP = 144
FINAL_PLAN_STEP = 648
LAST_STEP = 718
SHED_CAPACITY = 100
MAX_ORDERS = 10

PRODUCTS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)

SEED_PRICES = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,
}

ANIMAL_COSTS = {
    "COW": 400,
    "SHEEP": 500,
}

ANIMALS = {"COW", "SHEEP"}
CRASH_DUMP_ITEMS = ("STRAWBERRY", "MELON", "MILK", "WOOL", "TOMATO", "CARROT")
PIZZA_EXPANSION_THRESHOLD = 2
WEED_BLOCKED_WORK = {"PLANT", "BUILD_PASTURE"}


# Default reactive layer settings
CHASSIS_SETTINGS = {
    'hand_align': True,
    'weed_repair': True,
    'sell_lead': True,
    'front_run': False,
    'market_crash': True,
    'budget_guard': False,
    'room_guard': False,
    'clamp_sells': True,
    'dead_stock': False,
    'terminal_liquidation': False,
}

# Clean Opening Sequence (eliminates Day 0 bid-ask spread loss in Seat 1)
CLEAN_OPENING = [["BUY_PRODUCT", "WHEAT", 13]]

# Exact Day-0 Cash Floor ($10.0 guarantees funding for 3 morning workers at Step 25)
DAY0_CASH_FLOOR = 10.0
