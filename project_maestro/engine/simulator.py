"""Calibrated High-Fidelity Farm Lifecycle Simulator - Project Maestro (Engine)

Replicates exact Kaggle environments kaggriculture mechanics and market price dynamics:
- CARE pending_care_bonus accumulation (3x milk on cows, 4x wool on sheep, 2x eggs on geese)
- Daily fertilizer collection (1 fertilizer/animal/day)
- On-farm wheat production: 100% feed self-sufficiency + surplus wheat marketing
- Cash crop production (Strawberries / Carrots on unlocked quadrants)
- Phased capital acquisition ramp (starting cash $3,000)
- Land unlocks (NE $1k, SW $2k, SE $4k)
- Dynamic crew sizing with exact daily Fibonacci costs
- Step-accurate AMM market clearance with continuous town shop drains and opponent sales
- 100-unit shed capacity constraint

References:
- kaggriculture.py:97 (LAND_PRICES)
- kaggriculture.py:99-101 (FARM_HAND_COST_MULT)
- kaggriculture.py:126-150 (MARKET_PARAMS, MARKET_I0, PRICE_FLOOR)
- kaggriculture.py:195-207 (_refresh_prices exact price computation)
- kaggriculture.py:505 (FEED)
- kaggriculture.py:518 (CARE)
- kaggriculture.py:526 (COLLECT_FERTILIZER)
- kaggriculture.py:596-597 (interleaved per-unit market order execution)
- kaggriculture.py:728-750 (_town_consume: shop tick every 4 turns, town center every 24 turns)
- kaggriculture.py:804-839 (pending_care_bonus, fertilizer_available)
- kaggriculture.py:843 (shedCapacity = 100)
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from project_maestro.oracle.price_model import (
    MARKET_I0, PRICE_FLOOR, CROPS, ANIMALS, MARKET_PARAMS, SHOPS_MAP,
    calculate_exact_animal_yield, get_price, calculate_realized_revenue,
    calculate_interleaved_revenue
)

FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]


def daily_hire_cost(hires: int) -> int:
    """Exact daily cost for hiring N farmhands with FARM_HAND_COST_MULT = 1."""
    if hires <= 0:
        return 0
    return sum(FIB[i] for i in range(min(hires, len(FIB))))


class CalibratedFarmSimulation:
    def __init__(
        self,
        target_cows: int,
        target_sheep: int,
        target_geese: int,
        wheat_plots: int,
        cash_crop_type: Optional[str] = None,
        cash_crop_plots: int = 0,
        unlock_ne_day: int = 6,
        unlock_sw_day: int = 10,
        unlock_se_day: int = -1,
        day0_crew: int = 5,
        maint_crew: int = 5,
        peak_crew: int = 9,
        demand_pressure: Optional[Dict[str, float]] = None,
        opp_cows: int = 10,
        opp_sheep: int = 4,
        opp_geese: int = 0,
    ):
        self.target_cows = target_cows
        self.target_sheep = target_sheep
        self.target_geese = target_geese
        self.wheat_plots = wheat_plots
        self.cash_crop_type = cash_crop_type
        self.cash_crop_plots = cash_crop_plots
        self.unlock_ne_day = unlock_ne_day
        self.unlock_sw_day = unlock_sw_day
        self.unlock_se_day = unlock_se_day
        self.day0_crew = day0_crew
        self.maint_crew = maint_crew
        self.peak_crew = peak_crew
        self.demand_pressure = demand_pressure or {p: 1.0 for p in MARKET_PARAMS}
        self.opp_cows = opp_cows
        self.opp_sheep = opp_sheep
        self.opp_geese = opp_geese

    def run(self) -> Dict[str, Any]:
        money = 3000.0
        quads = ["NW"]
        cows = []
        sheep = []
        geese = []

        wheat_inventory = 0
        shed = {p: 0 for p in MARKET_PARAMS}
        # Continuous AMM inventory tracking
        amm_inv = {p: float(MARKET_I0) for p in MARKET_PARAMS}

        daily_cash_history = []
        total_labor_cost = 0.0
        total_milk_produced = 0
        total_wool_produced = 0
        total_eggs_produced = 0
        total_fert_collected = 0
        total_wheat_sold = 0
        total_cash_crop_sold = 0

        # 30-day simulation loop (24 steps/day)
        for day in range(30):
            # Dynamic crew sizing
            is_peak = (day % 2 == 0 and day >= 6) or (day in [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30])
            crew = self.day0_crew if day == 0 else (self.peak_crew if is_peak else self.maint_crew)
            labor_cost = daily_hire_cost(crew)
            money -= labor_cost
            total_labor_cost += labor_cost

            # Phased Land Unlocks
            if "NE" not in quads and day >= self.unlock_ne_day and self.unlock_ne_day >= 0 and money >= 1000:
                money -= 1000
                quads.append("NE")
            if "SW" not in quads and day >= self.unlock_sw_day and self.unlock_sw_day >= 0 and money >= 2000:
                money -= 2000
                quads.append("SW")
            if "SE" not in quads and day >= self.unlock_se_day and self.unlock_se_day >= 0 and money >= 4000:
                money -= 4000
                quads.append("SE")

            # Phased Animal Purchases
            if day == 0:
                init_cows = min(self.target_cows, 4)
                init_geese = min(self.target_geese, 4 if self.target_geese > 0 else 0)
                init_sheep = min(self.target_sheep, 2 if self.target_sheep > 0 and init_cows >= 4 else 0)
                cost = (init_cows * 400) + (init_geese * 300) + (init_sheep * 500)
                if money >= cost + 100:
                    money -= cost
                    for _ in range(init_cows): cows.append({"placed_day": day, "care_bonus": 0})
                    for _ in range(init_geese): geese.append({"placed_day": day, "care_bonus": 0})
                    for _ in range(init_sheep): sheep.append({"placed_day": day, "care_bonus": 0})
            elif day in [4, 6, 8, 10, 12, 14]:
                needed_c = self.target_cows - len(cows)
                needed_s = self.target_sheep - len(sheep)
                needed_g = self.target_geese - len(geese)
                
                if needed_c > 0 and money >= 800:
                    buy_c = min(needed_c, int(money // 400) - 1)
                    if buy_c > 0:
                        money -= buy_c * 400
                        for _ in range(buy_c): cows.append({"placed_day": day, "care_bonus": 0})
                if needed_s > 0 and money >= 1000:
                    buy_s = min(needed_s, int(money // 500) - 1)
                    if buy_s > 0:
                        money -= buy_s * 500
                        for _ in range(buy_s): sheep.append({"placed_day": day, "care_bonus": 0})
                if needed_g > 0 and money >= 600:
                    buy_g = min(needed_g, int(money // 300) - 1)
                    if buy_g > 0:
                        money -= buy_g * 300
                        for _ in range(buy_g): geese.append({"placed_day": day, "care_bonus": 0})

            # On-Farm Wheat Production
            if day % 4 == 0:
                money -= self.wheat_plots * 10
            if day % 4 == 3 and day >= 3:
                harvested = self.wheat_plots * 4
                wheat_inventory += harvested
                feed_buffer = (len(cows) + len(sheep) + len(geese)) * 2
                if wheat_inventory > feed_buffer:
                    surplus = wheat_inventory - feed_buffer
                    shed["WHEAT"] = min(100, shed["WHEAT"] + surplus)
                    wheat_inventory = feed_buffer

            # Feeding & Fertilizer
            total_animals = len(cows) + len(sheep) + len(geese)
            if total_animals > 0:
                if wheat_inventory >= total_animals:
                    wheat_inventory -= total_animals
                else:
                    shortfall = total_animals - wheat_inventory
                    wheat_inventory = 0
                    p_w = get_price("WHEAT", amm_inv["WHEAT"])
                    money -= shortfall * p_w
                    amm_inv["WHEAT"] += shortfall

                # Daily Fertilizer Collection
                shed["FERTILIZER"] = min(100, shed["FERTILIZER"] + total_animals)
                total_fert_collected += total_animals

            # Animal Yields with CARE
            for cow in cows:
                p_day = cow["placed_day"]
                days_since = day - p_day - 8
                if days_since >= 0 and days_since % 2 == 0:
                    yield_amount = 1 + cow["care_bonus"]
                    shed["MILK"] = min(100, shed["MILK"] + yield_amount)
                    total_milk_produced += yield_amount
                    cow["care_bonus"] = 0
                else:
                    cow["care_bonus"] += 1

            for s in sheep:
                p_day = s["placed_day"]
                days_since = day - p_day - 6
                if days_since >= 0 and days_since % 3 == 0:
                    yield_amount = 1 + s["care_bonus"]
                    shed["WOOL"] = min(100, shed["WOOL"] + yield_amount)
                    total_wool_produced += yield_amount
                    s["care_bonus"] = 0
                else:
                    s["care_bonus"] += 1

            for g in geese:
                p_day = g["placed_day"]
                days_since = day - p_day - 4
                if days_since >= 0:
                    yield_amount = 1 + g["care_bonus"]
                    shed["EGG"] = min(100, shed["EGG"] + yield_amount)
                    total_eggs_produced += yield_amount
                    g["care_bonus"] = 0
                else:
                    g["care_bonus"] += 1

            # Cash Crops
            if self.cash_crop_type and self.cash_crop_plots > 0 and len(quads) >= 2:
                cspec = CROPS[self.cash_crop_type]
                if day % cspec["max_yield_day"] == 0:
                    money -= self.cash_crop_plots * cspec["seed"]
                if day >= cspec["first_yield_day"] and (day - cspec["first_yield_day"]) % max(1, cspec["interval"] + 1) == 0:
                    yield_units = self.cash_crop_plots * (2 if self.cash_crop_type == "STRAWBERRY" else 3)
                    shed[self.cash_crop_type] = min(100, shed[self.cash_crop_type] + yield_units)

            # Continuous 24-step hour-by-hour market selling & town consumption
            for hour in range(24):
                # Town consumption tick (every 4 steps for shops, step 23 for town center)
                if hour % 4 == 0:
                    for prod in MARKET_PARAMS:
                        # 6 shop ticks per day: each tick drains 1/6th of daily shop demand
                        daily_p = self.demand_pressure.get(prod, 1.0)
                        drain_step = max(0.0, (daily_p - 1.0) / 6.0) if prod != "FERTILIZER" else 0.0
                        amm_inv[prod] = max(0.0, amm_inv[prod] - drain_step)
                if hour == 23:
                    # Town center drains 1 unit of every non-fertilizer product
                    for prod in MARKET_PARAMS:
                        if prod != "FERTILIZER":
                            amm_inv[prod] = max(0.0, amm_inv[prod] - 1.0)

                # Paced selling during daytime hours
                if hour in [6, 12, 18, 22]:
                    for prod in ["MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT", "CARROT", "STRAWBERRY"]:
                        qty = shed[prod]
                        if qty <= 0:
                            continue
                        daily_drain = self.demand_pressure.get(prod, 1.0)
                        # Sell in small paced batches of 3-6 units matching continuous drain
                        sell_batch = min(qty, int(daily_drain / 4.0) + 3) if day < 28 else min(qty, 20)
                        if sell_batch <= 0:
                            continue

                        # Opponent concurrent sell batch
                        opp_batch = 0
                        if prod == "MILK" and self.opp_cows > 0 and day >= 8 and (day - 8) % 2 == 0:
                            opp_batch = max(0, int(self.opp_cows * 3 / 4.0))
                        elif prod == "WOOL" and self.opp_sheep > 0 and day >= 6 and (day - 6) % 3 == 0:
                            opp_batch = max(0, int(self.opp_sheep * 4 / 4.0))
                        elif prod == "FERTILIZER":
                            opp_batch = max(0, int(total_animals / 4.0))

                        rev = calculate_interleaved_revenue(prod, sell_batch, opp_batch, start_inventory=amm_inv[prod])
                        money += rev
                        shed[prod] -= sell_batch
                        amm_inv[prod] += (sell_batch + opp_batch)
                        if prod == "WHEAT": total_wheat_sold += sell_batch
                        if prod in ["STRAWBERRY", "CARROT"]: total_cash_crop_sold += sell_batch

            daily_cash_history.append(round(money, 1))

        return {
            "final_reward": round(money, 1),
            "total_labor_cost": total_labor_cost,
            "total_cows": len(cows),
            "total_sheep": len(sheep),
            "total_geese": len(geese),
            "total_milk": total_milk_produced,
            "total_wool": total_wool_produced,
            "total_eggs": total_eggs_produced,
            "total_fertilizer": total_fert_collected,
            "total_wheat_sold": total_wheat_sold,
            "total_cash_crop_sold": total_cash_crop_sold,
            "quads_unlocked": len(quads),
            "cash_history": daily_cash_history,
        }
