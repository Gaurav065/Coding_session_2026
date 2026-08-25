"""Project Aegis - Module 2: The River (Continuous Trickle-Selling & Queue Engine)

Contains:
1. Dynamic Scaled Trickle-Selling (Production Phase).
2. Shed Pressure Valve with Wave-2 Melon & Harvest Protection (keeps shed < 40 on Days 20-27).
3. Defensive Liquidity Guard (3-step Lookahead Capex).
4. AMM Quadratic Price Floor Protection for Melons and Premium goods.
"""

from typing import Dict, List, Any, Optional
from project_aegis.core import (
    ALL_PRODUCTS,
    PREMIUM_PRODUCTS,
    MARKET_PARAMS,
    MAX_MARKET_ORDERS,
    PRICE_FLOOR,
    calculate_single_unit_price,
    get_active_animal_count,
)

PRODUCTION_PHASE_START_STEP = 288  # Day 12
SHED_FLUSH_THRESHOLD = 75
DEFAULT_SHED_FLUSH_THRESHOLD = SHED_FLUSH_THRESHOLD
PRE_HARVEST_SHED_FLUSH_THRESHOLD = 40
PRICE_FLOOR_PAUSE_RATIO = 0.60


class LiquidityGuard:
    """Defensive 3-step Lookahead Capex and Urgent Liquidation Engine."""

    @staticmethod
    def calculate_upcoming_capex(future_tape_slice: List[Dict[str, Any]], current_quadrants_count: int) -> float:
        total_capex = 0.0
        quad_idx = current_quadrants_count

        for action_dict in future_tape_slice:
            market_orders = action_dict.get("market", []) or []
            for order in market_orders:
                if not isinstance(order, list) or len(order) == 0:
                    continue
                op = order[0]
                if op == "BUY_LAND":
                    cost = 1000.0 if quad_idx == 1 else (2000.0 if quad_idx == 2 else 4000.0)
                    total_capex += cost
                    quad_idx += 1
                elif op == "BUY_ANIMAL" and len(order) >= 2:
                    animal = order[1]
                    n = int(order[2]) if len(order) >= 3 else 1
                    unit_c = 800.0 if animal == "COW" else (600.0 if animal == "SHEEP" else 300.0)
                    total_capex += unit_c * n
                elif op == "BUY_SEED" and len(order) >= 2:
                    seed = order[1]
                    n = int(order[2]) if len(order) >= 3 else 1
                    unit_c = 60.0 if seed == "STRAWBERRY" else (20.0 if seed == "MELON" else (10.0 if seed == "WHEAT" else 5.0))
                    total_capex += unit_c * n
                elif op == "BUY_PRODUCT" and len(order) >= 2:
                    prod = order[1]
                    n = int(order[2]) if len(order) >= 3 else 1
                    unit_c = 25.0 if prod == "WHEAT" else 40.0
                    total_capex += unit_c * n

        return total_capex

    @staticmethod
    def ensure_liquidity(
        obs: Dict[str, Any],
        current_market_orders: List[List[Any]],
        upcoming_capex: float = 0.0,
        needed_cash: Optional[float] = None,
    ) -> List[List[Any]]:
        required_cash = needed_cash if needed_cash is not None else upcoming_capex
        player = obs.get("player", 0)
        farms = obs.get("farms", [{}, {}])
        my_farm = farms[player] if len(farms) > player else {}
        money = float(my_farm.get("money", 0.0) or 0.0)

        if money >= required_cash:
            return []

        shortfall = required_cash - money
        shed = (obs.get("private") or {}).get("shed", {}) or {}
        market_prices = obs.get("market", {}).get("prices", {}) or {}

        already_selling: Dict[str, int] = {}
        for order in current_market_orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                already_selling[order[1]] = already_selling.get(order[1], 0) + max(0, int(order[2] or 0))

        live_animals = get_active_animal_count(obs)
        wheat_feed_reserve = live_animals * 2

        urgent_orders: List[List[Any]] = []
        recovered_cash = 0.0

        sellable_products = [p for p in ALL_PRODUCTS if p != "WHEAT"] + ["WHEAT"]
        sorted_products = sorted(
            sellable_products,
            key=lambda item: market_prices.get(item, MARKET_PARAMS[item]["base"]),
            reverse=True
        )

        for item in sorted_products:
            if recovered_cash >= shortfall or len(current_market_orders) + len(urgent_orders) >= MAX_MARKET_ORDERS:
                break

            total_held = int(shed.get(item, 0) or 0)
            avail = max(0, total_held - already_selling.get(item, 0))

            if item == "WHEAT":
                avail = max(0, avail - wheat_feed_reserve)

            if avail <= 0:
                continue

            unit_p = max(PRICE_FLOOR, market_prices.get(item, MARKET_PARAMS[item]["base"]))
            needed_units = int((shortfall - recovered_cash + unit_p - 1) // unit_p)
            sell_qty = min(avail, max(1, needed_units))

            urgent_orders.append(["SELL", item, sell_qty])
            already_selling[item] = already_selling.get(item, 0) + sell_qty
            recovered_cash += sell_qty * unit_p

        return urgent_orders


class RiverEngine:
    """Continuous trickle-selling and queue management engine."""

    def __init__(self):
        self.pending_sell_queue: Dict[str, int] = {item: 0 for item in ALL_PRODUCTS}

    def process_tape_orders(self, tape_market_orders: List[List[Any]], step: int) -> List[List[Any]]:
        has_buys = any(
            isinstance(o, list) and len(o) > 0 and (o[0].startswith("BUY") or o[0] == "HIRE")
            for o in tape_market_orders
        )

        if step < PRODUCTION_PHASE_START_STEP or has_buys:
            return list(tape_market_orders)

        retained_orders = []
        for order in tape_market_orders:
            if not isinstance(order, list) or len(order) == 0:
                continue
            if order[0] == "SELL" and len(order) >= 3:
                item = order[1]
                qty = max(0, int(order[2] or 0))
                if item in self.pending_sell_queue:
                    self.pending_sell_queue[item] += qty
            else:
                retained_orders.append(order)
        return retained_orders

    def generate_trickle_orders(
        self,
        obs: Dict[str, Any],
        current_market_orders: List[List[Any]],
        future_tape_slice: List[Dict[str, Any]],
    ) -> List[List[Any]]:
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        player = obs.get("player", 0)
        farms = obs.get("farms", [{}, {}])
        my_farm = farms[player] if len(farms) > player else {}
        my_quads_count = len(my_farm.get("unlocked_quadrants", ["NW"]))

        shed = (obs.get("private") or {}).get("shed", {}) or {}
        market_prices = obs.get("market", {}).get("prices", {}) or {}
        market_inv = obs.get("market", {}).get("inventory", {}) or {}

        total_shed_count = sum(max(0, int(v or 0)) for v in shed.values())
        live_animals = get_active_animal_count(obs)
        wheat_feed_reserve = live_animals * 2

        # 1. Defensive Liquidity Check for next 3 steps
        immediate_slice = future_tape_slice[:3]
        upcoming_capex = LiquidityGuard.calculate_upcoming_capex(immediate_slice, my_quads_count)
        liquidity_orders = LiquidityGuard.ensure_liquidity(obs, current_market_orders, upcoming_capex)

        dispatched_orders = list(current_market_orders) + liquidity_orders

        if step < PRODUCTION_PHASE_START_STEP:
            return dispatched_orders[:MAX_MARKET_ORDERS]

        already_selling: Dict[str, int] = {}
        for order in dispatched_orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                already_selling[order[1]] = already_selling.get(order[1], 0) + max(0, int(order[2] or 0))

        # 2. Pre-Harvest Shed Pressure Valve (Protects Wave-2 Melon deposits from 100-cap discard)
        flush_threshold = PRE_HARVEST_SHED_FLUSH_THRESHOLD if (20 <= day <= 27) else DEFAULT_SHED_FLUSH_THRESHOLD
        is_pressure_valve_active = total_shed_count >= flush_threshold

        if is_pressure_valve_active:
            # Flush Fertilizer & Wheat first
            avail_fert = max(0, int(shed.get("FERTILIZER", 0) or 0) - already_selling.get("FERTILIZER", 0))
            if avail_fert > 0 and len(dispatched_orders) < MAX_MARKET_ORDERS:
                flush_qty = min(avail_fert, 15)
                dispatched_orders.append(["SELL", "FERTILIZER", flush_qty])
                already_selling["FERTILIZER"] = already_selling.get("FERTILIZER", 0) + flush_qty

            avail_wheat = max(0, int(shed.get("WHEAT", 0) or 0) - already_selling.get("WHEAT", 0) - wheat_feed_reserve)
            if avail_wheat > 0 and len(dispatched_orders) < MAX_MARKET_ORDERS:
                flush_qty = min(avail_wheat, 15)
                dispatched_orders.append(["SELL", "WHEAT", flush_qty])
                already_selling["WHEAT"] = already_selling.get("WHEAT", 0) + flush_qty

            # Flush non-feed items (Wool, Milk, Strawberry) if shed is still crowded
            for prod in ("WOOL", "MILK", "STRAWBERRY"):
                if len(dispatched_orders) >= MAX_MARKET_ORDERS:
                    break
                avail_prod = max(0, int(shed.get(prod, 0) or 0) - already_selling.get(prod, 0))
                if avail_prod > 0:
                    flush_qty = min(avail_prod, 10)
                    dispatched_orders.append(["SELL", prod, flush_qty])
                    already_selling[prod] = already_selling.get(prod, 0) + flush_qty

        # 3. Dynamic Scaled Trickle-Selling & Melon AMM Protection
        dynamic_batch_size = max(1, min(8, int(total_shed_count // 8)))

        # Prioritize selling Melons if held in shed
        melon_held = int(shed.get("MELON", 0) or 0)
        melon_avail = max(0, melon_held - already_selling.get("MELON", 0))
        if melon_avail > 0 and len(dispatched_orders) < MAX_MARKET_ORDERS:
            melon_price = market_prices.get("MELON", 250)
            melon_inv = market_inv.get("MELON", 10000)
            # Quadratic AMM guard: sell if price >= 120 or if pressure valve is active
            if melon_price >= 120 or melon_inv < 10020 or is_pressure_valve_active:
                melon_sell_qty = min(melon_avail, 10)
                dispatched_orders.append(["SELL", "MELON", melon_sell_qty])
                already_selling["MELON"] = already_selling.get("MELON", 0) + melon_sell_qty

        for item in ALL_PRODUCTS:
            if len(dispatched_orders) >= MAX_MARKET_ORDERS:
                break

            queued_qty = self.pending_sell_queue.get(item, 0)
            avail_in_shed = max(0, int(shed.get(item, 0) or 0) - already_selling.get(item, 0))
            if item == "WHEAT":
                avail_in_shed = max(0, avail_in_shed - wheat_feed_reserve)

            if queued_qty <= 0 or avail_in_shed <= 0:
                continue

            base_price = MARKET_PARAMS[item]["base"]
            cur_price = market_prices.get(item, calculate_single_unit_price(item, market_inv.get(item, 10000)))

            if not is_pressure_valve_active and cur_price < base_price * PRICE_FLOOR_PAUSE_RATIO:
                continue

            sell_qty = min(queued_qty, avail_in_shed, dynamic_batch_size)
            if sell_qty <= 0:
                continue

            dispatched_orders.append(["SELL", item, sell_qty])
            already_selling[item] = already_selling.get(item, 0) + sell_qty
            self.pending_sell_queue[item] -= sell_qty

        return dispatched_orders[:MAX_MARKET_ORDERS]
