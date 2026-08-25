"""Unit + integration tests for main.py.  Run: python test_agent.py

Every public function is exercised, and the game-model pieces are checked
against the real kaggle_environments implementation rather than against my
own assumptions.
"""
import sys
import traceback

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as ENV

import main

_pass = 0
_fail = 0


def check(name, got, want):
    global _pass, _fail
    if got == want:
        _pass += 1
        print(f"  ok   {name}")
    else:
        _fail += 1
        print(f"  FAIL {name}: got {got!r}, want {want!r}")


def check_true(name, cond, detail=""):
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"  ok   {name}")
    else:
        _fail += 1
        print(f"  FAIL {name} {detail}")


def section(title):
    print(f"\n--- {title} ---")


# ===========================================================================
section("constants match the shipped environment")
# ===========================================================================
check("TURNS_PER_DAY", main.TURNS_PER_DAY, 24)
check("PRODUCTS", main.PRODUCTS, ENV.PRODUCTS)
check("MARKET_I0", main.MARKET_I0, ENV.MARKET_I0)
check("PRICE_FLOOR", main.PRICE_FLOOR, ENV.PRICE_FLOOR)
check("LAND_PRICES", main.LAND_PRICES, ENV.LAND_PRICES)
check("SHOPS", main.SHOPS, ENV.SHOPS)
check("DIRS", main.DIRS, ENV.FARMER_MOVES)
check("SHED_TILES", main.SHED_TILES, ENV._shed_access_tiles(10))

for crop, spec in ENV.CROPS.items():
    mine = main.CROPS[crop]
    check(f"CROPS[{crop}].seed", mine["seed"], spec["seed"])
    check(f"CROPS[{crop}].first", mine["first"], spec["first_yield_day"])
    check(f"CROPS[{crop}].maxday", mine["maxday"], spec["max_yield_day"])
    check(f"CROPS[{crop}].cap", mine["cap"], spec["max_yield"])
    check(f"CROPS[{crop}].ongoing", mine["ongoing"], spec["ongoing"])

for kind, spec in ENV.ANIMALS.items():
    mine = main.ANIMALS[kind]
    check(f"ANIMALS[{kind}].cost", mine["cost"], spec["cost"])
    check(f"ANIMALS[{kind}].first", mine["first"], spec["first_yield_day"])
    check(f"ANIMALS[{kind}].interval", mine["interval"], spec["interval"])
    check(f"ANIMALS[{kind}].held", mine["held"], spec["max_held"])
    check(f"ANIMALS[{kind}].prod", mine["prod"], spec["product"])

# ===========================================================================
section("market_price matches the environment exactly")
# ===========================================================================
_env_params = ENV._resolve_market_params(None)
_mismatch = 0
for item in main.PRODUCTS:
    for delta in (-4000, -1000, -400, -100, -1, 0, 1, 100, 400, 1000, 4000):
        inv = main.MARKET_I0 + delta
        mine = main.market_price(item, inv)
        theirs = ENV.market_price(item, inv, _env_params)
        if mine != theirs:
            _mismatch += 1
            if _mismatch <= 5:
                print(f"  FAIL {item} @ I0{delta:+d}: mine={mine} env={theirs}")
check_true("market_price agrees with env at 99 sample points",
           _mismatch == 0, f"({_mismatch} mismatches)")

# Spot-check against the published table in the competition README.
check("price WHEAT at I0-T", main.market_price("WHEAT", 10000 - 400), 45)
check("price WHEAT at I0+T", main.market_price("WHEAT", 10000 + 400), 20)
check("price STRAWBERRY at I0-T", main.market_price("STRAWBERRY", 10000 - 100), 204)
check("price STRAWBERRY at I0+T", main.market_price("STRAWBERRY", 10000 + 100), 1)
check("price MILK at I0-T", main.market_price("MILK", 10000 - 122), 256)
check("price MILK at I0+T", main.market_price("MILK", 10000 + 122), 1)
check("price WOOL at I0-T", main.market_price("WOOL", 10000 - 105), 240)
check("price MELON at I0-T", main.market_price("MELON", 10000 - 300), 300)
check("price FERTILIZER at I0+T", main.market_price("FERTILIZER", 10000 + 200), 60)
check("price floors at 1", main.market_price("MILK", 10000 + 99999), 1)

# ===========================================================================
section("units_sellable")
# ===========================================================================
check("sell nothing when have=0", main.units_sellable("MILK", 10000, 100, 0), 0)
check("sell nothing below floor",
      main.units_sellable("MILK", 10000 + 200, 150, 10), 0)
check("sell all when floor is 1",
      main.units_sellable("MILK", 10000, 1, 10), 10)

_n = main.units_sellable("MILK", 10000, 130, 200)
check_true("milk sell depth at floor 130 is partial",
           0 < _n < 200, f"(got {_n})")
check_true("price after selling that many is still >= floor",
           main.market_price("MILK", 10000 + _n - 1) >= 130)
check_true("selling one more would breach the floor",
           main.market_price("MILK", 10000 + _n) < 130)

# Stable goods absorb far more volume than premium goods.
_wheat_depth = main.units_sellable("WHEAT", 10000, 18, 5000)
_milk_depth = main.units_sellable("MILK", 10000, 130, 5000)
check_true("wheat absorbs more volume than milk",
           _wheat_depth > _milk_depth,
           f"(wheat={_wheat_depth} milk={_milk_depth})")

# ===========================================================================
section("geometry helpers")
# ===========================================================================
check("manhattan", main.manhattan((0, 0), (3, 4)), 7)
check("step EAST", main.step_toward((0, 0), (5, 0)), ["EAST"])
check("step WEST", main.step_toward((5, 0), (0, 0)), ["WEST"])
check("step SOUTH (y grows down)", main.step_toward((0, 0), (0, 5)), ["SOUTH"])
check("step NORTH", main.step_toward((0, 5), (0, 0)), ["NORTH"])
check("step on target", main.step_toward((2, 2), (2, 2)), ["PASS"])

# Directions must actually move the way the environment says they do.
for op, (dx, dy) in ENV.FARMER_MOVES.items():
    start = (5, 5)
    target = (5 + dx, 5 + dy)
    check(f"step_toward picks {op}", main.step_toward(start, target), [op])

check("nearest_shed_tile from NW corner", main.nearest_shed_tile((0, 0)), (4, 4))
check("nearest_shed_tile from SE corner", main.nearest_shed_tile((9, 9)), (5, 5))
check_true("shed_dist is 0.0 at the four centre tiles",
           all(abs(main.shed_dist(x, y) - 1.0) < 1e-9 for (x, y) in main.SHED_TILES))

# ===========================================================================
section("targets / planting deadlines")
# ===========================================================================
check("day 0 cows", main.targets(0)["COW"], 2)
check("day 0 sheep", main.targets(0)["SHEEP"], 2)
check("day 0 melon", main.targets(0)["MELON"], 12)
check("day 0 wheat", main.targets(0)["WHEAT"], 7)
check("day 0 strawberry", main.targets(0)["STRAWBERRY"], 0)
check("day 14 cows", main.targets(14)["COW"], 8)
check("day 14 sheep", main.targets(14)["SHEEP"], 6)
check("day 14 strawberry", main.targets(14)["STRAWBERRY"], 42)
check("melon stops after day 19", main.targets(20)["MELON"], 0)
check("strawberry stops after day 19", main.targets(20)["STRAWBERRY"], 0)
check("wheat stops after day 27", main.targets(28)["WHEAT"], 0)
check_true("no goose ever", "GOOSE" not in main.targets(10))

_day0_cost = (2 * main.ANIMALS["COW"]["cost"] + 2 * main.ANIMALS["SHEEP"]["cost"]
              + 12 * main.CROPS["MELON"]["seed"] + 7 * main.CROPS["WHEAT"]["seed"])
check("day 0 build order costs $2830", _day0_cost, 2830)
check_true("day 0 build fits in $3000 with room to hire",
           _day0_cost < 3000, f"(costs {_day0_cost})")

# ===========================================================================
section("live game: state, survey, plan, tasks, schedule, orders")
# ===========================================================================
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 101})
reset = env.reset(num_agents=2)
obs0 = reset[0].observation
obs0["player"] = 0

st = main.S(obs0)
check("S.pid", st.pid, 0)
check("S.day", st.day, 0)
check("S.hour", st.hour, 0)
check("S.money", st.money, 3000.0)
check("S.days_left", st.days_left, 29)
check("S.endgame at day 0", st.endgame, False)
check("S.unlocked at start", st.unlocked, ["NW"])
check("S.units has just the farmer", len(st.units), 1)
check_true("S.prices covers every product",
           all(p in st.prices for p in main.PRODUCTS))
check_true("S.minv covers every product",
           all(p in st.minv for p in main.PRODUCTS))

sur = main.survey(st)
check("survey: one unlocked quadrant = 25 tiles", sur["n_tiles"], 25)
check("survey: all 25 empty at start", len(sur["empties"]), 25)
check("survey: no animals", sum(sur["animals"].values()), 0)
check("survey: no crops", len(sur["plants"]), 0)
check_true("survey: empties sorted nearest-shed-first",
           main.shed_dist(*sur["empties"][0]) <= main.shed_dist(*sur["empties"][-1]))

check("town_rate FERTILIZER is 0", main.town_rate(st, "FERTILIZER"), 0.0)
check("town_rate WHEAT with no shops", main.town_rate(st, "WHEAT"), 1.0)

plan = main.plan_turn(st, sur)
for key in ("targets", "want", "crop_gap", "pasture_gap", "feed_keep",
            "floors", "herd", "buy_land"):
    check_true(f"plan has '{key}'", key in plan)
check("plan wants 2 cows on day 0", plan["want"]["COW"], 2)
check("plan wants 2 sheep on day 0", plan["want"]["SHEEP"], 2)
check("plan needs 4 pastures on day 0", plan["pasture_gap"], 4)
check("plan buys no land on day 0", plan["buy_land"], False)
check_true("floors defined for every product",
           all(p in plan["floors"] for p in main.PRODUCTS))

tasks = main.build_tasks(st, sur, plan)
check_true("day 0 produces tasks", len(tasks) > 0, f"(got {len(tasks)})")
check_true("all task keys are unique",
           len({t.key for t in tasks}) == len(tasks))
check_true("all task positions are on the board",
           all(0 <= t.pos[0] < 10 and 0 <= t.pos[1] < 10 for t in tasks))
check_true("all task values are positive",
           all(t.value > 0 for t in tasks))
check_true("day 0 wants pastures built",
           any(t.ops[0] == "BUILD_PASTURE" for t in tasks))

sticky = {}
acts = main.schedule(st, sur, plan, sticky)
check("schedule returns one action per unit", len(acts), len(st.units))
check_true("every action is a non-empty list",
           all(isinstance(a, list) and a for a in acts))

orders = main.market_orders(st, sur, plan, {})
check_true("day 0 issues orders", len(orders) > 0)
check_true("never exceeds the 10-order cap", len(orders) <= main.MAX_ORDERS)
_ops = [o[0] for o in orders]
check_true("day 0 buys animals", "BUY_ANIMAL" in _ops, f"(got {_ops})")
check_true("day 0 hires", "HIRE" in _ops, f"(got {_ops})")

# ===========================================================================
section("agent() contract on a fresh observation")
# ===========================================================================
main._MEM.clear()
action = main.agent(obs0)
check_true("returns a dict", isinstance(action, dict))
check_true("has farmer/hands/market",
           set(action) == {"farmer", "hands", "market"})
check_true("farmer op is a list", isinstance(action["farmer"], list))
check_true("hands is a list", isinstance(action["hands"], list))
check_true("market is a list", isinstance(action["market"], list))
check_true("market within cap", len(action["market"]) <= main.MAX_ORDERS)

_LEGAL = (set(ENV.FARMER_MOVES)
          | {"PASS", "WATER", "HARVEST", "PLANT", "FERTILIZE", "DIG",
             "FEED", "CARE", "COLLECT_FERTILIZER", "BUILD_COOP",
             "BUILD_PASTURE", "PICKUP", "DROP", "PLACE"})
check_true("farmer op is legal", action["farmer"][0] in _LEGAL,
           f"(got {action['farmer']})")

_MARKET_OPS = {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE",
               "BUY_LAND"}
check_true("all market ops legal",
           all(o[0] in _MARKET_OPS for o in action["market"]),
           f"(got {[o[0] for o in action['market']]})")

# ===========================================================================
section("_MEM isolation between episodes")
# ===========================================================================
main._MEM.clear()
main.agent(obs0)
main._MEM[0]["sticky"][0] = "stale-marker"
main._MEM[0]["bought"]["COW"] = 99
main.agent(obs0)          # obs0 is step 0, so this must reset
check("step 0 clears stale sticky", main._MEM[0]["sticky"].get(0), None)
check("step 0 clears stale bought", main._MEM[0]["bought"].get("COW"), None)

# ===========================================================================
section("full 720-turn game (no crashes, sane result)")
# ===========================================================================
import time
main._MEM.clear()
_timings = []


def timed_agent(obs):
    t0 = time.time()
    try:
        out = main.agent(obs)
    except Exception:
        traceback.print_exc()
        raise
    _timings.append(time.time() - t0)
    return out


env2 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 101})
env2.run([timed_agent, "pass"])
final = env2.steps[-1]
score = float(final[0].reward or 0)

check("game reached DONE", final[0].status, "DONE")
check_true("scored above the $3000 starting bank", score > 3000,
           f"(scored {score:.0f})")
check_true("beat the passive opponent", score > float(final[1].reward or 0))
check("agent acted on all 720 turns", len(_timings), 720)

_worst = max(_timings) * 1000
_mean = sum(_timings) / len(_timings) * 1000
check_true("worst turn under the 1s actTimeout", _worst < 1000,
           f"(worst {_worst:.0f}ms)")
print(f"       turn time: mean {_mean:.1f}ms  worst {_worst:.0f}ms")

# Did the scripted build order actually happen?
_farm = final[0].observation["farms"][0]
_counts = {}
for _row in _farm["tiles"]:
    for _t in _row:
        if isinstance(_t, dict):
            if _t.get("animal"):
                _counts[_t["animal"]] = _counts.get(_t["animal"], 0) + 1
            elif _t.get("kind") == "PLANT":
                _counts[_t["crop"]] = _counts.get(_t["crop"], 0) + 1
print(f"       final board: {_counts}")
print(f"       final land:  {_farm['unlocked_quadrants']}")
print(f"       final score: ${score:,.0f}")

check_true("owns 3 quadrants by the end",
           len(_farm["unlocked_quadrants"]) >= 3,
           f"(got {_farm['unlocked_quadrants']})")
check_true("kept a herd alive",
           _counts.get("COW", 0) + _counts.get("SHEEP", 0) >= 8,
           f"(got {_counts})")

# ===========================================================================
print("\n" + "=" * 58)
print(f"passed {_pass}   failed {_fail}")
print("=" * 58)
sys.exit(1 if _fail else 0)
