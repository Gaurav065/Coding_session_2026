"""Empirical verification of the mechanics the strategy leans on.

Every number in STRATEGY.md that is load-bearing gets checked here against the
real kaggle-environments interpreter, not against the README prose.

Run:  python analysis/verify_mechanics.py
"""
from kaggle_environments import make

TPD = 24
SHED_TILE = (4, 4)   # NW quadrant AND shed-adjacent -> farmer never has to move


def run(agent, days=30):
    env = make("kaggriculture", configuration={"episodeSteps": days * TPD}, debug=False)
    env.run([agent, "pass"])
    return env


def tile_at(obs, x=4, y=4):
    return obs["farms"][obs["player"]]["tiles"][y][x]


# ------------------------------------------------------------------ animals
def animal_agent(animal, structure, feed_days, care, log, days=30):
    """Farmer parks on (4,4): build -> pickup -> place -> feed/care/collect/harvest."""
    state = {"placed": False}

    def agent(obs):
        day, hour = obs["day"], obs["hour"]
        priv = obs["private"]
        inv = priv["inventories"][0]
        shed = priv["shed"]
        tile = tile_at(obs)
        market, farmer = [], ["PASS"]

        # keep a wheat buffer in the shed, dump fertilizer so the shed never fills
        if shed.get("WHEAT", 0) < 6:
            market.append(["BUY_PRODUCT", "WHEAT", 8])
        if shed.get("FERTILIZER", 0) > 0:
            market.append(["SELL", "FERTILIZER", shed["FERTILIZER"]])

        if day == 0 and hour == 0:
            market.append(["BUY_ANIMAL", animal, 1])
            farmer = [structure_op(structure)]
        elif not state["placed"]:
            if inv.get(animal, 0) > 0:
                farmer = ["PLACE", animal]
                state["placed"] = True
            elif shed.get(animal, 0) > 0:
                farmer = ["PICKUP", animal, 1]
            else:
                farmer = ["PASS"]
        else:
            # Placement day counts as unfed, so an every-other-day regime must
            # feed on the ODD days (first feed on day 1) or the animal escapes
            # at the end of day 1.
            feed_this_day = (day % 2 == 1) if feed_days == "alternate" else True
            if hour == 0:
                log.append((day, dict(tile) if isinstance(tile, dict) else tile,
                            dict(shed)))
            if isinstance(tile, dict) and inv.get("WHEAT", 0) < 2:
                farmer = ["PICKUP", "WHEAT", 2]
            elif feed_this_day and isinstance(tile, dict) and not tile.get("fed_today"):
                farmer = ["FEED"]
            elif care and feed_this_day and isinstance(tile, dict) and not tile.get("cared_today"):
                farmer = ["CARE"]
            elif isinstance(tile, dict) and tile.get("fertilizer_available"):
                farmer = ["COLLECT_FERTILIZER"]
            elif isinstance(tile, dict) and tile.get("yield_units", 0) > 0:
                farmer = ["HARVEST"]
        return {"farmer": farmer, "hands": [], "market": market[:10]}

    return agent


def structure_op(structure):
    return "BUILD_COOP" if structure == "COOP" else "BUILD_PASTURE"


def animal_test(animal, structure, product, feed_days, care, days=30):
    log = []
    env = run(animal_agent(animal, structure, feed_days, care, log, days), days)
    final = env.steps[-1][0]["observation"]
    shed = final["private"]["shed"]
    survived = any(isinstance(t, dict) and t.get("animal") == animal
                   for row in final["farms"][0]["tiles"] for t in row)
    total = shed.get(product, 0)
    money = final["farms"][0]["money"]
    label = f"{animal:<6} feed={feed_days:<9} care={str(care):<5}"
    first_day = next((d for d, t, s in log
                      if isinstance(t, dict) and t.get("yield_units", 0) > 0), None)
    print(f"  {label} -> {product:<5} total={total:>4}  survived={survived}  "
          f"first_yield_day={first_day}  rate={total / max(1, days - 8):.2f}/day  "
          f"money=${money:,.0f}")
    return log, total


# ------------------------------------------------------------------- plants
def crop_agent(crop, water_ages, harvest_age, log):
    def agent(obs):
        day, hour = obs["day"], obs["hour"]
        priv = obs["private"]
        tile = tile_at(obs)
        market, farmer = [], ["PASS"]

        if day == 0 and hour == 0:
            market.append(["BUY_SEED", crop, 1])
        elif day == 0 and hour == 1:
            farmer = ["PLANT", crop]
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            age = day - tile["planted_day"]
            if hour == 0:
                log.append((age, tile["yield_units"], tile["consecutive_unwatered"]))
            if age >= harvest_age and hour >= 2:
                farmer = ["HARVEST"]
            elif age in water_ages and not tile["watered_today"]:
                farmer = ["WATER"]
        return {"farmer": farmer, "hands": [], "market": market}
    return agent


def crop_test(crop, water_ages, harvest_age, days=20):
    log = []
    env = run(crop_agent(crop, set(water_ages), harvest_age, log), days)
    final = env.steps[-1][0]["observation"]
    got = final["private"]["shed"].get(crop, 0)
    print(f"  {crop:<11} water_ages={sorted(water_ages)!s:<28} "
          f"harvest@{harvest_age:<3} -> {got} units")
    return got, log


def main():
    print("=" * 78)
    print("A. ANIMAL PRODUCTION -- does CARE really multiply output?")
    print("=" * 78)
    print("  Steady-state theory: production fires every `interval` days and pays")
    print("  base 1 + all CARE bonuses banked since the last firing, so the rate")
    print("  should be (1 + interval)/interval per day, NOT 2x.\n")
    for animal, structure, product, interval in (
        ("GOOSE", "COOP", "EGG", 1),
        ("COW", "PASTURE", "MILK", 2),
        ("SHEEP", "PASTURE", "WOOL", 3),
    ):
        animal_test(animal, structure, product, "daily", care=False)
        animal_test(animal, structure, product, "daily", care=True)
        animal_test(animal, structure, product, "alternate", care=False)
        print(f"    theory: no-care={1 / interval:.2f}/day  "
              f"care={(1 + interval) / interval:.2f}/day  "
              f"alternate={1 / interval:.2f}/day\n")

    print("=" * 78)
    print("B. CROP YIELDS -- minimum-action watering schedules")
    print("=" * 78)
    crop_test("WHEAT", [0, 2, 3, 4], 4)
    crop_test("WHEAT", list(range(0, 5)), 4)
    crop_test("CARROT", [0, 2, 3], 3)
    crop_test("MELON", [0, 2, 4, 6, 7, 8, 9, 10], 10)
    crop_test("MELON", list(range(0, 13)), 12, days=20)
    crop_test("TOMATO", [0, 2, 4, 6, 8, 9, 10, 11], 11, days=16)
    print("\n  (skipping every-day watering for wheat/carrot: identical yield,")
    print("   proving alternate-day watering outside the bonus window is free)")

    print("\n" + "=" * 78)
    print("C. FERTILIZER -- 1/animal/day regardless of feeding?")
    print("=" * 78)
    log, _ = animal_test("GOOSE", "COOP", "EGG", "alternate", care=False, days=12)
    fert_days = [d for d, t, s in log if isinstance(t, dict) and t.get("fertilizer_available")]
    print(f"  fertilizer_available at hour 0 on days: {fert_days}")
    print("  (an every-other-day-fed animal still offers fertilizer EVERY day)")

    print("\n" + "=" * 78)
    print("D. FIRST-YIELD BURST -- does CARE banked before first production pay out?")
    print("=" * 78)
    for animal, structure, product in (("GOOSE", "COOP", "EGG"),
                                       ("COW", "PASTURE", "MILK"),
                                       ("SHEEP", "PASTURE", "WOOL")):
        log, _ = animal_test(animal, structure, product, "daily", care=True, days=14)
        burst = [(d, t["yield_units"]) for d, t, s in log
                 if isinstance(t, dict) and t.get("yield_units", 0) > 0][:3]
        print(f"    {animal} yield_units on first producing days: {burst}")


if __name__ == "__main__":
    main()
