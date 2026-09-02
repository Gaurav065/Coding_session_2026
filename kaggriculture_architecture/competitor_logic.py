# SPDX-License-Identifier: Apache-2.0
"""ShopForge Fieldbook: six readable plans and a small public-state tree.

Generated from the public ShopForge episodes listed in ROUTE_SOURCES.
There is no compressed action blob and no exact-money lookup table.
"""

from __future__ import annotations

import copy

ITEMS = ('WHEAT',
 'CARROT',
 'TOMATO',
 'STRAWBERRY',
 'MELON',
 'EGG',
 'MILK',
 'WOOL',
 'FERTILIZER',
 'GOOSE',
 'COW',
 'SHEEP')
PRODUCTS = ITEMS[:9]
ROUTE_SOURCES = {0: {'action_sha256': '3319bb4e555847149dd5c82d3626a697056455d120fca487de52e1d5f4a9bfd4',
     'episode_id': 103823935,
     'label': 'BALANCED'},
 2: {'action_sha256': '39be02a28445bcd831735e8234903f1ccc1f5f2951ec66989bb9dcd0ea7e5df3',
     'episode_id': 104056237,
     'label': 'CASH_RECOVERY'},
 3: {'action_sha256': '94ef053e8ec78494c3df5d4e77a38e5e1d4306f263fbe8bf89ce6d4aab1572fe',
     'episode_id': 103609700,
     'label': 'YARN_ENGINE'},
 14: {'action_sha256': '45edb4cacfc0b74a450222454b0de14559399e3ae10267ea22035a50b2523729',
      'episode_id': 103576156,
      'label': 'YARN_LATE'},
 16: {'action_sha256': 'ec38433bc7080fca2139d2e2cae735f2c4a3c23c145a8e60c6762a41ff4ffab0',
      'episode_id': 103926612,
      'label': 'LAND_RECOVERY'},
 18: {'action_sha256': '355effb1b7a24b0fe98715e5b86b30e6cd19ff2312922f6c3ba845dd11f598bf',
      'episode_id': 103908697,
      'label': 'WHEAT_RECOVERY'}}
ROUTE_NAMES = {index: row["label"] for index, row in ROUTE_SOURCES.items()}

DEFAULT_SETTINGS = {
    "branch_depth": 2,
    "sell_lead": True,
    "terminal_liquidation": True,
    "severe_cash_gap": -199.0,
    "very_severe_cash_gap": -721.5,
    "wheat_cheap": 29.5,
    "low_cash": 242.5,
}

# One line is: step | farmer, hands... | market orders.
# The first unit is the farmer. Remaining units are farm hands.
from fieldbook_tapes import PLAN_SCRIPTS

# <FIELD_BOOK_PLAN_SCRIPTS>


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def _parse_token(token):
    parts = token.split(":")
    action = [parts[0]]
    for value in parts[1:]:
        action.append(int(value) if value.lstrip("-").isdigit() else value)
    return action


def _decode_plan(script):
    result = {}
    for line in script.splitlines():
        step_text, units_text, market_text = line.split("|", 2)
        units = [_parse_token(token) for token in units_text.split(",")]
        market = [] if market_text == "-" else [
            _parse_token(token) for token in market_text.split(",")
        ]
        result[int(step_text)] = {
            "farmer": units[0],
            "hands": units[1:],
            "market": market,
        }
    return result


_SEGMENTS = {name: _decode_plan(script) for name, script in PLAN_SCRIPTS.items()}


def _compose(root_name, tail_name):
    actions = [None] * 719
    for segment_name in ("OPENING_000_143", root_name, tail_name):
        for step, action in _SEGMENTS[segment_name].items():
            if actions[step] is not None:
                raise ValueError(f"overlapping Fieldbook step {step}")
            actions[step] = action
    if any(action is None for action in actions):
        raise ValueError("Fieldbook route has a missing step")
    return actions


ROUTES = {
    0: _compose("ROOT_BALANCED_144_215", "TAIL_BALANCED_216_718"),
    2: _compose("ROOT_BALANCED_144_215", "TAIL_CASH_RECOVERY_216_718"),
    3: _compose("ROOT_YARN_144_215", "TAIL_YARN_ENGINE_216_718"),
    14: _compose("ROOT_BALANCED_144_215", "TAIL_YARN_LATE_216_718"),
    16: _compose("ROOT_LAND_RECOVERY_144_215", "TAIL_LAND_RECOVERY_216_718"),
    18: _compose("ROOT_LAND_RECOVERY_144_215", "TAIL_WHEAT_RECOVERY_216_718"),
}


def _step(observation):
    raw = _get(observation, "step")
    if raw is not None:
        return int(raw)
    return int(_get(observation, "day", 0) or 0) * 24 + int(
        _get(observation, "hour", 0) or 0
    )


def _shops(observation):
    town = _get(observation, "town", {}) or {}
    return list(_get(town, "unlocked_shops", []) or [])


def _farm_pair(observation):
    farms = list(_get(observation, "farms", []) or [])
    player = int(_get(observation, "player", 0) or 0)
    own = farms[player] if player < len(farms) else {}
    rival = farms[1 - player] if len(farms) >= 2 else {}
    return player, own, rival


def _capture_step144(observation):
    _, own, rival = _farm_pair(observation)
    market = _get(observation, "market", {}) or {}
    prices = _get(market, "prices", {}) or {}
    own_money = float(_get(own, "money", 0.0) or 0.0)
    rival_money = float(_get(rival, "money", 0.0) or 0.0)
    own_land = len(list(_get(own, "unlocked_quadrants", []) or []))
    rival_land = len(list(_get(rival, "unlocked_quadrants", []) or []))
    return {
        "shops": _shops(observation)[:2],
        "cash": own_money,
        "cash_gap": own_money - rival_money,
        "land_gap": own_land - rival_land,
        "wheat_price": float(_get(prices, "WHEAT", 0.0) or 0.0),
    }


def _root_choice(cache):
    shops = cache["shops"]
    first = shops[0] if len(shops) >= 1 else None
    second = shops[1] if len(shops) >= 2 else None
    if first == "YARN_STORE":
        return "YARN", 3
    if second == "YARN_STORE":
        if cache["land_gap"] < 0:
            return "LAND_RECOVERY", 16
        return "YARN", 3
    return "BALANCED", 0


def _terminal_choice(group, cache, third_shop, settings):
    if group == "YARN":
        return 3
    if group == "LAND_RECOVERY":
        if cache["cash_gap"] <= settings["severe_cash_gap"]:
            if cache["wheat_price"] <= settings["wheat_cheap"]:
                return 18 if cache["cash"] <= settings["low_cash"] else 16
            return 16 if cache["cash_gap"] <= settings["very_severe_cash_gap"] else 18
        second = cache["shops"][1] if len(cache["shops"]) >= 2 else None
        if second != "BRUNCH_SPOT" and third_shop != "FARMERS_MARKET":
            return 16
        return 18
    second = cache["shops"][1] if len(cache["shops"]) >= 2 else None
    if third_shop != "YARN_STORE" and second != "YARN_STORE":
        return 2 if cache["cash_gap"] < 0 else 0
    return 14


def _configuration(configuration, key, default):
    return _get(configuration or {}, key, default)


def _order_limit(configuration):
    return max(0, min(16, int(_configuration(configuration, "maxMarketOrdersPerTurn", 10))))


def _shed_adjacent(position, board_size):
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        return False
    half = board_size // 2
    return position[0] in {half - 1, half} and position[1] in {half - 1, half}


def _projected_shed(observation, action, configuration):
    _, own, _ = _farm_pair(observation)
    private = _get(observation, "private", {}) or {}
    shed = _get(private, "shed", {}) or {}
    projected = {item: max(0, int(_get(shed, item, 0) or 0)) for item in PRODUCTS}
    total = sum(projected.values())
    capacity = int(_configuration(configuration, "shedCapacity", 100))
    board_size = int(_configuration(configuration, "boardSize", 10))
    positions = [_get(own, "farmer", None), *list(_get(own, "hands", []) or [])]
    inventories = list(_get(private, "inventories", []) or [])
    unit_actions = [action.get("farmer") or ["PASS"], *list(action.get("hands") or [])]
    for index, unit_action in enumerate(unit_actions[: len(positions)]):
        if not _shed_adjacent(positions[index], board_size):
            continue
        operation = unit_action[0] if unit_action else "PASS"
        if operation == "PICKUP" and len(unit_action) >= 2 and unit_action[1] in projected:
            requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            quantity = min(projected[unit_action[1]], max(0, requested))
            projected[unit_action[1]] -= quantity
            total -= quantity
        elif operation == "DROP":
            inventory = inventories[index] if index < len(inventories) else {}
            for item in ITEMS:
                held = max(0, int(_get(inventory, item, 0) or 0))
                room = max(0, capacity - total)
                dropped = min(held, room)
                if item in projected:
                    projected[item] += dropped
                total += dropped
    return projected


def _suppress_advanced_sale(action, sell_state, step):
    if sell_state.get("due_step") != step:
        return action
    remaining = dict(sell_state.get("suppress", {}))
    kept = []
    for order in action.get("market", []):
        order = list(order)
        if order and order[0] == "SELL" and len(order) >= 3 and remaining.get(order[1], 0) > 0:
            removed = min(max(0, int(order[2])), remaining[order[1]])
            order[2] -= removed
            remaining[order[1]] -= removed
        if not order or order[0] != "SELL" or int(order[2]) > 0:
            kept.append(order)
    action["market"] = kept
    return action


def _lead_sale(observation, action, future_action, sell_state, step, configuration):
    next_state = {"due_step": -1, "suppress": {}}
    future_step = step + 1
    unlock_period = int(_configuration(configuration, "townShopUnlockInterval", 3)) * int(
        _configuration(configuration, "turnsPerDay", 24)
    )
    demand_period = int(_configuration(configuration, "townShopSellInterval", 4))
    if future_step >= 719 or future_step % max(1, unlock_period) == 0 or step % max(1, demand_period) == 0:
        sell_state.clear()
        sell_state.update(next_state)
        return action
    projected = _projected_shed(observation, action, configuration)
    prices = _get(_get(observation, "market", {}) or {}, "prices", {}) or {}
    planned = {item: 0 for item in PRODUCTS}
    for order in future_action.get("market", []):
        if order and order[0] == "SELL" and order[1] in planned:
            planned[order[1]] += max(0, int(order[2]))
    already = {order[1] for order in action.get("market", []) if order and order[0] == "SELL"}
    for item in PRODUCTS:
        if item in {"WHEAT", "FERTILIZER"} or planned[item] <= 0 or item in already:
            continue
        quantity = min(projected[item], planned[item])
        if quantity <= 0 or float(_get(prices, item, 0) or 0) < 2:
            continue
        if len(action.get("market", [])) >= _order_limit(configuration):
            break
        action.setdefault("market", []).append(["SELL", item, quantity])
        next_state["suppress"][item] = quantity
    if next_state["suppress"]:
        next_state["due_step"] = future_step
    sell_state.clear()
    sell_state.update(next_state)
    return action


def _terminal_sale(observation, action, step, configuration):
    episode_steps = int(_configuration(configuration, "episodeSteps", 720))
    if step < episode_steps - 2:
        return action
    projected = _projected_shed(observation, action, configuration)
    action["market"] = [
        ["SELL", item, quantity]
        for item, quantity in projected.items()
        if quantity > 0
    ][:_order_limit(configuration)]
    return action


class FieldbookRuntime:
    """Stateful but readable route selection and SELL timing."""

    def __init__(self, **overrides):
        self.settings = {**DEFAULT_SETTINGS, **overrides}
        self.route_state = {}
        self.sell_state = {}

    def _route(self, observation, step, player):
        if self.settings["branch_depth"] <= 0 or step < 144:
            return 0
        state = self.route_state.get(player)
        if state is None or state.get("stage", 0) < 2:
            cache = _capture_step144(observation)
            group, route = _root_choice(cache)
            state = {"stage": 2, "cache": cache, "group": group, "route": route}
            self.route_state[player] = state
        if self.settings["branch_depth"] >= 2 and step >= 216 and state["stage"] < 3:
            shops = _shops(observation)
            third = shops[2] if len(shops) >= 3 else None
            state["route"] = _terminal_choice(state["group"], state["cache"], third, self.settings)
            state["stage"] = 3
        return state["route"]

    def act(self, observation, configuration=None):
        step = min(max(_step(observation), 0), 718)
        player, own, _ = _farm_pair(observation)
        if step == 0:
            self.route_state.pop(player, None)
            self.sell_state[player] = {"due_step": -1, "suppress": {}}
        route = self._route(observation, step, player)
        action = copy.deepcopy(ROUTES[route][step])
        expected_hands = len(list(_get(own, "hands", []) or []))
        hands = list(action.get("hands") or [])
        hands.extend([["PASS"] for _ in range(max(0, expected_hands - len(hands)))])
        action["hands"] = hands[:expected_hands]

        state = self.sell_state.setdefault(player, {"due_step": -1, "suppress": {}})
        action = _suppress_advanced_sale(action, state, step)
        if self.settings["sell_lead"]:
            future = ROUTES[route][step + 1] if step + 1 < 719 else {"market": []}
            action = _lead_sale(observation, action, future, state, step, configuration)
        else:
            state.clear()
            state.update({"due_step": -1, "suppress": {}})
        if self.settings["terminal_liquidation"]:
            action = _terminal_sale(observation, action, step, configuration)
        return action


def make_agent(**overrides):
    runtime = FieldbookRuntime(**overrides)

    def policy(observation, configuration=None):
        return runtime.act(observation, configuration)

    policy.runtime = runtime
    return policy


agent = make_agent()
main = agent
