"""Gold-floor continuation with narrowly gated market feedback.

The farm backbone remains the validated v43 three-route shop policy.  Two
orthogonal ablations are available:

* ``aligned`` replays a route without weed recovery, while still matching the
  live hand count and optionally reordering existing SELL slots;
* clone preemption moves quantities from a real future SELL slot to the current
  turn after a persistent public-farm match, and removes the same quantity from
  its original slot.

No team name, submission id, lineage label, private opponent state, or future
opponent action is available to this runtime.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from scripts.v19_terminal import (
    align_hands,
    clone_distance,
    projected_shed,
    terminal_market,
)
from v23.planner import PlannerConfig, build_sparse_planner
from v23.policy_library import reorder_sell_slots
from v23.state_encoder import BASE_PRICE, get
from v24.market_maker import MarketMakerConfig, MarketMakerExpert


ROUTES = ("default", "yarn_first", "yarn_second", "yarn_third")
OPTIONAL_ROUTES = ("bakery_capital",)


@dataclass(frozen=True)
class GoldFloorConfig:
    yarn_first_start: int = 88
    yarn_second_start: int = 153
    yarn_third_start: int = 216
    yarn_third_enabled: bool = False
    yarn_third_pet_brunch_veto: bool = True
    # Empty means every visible non-YARN/non-YARN prefix is eligible.  A
    # non-empty tuple is a conservative allow-list learned outside runtime.
    yarn_third_prefixes: tuple[tuple[str, str], ...] = ()
    # An option-preserving continuation learned from a public route whose
    # complete action prefix equals the default through this decision point.
    # Selection uses only the visible first shop and public opponent assets.
    bakery_capital_enabled: bool = False
    bakery_capital_start: int = 120
    bakery_capital_second_shops: tuple[str, ...] = ()
    bakery_capital_minimum_cows: int = 3
    bakery_capital_minimum_sheep: int = 2
    bakery_capital_minimum_melons: int = 10
    bakery_capital_maximum_geese: int = 0
    controller: str = "sparse"
    aligned_reorder: bool = True
    clone_preempt_horizon: int = 0
    clone_detection_start: int = 48
    clone_active_start: int = 160
    clone_active_stop: int = 700
    clone_distance_threshold: float = 2.0
    clone_streak_required: int = 24
    clone_maximum_batch: int = 25
    # A latch says that the opening was close; it need not imply that the
    # routes are still close when a later SELL is moved.  This stricter guard
    # prevents stale opening matches from activating a false clone response.
    clone_requires_current_near: bool = False
    clone_veto_enabled: bool = False
    clone_veto_step: int = 120
    clone_veto_first_shop: str = "BAKERY"
    clone_veto_minimum_sheep: int = 4
    clone_veto_maximum_cows: int = 1
    clone_veto_minimum_wheat: int = 8
    clone_veto_minimum_melons: int = 7
    clone_veto_maximum_geese: int = 0
    # Optional closed-loop promotion from the ordinary clone horizon to a
    # one-step-longer horizon.  The detector uses only observed market
    # inventory flow and our own previous order.  It is disabled by default so
    # the frozen v44 behaviour remains unchanged.
    clone_phase_detector: bool = False
    clone_phase_horizon: int = 3
    clone_phase_maximum_batch: int = 20
    clone_phase_detection_start: int = 144
    clone_phase_detection_stop: int = 159
    clone_phase_minimum_excess_units: int = 1
    clone_phase_maximum_excess_units: int = 10**9
    clone_phase_future_window: int = 2
    clone_phase_items: tuple[str, ...] = (
        "STRAWBERRY",
        "MELON",
        "MILK",
        "WOOL",
    )
    maximum_market_orders: int = 10
    exposure_preempt: bool = False
    exposure_item: str = "FERTILIZER"
    exposure_active_start: int = 216
    exposure_active_stop: int = 680
    exposure_lookahead: int = 24
    exposure_minimum_opponent_animals: int = 8
    exposure_minimum_price_ratio: float = 0.80
    exposure_maximum_batch: int = 10
    wheat_market_maker: bool = False
    wheat_start_step: int = 260
    wheat_batch: int = 10
    wheat_cash_reserve: float = 2500.0
    wheat_minimum_profit: float = 25.0
    feed_days_reserve: float = 2.0
    investment_horizon: int = 2
    shed_headroom: int = 15
    terminal_rule: str = "none"


def _shops(obs: Any) -> list[str]:
    town = get(obs, "town", {}) or {}
    return [str(value) for value in (get(town, "unlocked_shops", []) or [])]


def selected_route(obs: Any, config: GoldFloorConfig) -> str:
    step = int(get(obs, "step", 0) or 0)
    shops = _shops(obs)
    allowed_third_prefixes = {
        (str(prefix[0]), str(prefix[1]))
        for prefix in config.yarn_third_prefixes
        if len(prefix) >= 2
    }
    if shops and shops[0] == "YARN_STORE" and step >= int(config.yarn_first_start):
        return "yarn_first"
    if (
        len(shops) >= 2
        and shops[0] != "YARN_STORE"
        and shops[1] == "YARN_STORE"
        and step >= int(config.yarn_second_start)
    ):
        return "yarn_second"
    if (
        config.yarn_third_enabled
        and len(shops) >= 3
        and shops[0] != "YARN_STORE"
        and shops[1] != "YARN_STORE"
        and shops[2] == "YARN_STORE"
        and (
            not allowed_third_prefixes
            or (shops[0], shops[1]) in allowed_third_prefixes
        )
        and not (
            config.yarn_third_pet_brunch_veto
            and shops[0] == "PET_CAFE"
            and shops[1] == "BRUNCH_SPOT"
        )
        and step >= int(config.yarn_third_start)
    ):
        return "yarn_third"
    return "default"


def _public_asset_counts(farm: dict) -> dict[str, int]:
    counts = {
        "COW": 0,
        "SHEEP": 0,
        "GOOSE": 0,
        "MELON": 0,
        "WHEAT": 0,
        "STRAWBERRY": 0,
    }
    for row in (get(farm, "tiles", []) or []):
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            for field in ("animal", "crop"):
                value = str(tile.get(field, "") or "")
                if value in counts:
                    counts[value] += 1
    return counts


def bakery_capital_candidate(obs: Any, config: GoldFloorConfig) -> bool:
    """Return whether the public state supports the capital continuation."""
    if not bool(config.bakery_capital_enabled):
        return False
    step = int(get(obs, "step", 0) or 0)
    shops = _shops(obs)
    # This is a single option-preserving decision point.  Re-evaluating the
    # same coarse signature later could jump into a suffix after its state has
    # already diverged from the default route.
    if step != int(config.bakery_capital_start) or not shops or shops[0] != "BAKERY":
        return False
    allowed_second = {str(value) for value in config.bakery_capital_second_shops}
    if allowed_second and (len(shops) < 2 or shops[1] not in allowed_second):
        return False
    seat = 1 if int(get(obs, "player", 0) or 0) == 1 else 0
    farms = list(get(obs, "farms", []) or [])
    opponent = farms[1 - seat] if len(farms) >= 2 else {}
    counts = _public_asset_counts(opponent)
    return (
        counts["COW"] >= int(config.bakery_capital_minimum_cows)
        and counts["SHEEP"] >= int(config.bakery_capital_minimum_sheep)
        and counts["MELON"] >= int(config.bakery_capital_minimum_melons)
        and counts["GOOSE"] <= int(config.bakery_capital_maximum_geese)
    )


def clone_veto_candidate(obs: Any, config: GoldFloorConfig) -> bool:
    """Identify one visible state where the opening latch is stale."""
    if not bool(config.clone_veto_enabled):
        return False
    step = int(get(obs, "step", 0) or 0)
    shops = _shops(obs)
    if (
        step != int(config.clone_veto_step)
        or not shops
        or shops[0] != str(config.clone_veto_first_shop)
    ):
        return False
    seat = 1 if int(get(obs, "player", 0) or 0) == 1 else 0
    farms = list(get(obs, "farms", []) or [])
    opponent = farms[1 - seat] if len(farms) >= 2 else {}
    counts = _public_asset_counts(opponent)
    return (
        counts["SHEEP"] >= int(config.clone_veto_minimum_sheep)
        and counts["COW"] <= int(config.clone_veto_maximum_cows)
        and counts["WHEAT"] >= int(config.clone_veto_minimum_wheat)
        and counts["MELON"] >= int(config.clone_veto_minimum_melons)
        and counts["GOOSE"] <= int(config.clone_veto_maximum_geese)
    )


def _aligned_policy(actions: list[dict], reorder: bool):
    route = copy.deepcopy(actions)

    def policy(obs: Any, configuration: Any = None) -> dict:
        step = min(max(0, int(get(obs, "step", 0) or 0)), len(route) - 1)
        result = align_hands(route[step], obs)
        return (
            reorder_sell_slots(obs, result, configuration, demand_alpha=0.25)
            if reorder
            else result
        )

    return policy


def _sell_totals(rows: list[list]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for order in rows:
        if len(order) < 3 or order[0] != "SELL":
            continue
        item = str(order[1])
        try:
            quantity = max(0, int(order[2]))
        except (TypeError, ValueError):
            continue
        totals[item] = totals.get(item, 0) + quantity
    return totals


def _market_inventory_net(rows: list[list]) -> dict[str, int]:
    """Signed market-inventory flow caused by our own visible order list."""
    totals: dict[str, int] = {}
    for order in rows:
        if len(order) < 3:
            continue
        operation = str(order[0])
        if operation not in {"SELL", "BUY_PRODUCT"}:
            continue
        item = str(order[1])
        try:
            quantity = max(0, int(order[2]))
        except (TypeError, ValueError):
            continue
        sign = 1 if operation == "SELL" else -1
        totals[item] = totals.get(item, 0) + sign * quantity
    return totals


def _animal_count(farm: dict) -> int:
    return sum(
        isinstance(tile, dict) and bool(tile.get("animal"))
        for row in (farm.get("tiles", []) or [])
        for tile in row
    )


def _future_allocations(
    actions: list[dict],
    *,
    step: int,
    lookahead: int,
    item: str,
    maximum: int,
    reserved: dict[int, dict[str, int]],
) -> list[tuple[int, int]]:
    remaining = max(0, int(maximum))
    allocations = []
    stop = min(len(actions) - 1, int(step) + max(1, int(lookahead)))
    for due_step in range(int(step) + 1, stop + 1):
        planned = _sell_totals(
            list((actions[due_step] or {}).get("market", []) or [])
        ).get(item, 0)
        planned = max(
            0,
            int(planned)
            - int((reserved.get(due_step, {}) or {}).get(item, 0) or 0),
        )
        quantity = min(remaining, planned)
        if quantity:
            allocations.append((due_step, quantity))
            remaining -= quantity
        if remaining <= 0:
            break
    return allocations


class CloneSellPreemption:
    """Move only scheduled inventory across time, with exact quantity debt."""

    def __init__(self, routes: dict[str, list[dict]], config: GoldFloorConfig):
        self.routes = copy.deepcopy(routes)
        self.config = config
        self.states = {0: {}, 1: {}}
        self.telemetry = {
            "games": 0,
            "near_turns": 0,
            "latches": 0,
            "phase_evidence_turns": 0,
            "phase_evidence_units": 0,
            "phase_escalations": 0,
            "preempt_turns": 0,
            "preempt_units": 0,
            "repaid_units": 0,
            "exposure_turns": 0,
            "exposure_units": 0,
        }

    def _reset(self, seat: int, step: int) -> dict:
        state = {
            "last_step": step,
            "near_streak": 0,
            "latched": False,
            "route": "default",
            "due": {},
            "last_market_inventory": {},
            "last_emitted_market": [],
            "phase_escalated": False,
            "phase_evidence_units": 0,
            "phase_evidence_items": [],
            "clone_veto": False,
        }
        self.states[seat] = state
        self.telemetry["games"] += 1
        return state

    def _phase_evidence(
        self,
        obs: Any,
        state: dict,
        step: int,
    ) -> tuple[int, list[str]]:
        config = self.config
        if not (
            bool(config.clone_phase_detector)
            and not bool(state.get("phase_escalated", False))
            and bool(state.get("latched", False))
            and int(config.clone_phase_detection_start)
            <= step
            <= int(config.clone_phase_detection_stop)
            and clone_distance(obs) <= float(config.clone_distance_threshold)
        ):
            return 0, []
        previous = dict(state.get("last_market_inventory", {}) or {})
        if not previous or step <= 0:
            return 0, []
        market = get(obs, "market", {}) or {}
        current = dict(get(market, "inventory", {}) or {})
        own_net = _market_inventory_net(
            list(state.get("last_emitted_market", []) or [])
        )
        route_name = str(state.get("route", "default"))
        route = self.routes.get(route_name, self.routes["default"])
        normal = _sell_totals(
            list((route[step - 1] or {}).get("market", []) or [])
        )
        stop = min(
            len(route),
            step + max(1, int(config.clone_phase_future_window)) + 1,
        )
        upcoming: dict[str, int] = {}
        for due_step in range(step, stop):
            for item, quantity in _sell_totals(
                list((route[due_step] or {}).get("market", []) or [])
            ).items():
                upcoming[item] = upcoming.get(item, 0) + quantity

        minimum = max(1, int(config.clone_phase_minimum_excess_units))
        maximum = max(minimum, int(config.clone_phase_maximum_excess_units))
        evidence_units = 0
        evidence_items = []
        for item in tuple(str(value) for value in config.clone_phase_items):
            if int(upcoming.get(item, 0) or 0) <= 0:
                continue
            delta = int(current.get(item, 0) or 0) - int(previous.get(item, 0) or 0)
            # Town/shop demand and an opponent BUY can only reduce this value.
            # A positive remainder is therefore conservative evidence that a
            # near-clone supplied more than its ordinary previous-turn slot.
            excess = (
                delta
                - int(own_net.get(item, 0) or 0)
                - int(normal.get(item, 0) or 0)
            )
            if minimum <= excess <= maximum:
                evidence_units += excess
                evidence_items.append(item)
        return evidence_units, evidence_items

    @staticmethod
    def _remember(obs: Any, state: dict, result: dict) -> dict:
        market = get(obs, "market", {}) or {}
        state["last_market_inventory"] = dict(
            get(market, "inventory", {}) or {}
        )
        state["last_emitted_market"] = [
            list(order) for order in (result.get("market", []) or [])
        ]
        return result

    def apply(
        self,
        obs: Any,
        action: Any,
        route_name: str,
        configuration: Any = None,
    ) -> dict:
        result = align_hands(action, obs)
        seat = 1 if int(get(obs, "player", 0) or 0) == 1 else 0
        step = int(get(obs, "step", 0) or 0)
        state = self.states[seat]
        if step == 0 or step < int(state.get("last_step", -1)):
            state = self._reset(seat, step)
        state["last_step"] = step

        if clone_veto_candidate(obs, self.config):
            state["clone_veto"] = True

        distance = clone_distance(obs)
        if distance <= float(self.config.clone_distance_threshold):
            state["near_streak"] = int(state.get("near_streak", 0)) + 1
            self.telemetry["near_turns"] += 1
        else:
            state["near_streak"] = 0
        if (
            not bool(state.get("latched", False))
            and step >= int(self.config.clone_detection_start)
            and int(state.get("near_streak", 0))
            >= max(1, int(self.config.clone_streak_required))
        ):
            state["latched"] = True
            self.telemetry["latches"] += 1

        evidence_units, evidence_items = self._phase_evidence(obs, state, step)
        if evidence_units > 0:
            state["phase_escalated"] = True
            state["phase_evidence_units"] = evidence_units
            state["phase_evidence_items"] = evidence_items
            self.telemetry["phase_evidence_turns"] += 1
            self.telemetry["phase_evidence_units"] += evidence_units
            self.telemetry["phase_escalations"] += 1

        # No position can be opened before route selection has stabilized.
        # Still track the selected name so a configuration error cannot carry
        # debt between unrelated schedules.
        previous_route = str(state.get("route", "default"))
        if route_name != previous_route:
            if state.get("due"):
                state["due"] = {}
            state["route"] = route_name

        market = [list(order) for order in (result.get("market", []) or [])]
        due_now = dict(state.setdefault("due", {}).pop(step, {}) or {})
        adjusted = []
        repaid = 0
        for order in market:
            if len(order) >= 3 and order[0] == "SELL":
                item = str(order[1])
                debt = max(0, int(due_now.get(item, 0) or 0))
                if debt:
                    quantity = max(0, int(order[2] or 0))
                    reduction = min(quantity, debt)
                    quantity -= reduction
                    due_now[item] = debt - reduction
                    repaid += reduction
                    if quantity <= 0:
                        continue
                    order[2] = quantity
            adjusted.append(order)
        # A failed/short route SELL carries its debt to the next turn rather
        # than silently granting additional lifetime production.
        for item, quantity in due_now.items():
            if quantity > 0 and step < 718:
                row = state.setdefault("due", {}).setdefault(step + 1, {})
                row[item] = int(row.get(item, 0) or 0) + int(quantity)
        self.telemetry["repaid_units"] += repaid
        result["market"] = adjusted

        horizon = max(
            0,
            int(
                self.config.clone_phase_horizon
                if state.get("phase_escalated", False)
                else self.config.clone_preempt_horizon
            ),
        )
        maximum_batch = max(
            0,
            int(
                self.config.clone_phase_maximum_batch
                if state.get("phase_escalated", False)
                else self.config.clone_maximum_batch
            ),
        )
        clone_eligible = (
            horizon > 0
            and bool(state.get("latched", False))
            and not bool(state.get("clone_veto", False))
            and (
                not bool(self.config.clone_requires_current_near)
                or distance <= float(self.config.clone_distance_threshold)
            )
            and int(self.config.clone_active_start) <= step < int(self.config.clone_active_stop)
            and step + horizon < len(self.routes[route_name])
            and len(adjusted) < int(self.config.maximum_market_orders)
        )
        if clone_eligible:
            future_market = list(
                (self.routes[route_name][step + horizon] or {}).get("market", []) or []
            )
            future = _sell_totals(future_market)
            existing = _sell_totals(adjusted)
            available = projected_shed(obs, result)
            for item, quantity in existing.items():
                available[item] = max(
                    0, int(available.get(item, 0) or 0) - quantity
                )

            candidates = []
            prices = dict(get(get(obs, "market", {}) or {}, "prices", {}) or {})
            for item, planned in future.items():
                quantity = min(
                    max(0, int(planned) - int(existing.get(item, 0) or 0)),
                    max(0, int(available.get(item, 0) or 0)),
                    maximum_batch,
                )
                if quantity > 0:
                    candidates.append(
                        (float(prices.get(item, 0) or 0) * quantity, item, quantity)
                    )
            candidates.sort(reverse=True)
            remaining = maximum_batch
            shifted = 0
            due_step = step + horizon
            for _value, item, requested in candidates:
                if (
                    len(result["market"])
                    >= int(self.config.maximum_market_orders)
                    or remaining <= 0
                ):
                    break
                quantity = min(requested, remaining)
                if quantity <= 0:
                    continue
                result["market"].append(["SELL", item, quantity])
                row = state.setdefault("due", {}).setdefault(due_step, {})
                row[item] = int(row.get(item, 0) or 0) + quantity
                remaining -= quantity
                shifted += quantity
            if shifted:
                self.telemetry["preempt_turns"] += 1
                self.telemetry["preempt_units"] += shifted
                return self._remember(
                    obs,
                    state,
                    reorder_sell_slots(
                        obs, result, configuration, demand_alpha=0.25
                    ),
                )

        # A second, independent gate targets visible fertilizer gluts.  It is
        # disabled for near-clones because the tighter two-turn forecast above
        # already owns their timing debt.
        item = str(self.config.exposure_item)
        farms = list(get(obs, "farms", []) or [])
        opponent = farms[1 - seat] if len(farms) >= 2 else {}
        prices = dict(get(get(obs, "market", {}) or {}, "prices", {}) or {})
        base_price = float(BASE_PRICE.get(item, 1) or 1)
        price_ratio = float(prices.get(item, 0) or 0) / max(1.0, base_price)
        if not (
            bool(self.config.exposure_preempt)
            and not bool(state.get("latched", False))
            and int(self.config.exposure_active_start)
            <= step
            < int(self.config.exposure_active_stop)
            and _animal_count(opponent)
            >= int(self.config.exposure_minimum_opponent_animals)
            and price_ratio >= float(self.config.exposure_minimum_price_ratio)
            and len(result["market"]) < int(self.config.maximum_market_orders)
        ):
            return self._remember(obs, state, result)

        allocations = _future_allocations(
            self.routes[route_name],
            step=step,
            lookahead=int(self.config.exposure_lookahead),
            item=item,
            maximum=int(self.config.exposure_maximum_batch),
            reserved=state.setdefault("due", {}),
        )
        planned = sum(quantity for _due_step, quantity in allocations)
        if planned <= 0:
            return self._remember(obs, state, result)
        available = projected_shed(obs, result)
        already = _sell_totals(result["market"]).get(item, 0)
        quantity = min(
            planned,
            max(0, int(available.get(item, 0) or 0) - int(already)),
            max(0, int(self.config.exposure_maximum_batch)),
        )
        if quantity <= 0:
            return self._remember(obs, state, result)
        result["market"].append(["SELL", item, quantity])
        left = quantity
        for due_step, capacity in allocations:
            allocated = min(left, capacity)
            if allocated:
                row = state.setdefault("due", {}).setdefault(due_step, {})
                row[item] = int(row.get(item, 0) or 0) + allocated
                left -= allocated
            if left <= 0:
                break
        self.telemetry["exposure_turns"] += 1
        self.telemetry["exposure_units"] += quantity
        return self._remember(
            obs,
            state,
            reorder_sell_slots(obs, result, configuration, demand_alpha=0.25),
        )


def build_gold_floor_router(
    routes: dict[str, list[dict]],
    config: GoldFloorConfig = GoldFloorConfig(),
):
    expected = set(ROUTES)
    if config.bakery_capital_enabled:
        expected.add("bakery_capital")
    if set(routes) != expected:
        raise ValueError(f"expected routes {sorted(expected)}, received {sorted(routes)}")
    if any(len(routes[name]) != 719 for name in expected):
        raise ValueError("every route must contain exactly 719 actions")
    if config.controller not in {"sparse", "aligned"}:
        raise ValueError(f"unknown controller: {config.controller}")
    if config.terminal_rule not in {"none", "collision", "value", "existing"}:
        raise ValueError(f"unknown terminal rule: {config.terminal_rule}")

    if config.controller == "sparse":
        children = {
            name: build_sparse_planner(routes[name], PlannerConfig())
            for name in expected
        }
    else:
        children = {
            name: _aligned_policy(routes[name], bool(config.aligned_reorder))
            for name in expected
        }

    preemption = CloneSellPreemption(routes, config)
    makers = {
        name: MarketMakerExpert(
            routes[name],
            MarketMakerConfig(
                enabled=bool(config.wheat_market_maker),
                item="WHEAT",
                feed_item="WHEAT",
                start_step=int(config.wheat_start_step),
                stop_entry_step=716,
                max_batch=max(0, int(config.wheat_batch)),
                minimum_expected_profit=float(config.wheat_minimum_profit),
                mirror_minimum_expected_profit=float(config.wheat_minimum_profit),
                minimum_cash_reserve=float(config.wheat_cash_reserve),
                feed_days_reserve=float(config.feed_days_reserve),
                investment_horizon=int(config.investment_horizon),
                shed_headroom=int(config.shed_headroom),
            ),
        )
        for name in expected
    }
    telemetry = {
        "calls": 0,
        "selected": {name: 0 for name in expected},
        "market_maker_changed_turns": 0,
    }
    bakery_capital_latched = {0: False, 1: False}
    last_step = {0: -1, 1: -1}

    def agent(obs: Any, configuration: Any = None) -> dict:
        step = int(get(obs, "step", 0) or 0)
        seat = 1 if int(get(obs, "player", 0) or 0) == 1 else 0
        if step == 0 or step < last_step[seat]:
            bakery_capital_latched[seat] = False
        last_step[seat] = step
        actions = {
            name: policy(obs, configuration)
            for name, policy in children.items()
        }
        route_name = selected_route(obs, config)
        if bakery_capital_candidate(obs, config):
            bakery_capital_latched[seat] = True
        # YARN branches have their own validated continuation and retain
        # priority if a later public shop reveals one of those regimes.
        if route_name == "default" and bakery_capital_latched[seat]:
            route_name = "bakery_capital"
        result = preemption.apply(
            obs, actions[route_name], route_name, configuration
        )

        # Initialize every maker at game start, when none is allowed to enter.
        # Thereafter only the permanently selected route owns a position.
        if step == 0:
            for maker in makers.values():
                maker.apply(obs, result, configuration)
        elif config.wheat_market_maker:
            before = copy.deepcopy(result.get("market", []) or [])
            result = makers[route_name].apply(obs, result, configuration)
            telemetry["market_maker_changed_turns"] += (
                before != list(result.get("market", []) or [])
            )
        if step == 718 and config.terminal_rule != "none":
            result = terminal_market(
                obs,
                result,
                rule=str(config.terminal_rule),
                replace=True,
            )

        telemetry["calls"] += 1
        telemetry["selected"][route_name] += 1
        return result

    agent.children = children
    agent.preemption = preemption
    agent.market_makers = makers
    agent.telemetry = telemetry
    agent.gold_floor_config = config
    return agent
