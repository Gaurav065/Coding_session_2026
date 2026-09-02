"""Independent, reserve-safe one-tick market-making expert.

The expert does not change the farm route.  It may add one ``BUY_PRODUCT``
order immediately before deterministic town demand and one matching ``SELL``
order on a later turn.  Entry capital is limited to money left after reserving
the current route's investment orders, emergency feed capital, and a fixed
cash floor.  The bought position is accounted for separately from operational
WHEAT so an exit cannot knowingly consume the route's feed stock.

This module is observation-only at runtime.  The complete route is used only
to reserve already-planned public submission actions and to verify that a
future exit has an available market-order slot.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import math
from typing import Any, Iterable

from scripts.v19_terminal import clone_distance
from v23.simulator import execute_sell, market_price
from v23.state_encoder import SHOP_PRODUCTS, get


ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
CROP_COST = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,
}
LAND_COST = (1000, 2000, 4000)


@dataclass(frozen=True)
class MarketMakerConfig:
    enabled: bool = True
    item: str = "WHEAT"
    # A non-WHEAT trading expert must still protect operational animal feed.
    feed_item: str = "WHEAT"
    start_step: int = 260
    stop_entry_step: int = 716
    max_batch: int = 60
    minimum_expected_profit: float = 1.0
    mirror_minimum_expected_profit: float = 1.0
    mirror_distance_threshold: float = 2.0
    mirror_streak_required: int = 48
    minimum_cash_reserve: float = 2500.0
    feed_days_reserve: float = 2.0
    investment_horizon: int = 2
    price_cost_buffer: float = 1.05
    shed_headroom: int = 20
    max_hold_steps: int = 4
    max_orders: int = 10
    shed_capacity: int = 100


@dataclass(frozen=True)
class RoundTripPlan:
    quantity: int
    buy_cost: float
    sell_revenue: float
    expected_profit: float
    inventory_after_buy: int
    inventory_before_sell: int


@dataclass(frozen=True)
class ReserveBreakdown:
    money: float
    cash_floor: float
    feed: float
    investment: float
    available: float


def execute_buy(item: str, inventory: int, quantity: int) -> tuple[int, int]:
    """Exact unilateral BUY_PRODUCT cost under official per-unit pricing."""
    cost = 0
    inventory = int(inventory)
    for _ in range(max(0, int(quantity))):
        quote = market_price(item, inventory - 1)
        cost += quote
        inventory -= 1
    return cost, inventory


def round_trip_plan(
    *,
    item: str,
    inventory: int,
    quantity: int,
    intervening_demand: int,
) -> RoundTripPlan:
    """Buy now, apply known town demand, then liquidate on the next turn."""
    quantity = max(0, int(quantity))
    cost, after_buy = execute_buy(item, inventory, quantity)
    before_sell = after_buy - max(0, int(intervening_demand))
    revenue, _ending_inventory = execute_sell(item, before_sell, quantity)
    return RoundTripPlan(
        quantity=quantity,
        buy_cost=float(cost),
        sell_revenue=float(revenue),
        expected_profit=float(revenue - cost),
        inventory_after_buy=after_buy,
        inventory_before_sell=before_sell,
    )


def best_round_trip_quantity(
    *,
    item: str,
    inventory: int,
    intervening_demand: int,
    maximum_quantity: int,
    minimum_expected_profit: float = 1.0,
) -> RoundTripPlan | None:
    """Return the smallest quantity attaining maximum positive one-tick PnL."""
    rows = [
        round_trip_plan(
            item=item,
            inventory=inventory,
            quantity=quantity,
            intervening_demand=intervening_demand,
        )
        for quantity in range(1, max(0, int(maximum_quantity)) + 1)
    ]
    if not rows:
        return None
    selected = max(rows, key=lambda row: (row.expected_profit, -row.quantity))
    return (
        selected
        if selected.expected_profit >= float(minimum_expected_profit)
        else None
    )


def demand_on_step(obs: Any, configuration: Any, item: str) -> int:
    """Exact visible town demand that executes after this turn's market."""
    step = int(get(obs, "step", 0) or 0)
    town = get(obs, "town", {}) or {}
    shops = list(get(town, "unlocked_shops", []) or [])
    shop_interval = max(
        1, int(get(configuration, "townShopSellInterval", 4) or 4)
    )
    center_interval = max(
        1, int(get(configuration, "townCenterSellInterval", 12) or 12)
    )
    turns_per_day = max(1, int(get(configuration, "turnsPerDay", 24) or 24))
    demand = 0
    if step % shop_interval == 0:
        for shop in shops:
            products = SHOP_PRODUCTS.get(str(shop), ())
            if item in products:
                demand += 2 if len(products) == 1 else 1
    if item != "FERTILIZER" and step % center_interval == 0:
        if center_interval >= 24:
            demand += 1
        else:
            day = step // turns_per_day
            demand += 4 if day >= 20 else 2 if day >= 10 else 1
    return demand


def _seat(obs: Any) -> int:
    return 1 if int(get(obs, "player", 0) or 0) == 1 else 0


def _farm(obs: Any) -> dict:
    seat = _seat(obs)
    farms = list(get(obs, "farms", []) or [])
    return farms[seat] if seat < len(farms) else {}


def _safe_action(action: Any) -> dict:
    copied = copy.deepcopy(action) if isinstance(action, dict) else {}
    copied["farmer"] = list(copied.get("farmer") or ["PASS"])
    copied["hands"] = [
        list(order or ["PASS"]) for order in (copied.get("hands") or [])
    ]
    copied["market"] = [list(order) for order in (copied.get("market") or [])]
    return copied


def _animal_count(farm: dict) -> int:
    return sum(
        isinstance(tile, dict) and bool(tile.get("animal"))
        for row in farm.get("tiles", []) or []
        for tile in row
    )


def _shed_access_tiles(board_size: int) -> set[tuple[int, int]]:
    half = max(1, int(board_size)) // 2
    return {
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    }


def _take(inventory: dict[str, int], item: str, quantity: int) -> int:
    taken = min(
        max(0, int(quantity)),
        max(0, int(inventory.get(item, 0) or 0)),
    )
    if taken:
        left = int(inventory.get(item, 0) or 0) - taken
        if left > 0:
            inventory[item] = left
        else:
            inventory.pop(item, None)
    return taken


def _project_private_after_actor(
    obs: Any,
    action: Any,
    *,
    shed_capacity: int,
) -> tuple[dict[str, int], list[dict[str, int]]]:
    """Project private transfers that matter to feed and MM attribution.

    Actor actions execute before market orders.  Unlike the older terminal
    helper, this projection handles PICKUP as well as DROP/PLACE and consumes
    WHEAT for legal FEED actions.  Harvested WHEAT is deliberately not credited
    to the feed reserve before execution, which keeps that reserve conservative.
    """
    private = get(obs, "private", {}) or {}
    shed = {
        str(item): max(0, int(quantity or 0))
        for item, quantity in dict(get(private, "shed", {}) or {}).items()
    }
    inventories = [
        {
            str(item): max(0, int(quantity or 0))
            for item, quantity in dict(inventory or {}).items()
        }
        for inventory in list(get(private, "inventories", []) or [])
    ]
    farm = _farm(obs)
    positions = [get(farm, "farmer", [0, 0]), *(get(farm, "hands", []) or [])]
    safe = _safe_action(action)
    actor_actions = [safe["farmer"], *safe["hands"]]
    while len(inventories) < len(positions):
        inventories.append({})
    tiles = list(get(farm, "tiles", []) or [])
    board_size = len(tiles) or 10
    access = _shed_access_tiles(board_size)
    animal_structures = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}

    for index, unit_action in enumerate(actor_actions):
        if index >= len(positions) or index >= len(inventories):
            continue
        if not isinstance(unit_action, list) or not unit_action:
            continue
        position = positions[index]
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            continue
        x, y = int(position[0]), int(position[1])
        if not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
            continue
        tile = tiles[y][x]
        inventory = inventories[index]
        operation = str(unit_action[0])

        if operation == "DROP" and (x, y) in access:
            for item, quantity in list(inventory.items()):
                room = max(0, int(shed_capacity) - sum(shed.values()))
                deposited = min(max(0, int(quantity or 0)), room)
                if deposited:
                    shed[item] = shed.get(item, 0) + deposited
                # The official DROP discards overflow rather than retaining it.
                inventory.pop(item, None)
            continue

        if operation == "PICKUP" and (x, y) in access and len(unit_action) >= 2:
            item = str(unit_action[1])
            try:
                requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            except (TypeError, ValueError):
                requested = 0
            taken = _take(shed, item, max(0, requested))
            if taken:
                inventory[item] = inventory.get(item, 0) + taken
            continue

        if operation == "PLACE" and len(unit_action) >= 2:
            item = str(unit_action[1])
            structure = animal_structures.get(item)
            if (
                structure is not None
                and isinstance(tile, dict)
                and tile.get("kind") == structure
                and "animal" not in tile
            ):
                _take(inventory, item, 1)
                continue
            if (x, y) not in access:
                continue
            try:
                requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            except (TypeError, ValueError):
                requested = 0
            room = max(0, int(shed_capacity) - sum(shed.values()))
            deposited = _take(inventory, item, min(max(0, requested), room))
            if deposited:
                shed[item] = shed.get(item, 0) + deposited
            continue

        # Engine 1.32.7 resolves shed operations before checking ownership of
        # the standing tile.  Other tile-mutating operations, including FEED,
        # still no-op while the shed-access tile itself is locked.
        if tile == "LOCKED":
            continue

        if (
            operation == "FEED"
            and isinstance(tile, dict)
            and "animal" in tile
            and not bool(tile.get("fed_today", False))
        ):
            _take(inventory, "WHEAT", 1)

    return shed, inventories


def _fib(index: int) -> int:
    a, b = 1, 1
    for _ in range(max(0, int(index))):
        a, b = b, a + b
    return a


def _order_cost(
    order: list,
    *,
    item_price: float,
    hires_today: int,
    unlocked_quadrants: int,
    hire_multiplier: int,
) -> tuple[float, int, int]:
    """Conservative cost and updated HIRE/LAND counters for one order."""
    if not order:
        return 0.0, hires_today, unlocked_quadrants
    operation = str(order[0])
    if operation == "HIRE":
        return (
            float(max(1, int(hire_multiplier)) * _fib(hires_today)),
            hires_today + 1,
            unlocked_quadrants,
        )
    if operation == "BUY_LAND":
        extra = max(0, unlocked_quadrants - 1)
        cost = LAND_COST[extra] if extra < len(LAND_COST) else 0
        return float(cost), hires_today, unlocked_quadrants + (cost > 0)
    if len(order) < 3:
        return 0.0, hires_today, unlocked_quadrants
    try:
        quantity = max(0, int(order[2]))
    except (TypeError, ValueError):
        quantity = 0
    item = str(order[1])
    if operation == "BUY_SEED":
        cost = CROP_COST.get(item, 0) * quantity
    elif operation == "BUY_ANIMAL":
        cost = ANIMAL_COST.get(item, 0) * quantity
    elif operation == "BUY_PRODUCT":
        cost = max(1.0, float(item_price)) * quantity
    else:
        cost = 0.0
    return float(cost), hires_today, unlocked_quadrants


def planned_investment_cost(
    obs: Any,
    actions: list[dict],
    *,
    start_step: int,
    horizon: int,
    item_price: float,
    hire_multiplier: int = 1,
) -> float:
    """Reserve route costs over a short hold/exit window without sale credit."""
    farm = _farm(obs)
    current_day = int(get(obs, "day", start_step // 24) or 0)
    hires_today = int(get(farm, "hires_today", 0) or 0)
    quadrants = len(get(farm, "unlocked_quadrants", []) or [])
    total = 0.0
    last_day = current_day
    stop = min(len(actions), start_step + max(0, int(horizon)))
    for step in range(max(0, int(start_step)), stop):
        day = step // 24
        if day != last_day:
            hires_today = 0
            last_day = day
        action = actions[step] if step < len(actions) else {}
        for order in (action or {}).get("market", []) or []:
            cost, hires_today, quadrants = _order_cost(
                list(order),
                item_price=item_price,
                hires_today=hires_today,
                unlocked_quadrants=quadrants,
                hire_multiplier=hire_multiplier,
            )
            total += cost
    return total


def reserve_breakdown(
    obs: Any,
    actions: list[dict],
    configuration: Any,
    config: MarketMakerConfig,
    current_action: Any | None = None,
) -> ReserveBreakdown:
    farm = _farm(obs)
    money = float(get(farm, "money", 0) or 0)
    step = int(get(obs, "step", 0) or 0)
    market = get(obs, "market", {}) or {}
    inventory = get(market, "inventory", {}) or {}
    item_inventory = int(get(inventory, config.item, 10000) or 10000)
    current_quote = float(market_price(config.item, item_inventory))
    feed_item = str(config.feed_item or "WHEAT")
    feed_inventory = int(get(inventory, feed_item, 10000) or 10000)
    feed_quote = float(market_price(feed_item, feed_inventory))

    action = (
        current_action
        if current_action is not None
        else actions[step] if 0 <= step < len(actions) else {}
    )
    official_shed_capacity = int(
        get(configuration, "shedCapacity", config.shed_capacity)
        or config.shed_capacity
    )
    effective_shed_capacity = min(
        int(config.shed_capacity), max(1, official_shed_capacity)
    )
    projected_shed, projected_inventories = _project_private_after_actor(
        obs,
        action,
        shed_capacity=effective_shed_capacity,
    )
    projected_wheat = max(
        0, int(projected_shed.get(feed_item, 0) or 0)
    ) + sum(
        max(0, int(inventory.get(feed_item, 0) or 0))
        for inventory in projected_inventories
    )
    # Existing SELL commitments reduce protected stock.  Existing BUY orders
    # are not credited until they execute, so their failure cannot weaken the
    # feed reserve.
    for raw in (_safe_action(action).get("market", []) or []):
        order = list(raw or [])
        if len(order) < 3 or str(order[1]) != feed_item or order[0] != "SELL":
            continue
        try:
            projected_wheat = max(0, projected_wheat - max(0, int(order[2])))
        except (TypeError, ValueError):
            continue

    required_feed = int(
        math.ceil(_animal_count(farm) * max(0.0, config.feed_days_reserve))
    )
    feed_deficit = max(0, required_feed - projected_wheat)
    if feed_deficit:
        feed_cost, _ = execute_buy(feed_item, feed_inventory, feed_deficit)
    else:
        feed_cost = 0
    feed = float(feed_cost) * max(1.0, float(config.price_cost_buffer))

    investment = planned_investment_cost(
        obs,
        actions,
        start_step=step,
        horizon=max(1, int(config.investment_horizon)),
        item_price=feed_quote,
        hire_multiplier=int(get(configuration, "farmHandCostMult", 1) or 1),
    ) * max(1.0, float(config.price_cost_buffer))
    available = max(
        0.0,
        money - float(config.minimum_cash_reserve) - feed - investment,
    )
    return ReserveBreakdown(
        money=money,
        cash_floor=float(config.minimum_cash_reserve),
        feed=feed,
        investment=investment,
        available=available,
    )


def _shed_after_market(
    projected: dict[str, int],
    market: Iterable[list],
    *,
    shed_capacity: int,
) -> dict[str, int]:
    """Conservative unilateral shed projection for capacity accounting."""
    shed = {str(item): max(0, int(quantity or 0)) for item, quantity in projected.items()}
    for raw in market:
        order = list(raw or [])
        if len(order) < 3:
            continue
        operation, item = str(order[0]), str(order[1])
        try:
            quantity = max(0, int(order[2]))
        except (TypeError, ValueError):
            quantity = 0
        if operation == "SELL":
            shed[item] = max(0, shed.get(item, 0) - quantity)
        elif operation in ("BUY_PRODUCT", "BUY_ANIMAL"):
            room = max(0, int(shed_capacity) - sum(shed.values()))
            shed[item] = shed.get(item, 0) + min(quantity, room)
    return shed


def _wheat_after_market(quantity: int, market: Iterable[list], item: str) -> int:
    quantity = max(0, int(quantity))
    for raw in market:
        order = list(raw or [])
        if len(order) < 3 or str(order[1]) != item:
            continue
        try:
            units = max(0, int(order[2]))
        except (TypeError, ValueError):
            units = 0
        if order[0] == "SELL":
            quantity = max(0, quantity - units)
        elif order[0] == "BUY_PRODUCT":
            quantity += units
    return quantity


def _inventory_after_wheat_orders(
    inventory: int, market: Iterable[list], item: str
) -> int:
    inventory = int(inventory)
    for raw in market:
        order = list(raw or [])
        if len(order) < 3 or str(order[1]) != item:
            continue
        try:
            units = max(0, int(order[2]))
        except (TypeError, ValueError):
            units = 0
        if order[0] == "SELL":
            _revenue, inventory = execute_sell(item, inventory, units)
        elif order[0] == "BUY_PRODUCT":
            _cost, inventory = execute_buy(item, inventory, units)
    return inventory


class MarketMakerExpert:
    """Stateful expert that owns only its incremental market position."""

    def __init__(self, actions: list[dict], config: MarketMakerConfig | None = None):
        self.actions = copy.deepcopy(actions)
        self.config = config or MarketMakerConfig()
        self.states = {0: {}, 1: {}}
        self.telemetry = {
            "games": 0,
            "entries": 0,
            "entry_units": 0,
            "exits": 0,
            "exit_units": 0,
            "position_consumed_units": 0,
            "expected_profit": 0.0,
            "cash_blocks": 0,
            "capacity_blocks": 0,
            "slot_blocks": 0,
            "edge_blocks": 0,
            "deferred_exits": 0,
            "mirror_latches": 0,
            "mirror_entries": 0,
            "deployed_cash": 0.0,
            "maximum_feed_reserve": 0.0,
            "maximum_investment_reserve": 0.0,
            "minimum_entry_headroom": None,
        }

    def _reset(self, seat: int, step: int) -> dict:
        state = {
            "last_step": step,
            "open_units": 0,
            "entry_step": -1,
            "baseline_wheat": 0,
            "near_streak": 0,
            "mirror_mode": None,
        }
        self.states[seat] = state
        self.telemetry["games"] += 1
        return state

    def _future_has_exit_slot(self, step: int, max_orders: int) -> bool:
        exit_step = step + 1
        if exit_step >= len(self.actions):
            return False
        market = (self.actions[exit_step] or {}).get("market", []) or []
        return len(market) < int(max_orders)

    def _exit(
        self,
        obs: Any,
        action: dict,
        state: dict,
        configuration: Any,
    ) -> dict:
        market = list(action.get("market", []) or [])
        max_orders = min(
            int(self.config.max_orders),
            max(
                1,
                int(
                    get(
                        configuration,
                        "maxMarketOrdersPerTurn",
                        self.config.max_orders,
                    )
                    or self.config.max_orders
                ),
            ),
        )
        if len(market) >= max_orders:
            self.telemetry["slot_blocks"] += 1
            self.telemetry["deferred_exits"] += 1
            return action
        private = get(obs, "private", {}) or {}
        shed = get(private, "shed", {}) or {}
        observed_wheat = max(0, int(get(shed, self.config.item, 0) or 0))
        official_shed_capacity = int(
            get(configuration, "shedCapacity", self.config.shed_capacity)
            or self.config.shed_capacity
        )
        effective_shed_capacity = min(
            int(self.config.shed_capacity), max(1, official_shed_capacity)
        )
        projected, _inventories = _project_private_after_actor(
            obs,
            action,
            shed_capacity=effective_shed_capacity,
        )
        projected_wheat = max(0, int(projected.get(self.config.item, 0) or 0))
        actor_delta = projected_wheat - observed_wheat
        operational = max(0, int(state.get("baseline_wheat", 0)) + actor_delta)
        operational = _wheat_after_market(operational, market, self.config.item)
        total = _wheat_after_market(projected_wheat, market, self.config.item)
        available_position = max(0, total - operational)
        open_units = max(0, int(state.get("open_units", 0)))
        quantity = min(open_units, available_position)
        consumed = max(0, open_units - quantity)
        if consumed:
            # Actor actions execute before the market.  If part of the
            # incremental position was picked up or otherwise consumed, it is
            # no longer an open market position and must not block future
            # entries.  The operational route owns those units from here.
            self.telemetry["position_consumed_units"] += consumed
        if quantity <= 0:
            state["open_units"] = 0
            state["baseline_wheat"] = operational
            return action
        market.append(["SELL", self.config.item, quantity])
        action["market"] = market
        state["open_units"] = 0
        state["baseline_wheat"] = operational
        self.telemetry["exits"] += 1
        self.telemetry["exit_units"] += quantity
        return action

    def _entry(self, obs: Any, action: dict, configuration: Any, state: dict) -> dict:
        step = int(get(obs, "step", 0) or 0)
        if not (
            self.config.enabled
            and int(self.config.start_step) <= step <= int(self.config.stop_entry_step)
        ):
            return action
        demand = demand_on_step(obs, configuration, self.config.item)
        if demand <= 0:
            return action
        market_orders = list(action.get("market", []) or [])
        max_orders = min(
            int(self.config.max_orders),
            max(
                1,
                int(
                    get(
                        configuration,
                        "maxMarketOrdersPerTurn",
                        self.config.max_orders,
                    )
                    or self.config.max_orders
                ),
            ),
        )
        if len(market_orders) >= max_orders or not self._future_has_exit_slot(
            step, max_orders
        ):
            self.telemetry["slot_blocks"] += 1
            return action

        official_shed_capacity = int(
            get(configuration, "shedCapacity", self.config.shed_capacity)
            or self.config.shed_capacity
        )
        effective_shed_capacity = min(
            int(self.config.shed_capacity), max(1, official_shed_capacity)
        )
        projected, _inventories = _project_private_after_actor(
            obs,
            action,
            shed_capacity=effective_shed_capacity,
        )
        after_base = _shed_after_market(
            projected,
            market_orders,
            shed_capacity=effective_shed_capacity,
        )
        capacity = max(
            0,
            effective_shed_capacity
            - int(self.config.shed_headroom)
            - sum(after_base.values()),
        )
        if capacity <= 0:
            self.telemetry["capacity_blocks"] += 1
            return action

        reserve = reserve_breakdown(
            obs,
            self.actions,
            configuration,
            self.config,
            current_action=action,
        )
        if reserve.available <= 0:
            self.telemetry["cash_blocks"] += 1
            return action

        market = get(obs, "market", {}) or {}
        inventories = get(market, "inventory", {}) or {}
        inventory = int(get(inventories, self.config.item, 10000) or 10000)
        inventory = _inventory_after_wheat_orders(
            inventory, market_orders, self.config.item
        )
        maximum = min(int(self.config.max_batch), capacity)
        affordable = 0
        for quantity in range(1, maximum + 1):
            cost, _ = execute_buy(self.config.item, inventory, quantity)
            if cost * max(1.0, float(self.config.price_cost_buffer)) > reserve.available:
                break
            affordable = quantity
        if affordable <= 0:
            self.telemetry["cash_blocks"] += 1
            return action

        threshold = (
            float(self.config.mirror_minimum_expected_profit)
            if state.get("mirror_mode")
            else float(self.config.minimum_expected_profit)
        )
        plan = best_round_trip_quantity(
            item=self.config.item,
            inventory=inventory,
            intervening_demand=demand,
            maximum_quantity=affordable,
            minimum_expected_profit=threshold,
        )
        if plan is None:
            self.telemetry["edge_blocks"] += 1
            return action

        market_orders.append(["BUY_PRODUCT", self.config.item, plan.quantity])
        action["market"] = market_orders
        state["open_units"] = plan.quantity
        state["entry_step"] = step
        state["baseline_wheat"] = _wheat_after_market(
            max(0, int(projected.get(self.config.item, 0) or 0)),
            market_orders[:-1],
            self.config.item,
        )
        self.telemetry["entries"] += 1
        if state.get("mirror_mode"):
            self.telemetry["mirror_entries"] += 1
        self.telemetry["entry_units"] += plan.quantity
        self.telemetry["expected_profit"] += plan.expected_profit
        self.telemetry["deployed_cash"] += plan.buy_cost
        self.telemetry["maximum_feed_reserve"] = max(
            float(self.telemetry["maximum_feed_reserve"]), reserve.feed
        )
        self.telemetry["maximum_investment_reserve"] = max(
            float(self.telemetry["maximum_investment_reserve"]),
            reserve.investment,
        )
        headroom = reserve.available - (
            plan.buy_cost * max(1.0, float(self.config.price_cost_buffer))
        )
        prior_headroom = self.telemetry["minimum_entry_headroom"]
        self.telemetry["minimum_entry_headroom"] = (
            headroom
            if prior_headroom is None
            else min(float(prior_headroom), headroom)
        )
        return action

    def apply(self, obs: Any, action: Any, configuration: Any = None) -> dict:
        result = _safe_action(action)
        seat = _seat(obs)
        step = int(get(obs, "step", 0) or 0)
        state = self.states[seat]
        if step == 0 or step < int(state.get("last_step", -1)):
            state = self._reset(seat, step)
        state["last_step"] = step
        distance = clone_distance(obs)
        if distance <= float(self.config.mirror_distance_threshold):
            state["near_streak"] = int(state.get("near_streak", 0)) + 1
        else:
            state["near_streak"] = 0
        if state.get("mirror_mode") is None and step >= int(self.config.start_step):
            state["mirror_mode"] = (
                int(state.get("near_streak", 0))
                >= int(self.config.mirror_streak_required)
            )
            if state["mirror_mode"]:
                self.telemetry["mirror_latches"] += 1

        if int(state.get("open_units", 0)) > 0:
            result = self._exit(obs, result, state, configuration)
            if int(state.get("open_units", 0)) > 0:
                age = step - int(state.get("entry_step", step))
                if age >= int(self.config.max_hold_steps):
                    self.telemetry["deferred_exits"] += 1
                return result
            # Do not immediately re-enter on the same turn as an exit.
            return result
        return self._entry(obs, result, configuration, state)


def wrap_market_maker(base_policy, actions, config: MarketMakerConfig | None = None):
    expert = MarketMakerExpert(actions, config)

    def policy(obs, configuration=None):
        return expert.apply(obs, base_policy(obs, configuration), configuration)

    policy.expert = expert
    policy.telemetry = expert.telemetry
    policy.config = expert.config
    return policy
