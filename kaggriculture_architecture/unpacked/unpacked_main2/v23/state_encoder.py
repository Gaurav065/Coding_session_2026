"""Observation -> compact strategic state for sparse closed-loop decisions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
BASE_PRICE = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}
SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
ANIMAL_PRODUCT = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}


def get(value: Any, key: str, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def regime_from_configuration(configuration: Any) -> str:
    interval = int(get(configuration, "townCenterSellInterval", 12) or 12)
    return "rebalance" if interval >= 24 else "legacy"


def _asset_features(farm: dict) -> dict[str, float]:
    counts = Counter()
    exposure = Counter()
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            counts[f"kind_{kind}"] += 1
            crop = tile.get("crop")
            animal = tile.get("animal")
            if crop:
                counts[f"crop_{crop}"] += 1
                exposure[crop] += max(1, int(tile.get("yield_units", 0) or 0))
            if animal:
                counts[f"animal_{animal}"] += 1
                product = ANIMAL_PRODUCT.get(animal)
                if product:
                    exposure[product] += max(1, int(tile.get("yield_units", 0) or 0))
            if tile.get("fertilizer_available"):
                exposure["FERTILIZER"] += 1
    return {
        **{name: float(value) for name, value in counts.items()},
        **{f"exposure_{name}": float(value) for name, value in exposure.items()},
        "hands": float(len(farm.get("hands", []) or [])),
        "quadrants": float(len(farm.get("unlocked_quadrants", []) or [])),
        "money": float(farm.get("money", 0) or 0),
    }


def shop_demand_per_day(
    unlocked_shops: list[str],
    *,
    day: int,
    regime: str,
    turns_per_day: int = 24,
    shop_interval: int = 4,
    center_interval: int | None = None,
) -> dict[str, float]:
    """Current per-day demand, counting duplicate shop instances."""
    demand = {product: 0.0 for product in PRODUCTS}
    ticks = turns_per_day / max(1, shop_interval)
    for shop in unlocked_shops:
        products = SHOP_PRODUCTS.get(shop, ())
        multiplier = 2 if len(products) == 1 else 1
        for product in products:
            demand[product] += ticks * multiplier
    if center_interval is None:
        center_interval = 24 if regime == "rebalance" else 12
    center_ticks = turns_per_day / max(1, center_interval)
    center_multiplier = 1 if regime == "rebalance" else (4 if day >= 20 else 2 if day >= 10 else 1)
    for product in PRODUCTS:
        if product != "FERTILIZER":
            demand[product] += center_ticks * center_multiplier
    return demand


@dataclass(frozen=True)
class StrategicState:
    step: int
    day: int
    remaining_turns: int
    player: int
    regime: str
    shops: tuple[str, ...]
    shop_counts: dict[str, int]
    demand_per_day: dict[str, float]
    market_inventory: dict[str, float]
    market_prices: dict[str, float]
    own: dict[str, float]
    opponent: dict[str, float]
    shed: dict[str, float]
    seeds: dict[str, float]

    def flat_features(self) -> dict[str, float]:
        out = {
            "step": float(self.step),
            "day": float(self.day),
            "remaining_turns": float(self.remaining_turns),
            "is_rebalance": float(self.regime == "rebalance"),
            "duplicate_shops": float(len(self.shops) - len(set(self.shops))),
        }
        for shop in SHOP_PRODUCTS:
            out[f"shop_{shop}"] = float(self.shop_counts.get(shop, 0))
        for product in PRODUCTS:
            out[f"demand_{product}"] = float(self.demand_per_day.get(product, 0))
            out[f"inventory_{product}"] = float(self.market_inventory.get(product, 0))
            price = float(self.market_prices.get(product, BASE_PRICE[product]))
            out[f"price_{product}"] = price
            out[f"price_ratio_{product}"] = price / BASE_PRICE[product]
            out[f"shed_{product}"] = float(self.shed.get(product, 0))
            out[f"own_exposure_{product}"] = float(self.own.get(f"exposure_{product}", 0))
            out[f"opp_exposure_{product}"] = float(self.opponent.get(f"exposure_{product}", 0))
        for prefix, values in (("own", self.own), ("opp", self.opponent)):
            for name in ("money", "hands", "quadrants", "kind_WEED"):
                out[f"{prefix}_{name}"] = float(values.get(name, 0))
        return out


def encode_state(obs: Any, configuration: Any = None) -> StrategicState:
    player = int(get(obs, "player", 0) or 0)
    farms = list(get(obs, "farms", []) or [])
    mine = farms[player] if player < len(farms) else {}
    opponent_index = 1 - player if len(farms) == 2 else player
    opponent = farms[opponent_index] if opponent_index < len(farms) else {}
    market = get(obs, "market", {}) or {}
    town = get(obs, "town", {}) or {}
    private = get(obs, "private", {}) or {}
    step = int(get(obs, "step", 0) or 0)
    day = int(get(obs, "day", step // 24) or 0)
    regime = regime_from_configuration(configuration)
    shops = tuple(get(town, "unlocked_shops", []) or [])
    shop_interval = int(get(configuration, "townShopSellInterval", 4) or 4)
    turns_per_day = int(get(configuration, "turnsPerDay", 24) or 24)
    center_interval = int(
        get(configuration, "townCenterSellInterval", 24 if regime == "rebalance" else 12)
        or (24 if regime == "rebalance" else 12)
    )
    return StrategicState(
        step=step,
        day=day,
        remaining_turns=max(0, 719 - step),
        player=player,
        regime=regime,
        shops=shops,
        shop_counts=dict(Counter(shops)),
        demand_per_day=shop_demand_per_day(
            list(shops),
            day=day,
            regime=regime,
            turns_per_day=turns_per_day,
            shop_interval=shop_interval,
            center_interval=center_interval,
        ),
        market_inventory={
            product: float(value)
            for product, value in (get(market, "inventory", {}) or {}).items()
        },
        market_prices={
            product: float(value)
            for product, value in (get(market, "prices", {}) or {}).items()
        },
        own=_asset_features(mine),
        opponent=_asset_features(opponent),
        shed={
            product: float(value)
            for product, value in (get(private, "shed", {}) or {}).items()
        },
        seeds={
            product: float(value)
            for product, value in (get(private, "seeds", {}) or {}).items()
        },
    )
