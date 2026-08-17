# Kaggriculture — Competitive Strategy

Derived from the shipped environment source
(`kaggle_environments/envs/kaggriculture/kaggriculture.py`), not from the README
prose. Every load-bearing claim below is verified against the real interpreter by
`analysis/verify_mechanics.py`; the economics come from `analysis/market_analysis.py`
and `analysis/portfolio_sim.py`.

Where the README and the code disagree, the code wins — and they disagree on the
single most important mechanic in the game.

---

## 1. The four decisive facts

**1. `CARE` does not "double" animal output — it multiplies it by `1 + interval`.**
This is the biggest lever in the game and the README understates it badly.

`_daily_refresh_animals` banks `+1` into `pending_care_bonus` on every day the
animal is both fed *and* cared for, and pays out the **entire bank** on the next
scheduled production. So the steady-state rate is `(1 + interval) / interval` per
day, not `2 ×` the base rate. Measured over a 30-day season with one animal:

| Animal | interval | no CARE | with CARE | multiplier |
| :--- | ---: | ---: | ---: | ---: |
| Goose | 1 | 25 eggs | **52** | 2.1× |
| Cow | 2 | 11 milk | **36** | 3.3× |
| Sheep | 3 | 8 wool | **34** | 4.25× |

The longer the interval, the more CARE is worth. Removing CARE from the season
model costs **−$67k**. `CARE` is one action per animal per day and it is the
highest-value action in the game.

There is a matching kicker: the bank accumulates *before* the first production
too, so the first payout is a burst clipped by `max_held` — a cow's first
harvest is **6 milk on day 8**, a sheep's is **6 wool on day 6**, a goose's is
**4 eggs on day 4**. A $500 sheep repays itself in one harvest.

**2. Every surviving animal yields 1 FERTILIZER per day, fed or not.**
`fertilizer_available = True` is set for every animal that survives the
end-of-day refresh, independent of `fed_today`. Fertilizer's base price is $100
and it is the *only* product with zero town demand — no shop wants it and the
town center explicitly excludes it. So it is a pure first-come pool of ~493
units (~$25k) that never refills. It is also free cash from day 1, before any
crop or animal product exists.

**3. The town's appetite, not the glut curve, sets the real price.**
Reading only the glut table makes premium goods look untouchable (31 strawberries
halve the price; 59 wool hit the $1 floor). But shops consume 6×/day each and the
town center 1×/day, and that demand *far exceeds* what one farm can produce:

| Product | Base | Shops wanting it | Units/day at full unlock | Season demand | Value at base |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Strawberry | 120 | 4/8 | 25.0 | 426 | $51,120 |
| Milk | 160 | 3/8 | 19.0 | 327 | $52,320 |
| Wool | 200 | 1/8 (×2) | 13.0 | 228 | $45,600 |
| Wheat | 25 | 5/8 | 31.0 | 525 | $13,125 |
| Carrot | 35 | 2/8 | 19.0 | 327 | $11,445 |
| Tomato | 60 | 2/8 | 13.0 | 228 | $13,680 |
| Egg | 50 | 2/8 | 13.0 | 228 | $11,400 |
| **Melon** | 250 | **0/8** | 1.0 | **30** | — |
| **Fertilizer** | 100 | **0/8** | **0.0** | **0** | — |

Sell *at or below* that rate and the price sits at base or drifts **above** it.
Sell faster and you fall down the glut curve. This turns "premium goods are a
trap" into "premium goods are the whole game, if you meter them."

Two products are exceptions with no recovery at all — **melon and fertilizer**.
Their pools are strictly first-come-first-served.

**4. Labour is nearly free; actions are the real currency.**
`HIRE` costs `fib(n)` where `n` is the hires already made *today*, and it resets
each morning. Ten hands cost **$143 for the day** and buy 264 actions.

| Hands | Day cost | Actions/day |
| ---: | ---: | ---: |
| 8 | $54 | 216 |
| 10 | $143 | 264 |
| 12 | $376 | 312 |
| 14 | $986 | 360 |
| 16 | $2,583 | 408 |

The knee is 12–14. Never let an action go idle for want of a hand — but do not
buy hands you have no work for either.

---

## 2. Verified mechanics worth exploiting

Run `python analysis/verify_mechanics.py` to reproduce all of this.

**Watering outside the bonus window is wasted.** A plant dies only after *two*
consecutive dry days and starts at `consecutive_unwatered = 1`, so the planting
day is mandatory and then every *other* day suffices — except inside the bonus
window, where each watered day adds yield.

| Crop | Water on ages | Harvest | Units | Notes |
| :--- | :--- | ---: | ---: | :--- |
| Wheat | 0, 2, 3, 4 | 4 | 4 | identical to watering all 5 days |
| Carrot | 0, 2, 3 | 3 | 3 | |
| Melon | 0, 2, 4, 6, 7, 8, 9, 10 | **10** | 6 | ages 11–12 add nothing — harvest at 10 |
| Tomato | 0, 2, 4, 6, 8, 9, 10, 11 | 11 | 4 | |

Melon is the standout: **6 units for 10 actions**, and harvesting at age 10
instead of 12 frees the tile two days early.

**Every-other-day feeding keeps an animal alive at full base output** (production
is not gated on `fed_today` — only the CARE bonus is), and it still yields
fertilizer daily. But the placement day counts as unfed, so an alternate-feed
schedule must feed on **odd** days; feeding on even days lets the animal escape
at the end of day 1. Use this only as a wheat-shortage fallback — feeding daily
*without* CARE is strictly wasteful, since it costs double the wheat for
identical output.

**Other mechanics that matter:**
- Market orders resolve *after* unit actions, so a seed bought on turn `t` is
  plantable on turn `t+1`. Same for hires and animals.
- `(4,4)` is simultaneously an NW farm tile and a shed-access tile — the farmer
  can `PICKUP`, `FEED`, `CARE` and `DROP` there without moving.
- Shed cap is 100 **including bought goods** — `BUY_PRODUCT` fails outright when
  the shed is full. Overflow at the end-of-day drop is destroyed.
- Harvest lands in unit inventory and auto-drops to the shed at end of day, so
  the natural loop is *harvest today, sell tomorrow morning*. No `DROP` action
  needed unless the shed is about to overflow.
- Selling at the $1 floor does **not** add to market inventory, so dumping junk
  is never actively harmful — just near-worthless.
- Locked tiles are passable, and hands spawn on shed-access tiles regardless of
  lock. The first hire of each day lands on `(5,4)`, locked until NE is bought;
  it can simply walk back.

---

## 3. Target portfolio

From the sweep in `analysis/portfolio_sim.py`, across 729 tile allocations.
Roughly 92 of 100 tiles, leaving slack for weeds and pathing:

| Use | Tiles | Why |
| :--- | ---: | :--- |
| **Cow** | 12–16 | Best net/tile-day. 1.5 milk/day into a 327-unit pool. |
| **Sheep** | 8 | 1.33 wool/day into a 228-unit pool. More than 8 crashes wool to $1. |
| **Goose** | 8–10 | Cheapest animal → fastest fertilizer ramp; egg pool barely gluts (log curve). |
| **Wheat** | 30 | Feed self-sufficiency. Not optional — see below. |
| **Strawberry** | 16 | Only pool nobody can saturate; ends the season *above* base. |
| **Melon** | 14 | The day-10 cash bomb that funds everything else. |

Deliberately **excluded**: carrot and tomato. Both are ~$20/tile-day against
$100+ for animals, and their pools are small. Skip them.

**Wheat self-sufficiency is existential.** Removing home wheat and buying all
feed collapses the model from ~$164k to ~$0: cows and sheep bought early cannot
be fed, they escape, and the farm never recovers. Wheat is simultaneously the
animal feedstock *and* the most-demanded shop input (5/8 shops), so its price
climbs from $25 to ~$50 over the season while you need it most. Grow it.

**Right-sizing is visible in the closing prices.** A correctly sized herd ends
the season with each product near or above base:

| | Milk | Wool | Egg | Strawberry |
| :--- | ---: | ---: | ---: | ---: |
| 12 cow / 8 sheep / 8 goose | $226 | $196 | $46 | $265 |
| 20 cow / 8 sheep | $34 | $196 | $46 | $265 |
| 12 cow / 10 sheep (overbuilt) | $218 | **$1** | $43 | $265 |

A product ending at $1 means you built too much of it. Strawberry's stubborn
$265 means the opposite — there is headroom left there in every configuration
tested.

---

## 4. Opening book

Money is the binding constraint until day 10; tiles and actions bind after.

**Day 0** — starting bank $3,000.
1. Turn 0 market: `BUY_LAND` (NE, $1,000), `BUY_ANIMAL GOOSE`×2, `BUY_SEED MELON`×n,
   `BUY_PRODUCT WHEAT 20`. Hire 4–6 hands ($7–20).
2. Buy the *cheapest* animals first. Early on, animal **count** matters more than
   animal type, because fertilizer is 1/animal/day regardless of species and it
   is the only revenue before day 4. Goose-first priority scored +$9k in the model.
3. Build coops/pastures (free — 1 action each), place animals, plant melons.
4. Reserve ~$150 cash so the next day's wheat purchase cannot fail.

**Days 1–3** — fertilizer is already selling at ~$100/unit. Reinvest every coin
into animals and melon seed. Start `CARE` about 5 days before each animal's
first yield; banking earlier than that overflows `max_held` and is wasted.

**Days 4–7** — eggs arrive day 4, wool day 6. Cash compounds. Buy SW ($2,000).

**Day 10 — the melon bomb.** 14 tiles × 6 = 84 melons hit the market at once for
roughly **$18–21k in a single day**. This is the pivot: it funds SE ($4,000),
the full cow and sheep herd, and 10+ hands for the rest of the season.

**Days 11–20** — steady state. Replant melon once (harvest day 21), plant
strawberry by day 13 at the latest so all four yields fire before day 29.

**Days 21–29** — stop buying animals after ~day 22 (they cannot repay). On the
final two days, drop all reservation prices to $1 and liquidate everything:
unsold inventory scores zero.

---

## 5. The melon race

Melon is worth $250 base with **zero shop demand** — the pool never refills, so
whoever sells first takes it.

| You sell first | Revenue |
| ---: | ---: |
| 30 melons | $7,416 |
| 78 melons | $17,952 |
| 158 melons | $26,485 (pool exhausted) |

| Opponent dumped 100 first | Your revenue | Loss |
| ---: | ---: | ---: |
| your next 30 | $3,546 | −52% |
| your next 78 | $4,784 | −73% |

The same logic applies to fertilizer. Earliest possible melon harvest is age 10,
so **day 10 is a hard deadline** — plant on day 0. If the opponent beats you to
it, your melons are worth a third as much, which is why melon tiles should be
converted to animals in the back half rather than replanted indefinitely.

---

## 6. Selling policy

**Reservation selling, not dumping.** Sell a product only while its marginal
price is at or above ~85–100% of base; otherwise hold and let town demand drain
the inventory back down. Measured against the alternatives:

| Policy | Result |
| :--- | ---: |
| Reservation at 100% of base | best |
| Reservation at 85% | −$0.5k |
| Reservation at 60% | −$5k |
| Dump everything immediately | **−$14k** |

Two exceptions:
- **Melon and fertilizer** never recover, so hold out only against a low floor
  (~10–15% of base) and prioritise selling them *early* to beat the opponent.
- **The last two days**: reservation goes to $1. Liquidate everything.

**You can compute the opponent's sales exactly.** Market inventory is shared and
visible; the town's schedule is deterministic (shops tick at `step % 4 == 0`,
center at `step % 24 == 0`) and `town.unlocked_shops` is public. So each turn:

```
opponent_net = Δinventory[p] − (my_sales − my_buys) + town_consumption[p]
```

Use it as a trigger: if melon or fertilizer inventory starts climbing from a
source that is not you, the opponent is liquidating — abandon your reservation
price on that product and sell immediately.

---

## 7. Action economy and logistics

A ~32-animal, ~60-crop-tile farm needs roughly **280 actions/day**, which is
11–12 hands. Budget per animal per day: `FEED` + `CARE` + `COLLECT_FERTILIZER`
+ amortised `HARVEST` + ~1 move ≈ 4.2 actions.

**Harvest cadence is forced by `max_held`** — production is clipped, so a late
harvest is lost yield:

| Animal | Produces | `max_held` | Harvest at least every |
| :--- | :--- | ---: | ---: |
| Goose | 2/day | 4 | 2 days |
| Cow | 3 per 2 days | 6 | 4 days |
| Sheep | 4 per 3 days | 6 | 3 days |

**Routing.** Hands spawn at the shed each morning and drop inventory there each
night. Give each hand a contiguous strip and let it serpentine — move, act, move,
act. Put animals nearest the shed (4.2 actions/day each, plus wheat pickups) and
melons/wheat furthest (~1 water/day). One `PICKUP WHEAT 15` covers fifteen
`FEED`s, so batch it at the start of a hand's route.

**Watch the shed.** A mature farm produces ~90 items/day against a 100 cap.
Sell the shed down every morning, and if a day's harvest threatens the cap, have
a hand `DROP` mid-day so the goods can be sold before the overnight discard.

---

## 8. Agent architecture

A rule-based planner is sufficient; the game is deterministic and the policy
above is explicit. Suggested layering:

1. **Market brain** (pure function of the shared observation) — track inventory
   deltas, infer opponent flow, compute per-product reservation prices, emit the
   ≤10 orders per turn: sells first, then feed wheat, then capital purchases.
2. **Estate planner** (once per day) — decide land purchases, herd additions,
   what to plant on each free tile, how many hands to hire.
3. **Task queue** (once per day) — enumerate every needed tile action
   (`WATER` / `FEED` / `CARE` / `COLLECT_FERTILIZER` / `HARVEST` / `PLANT` /
   `DIG`), score by urgency, and assign to units by travel distance.
4. **Unit controller** (per turn) — each unit either acts on its tile or steps
   toward its next target.

Order of priority when actions are scarce: `FEED` (an unfed animal dies) →
`WATER` on a plant at `consecutive_unwatered == 1` → `HARVEST` at `max_held` →
`CARE` → `COLLECT_FERTILIZER` → bonus-window `WATER` → everything else.

---

## 9. Expected final score

Both farms sell into **one** shared order book, so the opponent's volume is
headroom you no longer have. Modelled head-to-head (`scoring()` in
`portfolio_sim.py`), day-29 bank:

| Opponent | Our bank | Theirs |
| :--- | ---: | ---: |
| none (solo ceiling) | $189,827 | — |
| `starter` baseline (carrot loop) | $189,827 | $3,000 |
| competent crop-only agent | $177,556 | $23,735 |
| goose-spam agent | $150,624 | $22,092 |
| **equally strong mirror** | **$103,082** | $92,122 |

**Read the mirror row, not the solo row.** A good opponent costs ~45% of the
ceiling, and the margin in the mirror is only 12% — which comes purely from
alternating who sells first. Against a true mirror this is close to a coin flip,
so the win has to be earned in *execution*: reaching melon and fertilizer a day
earlier, tighter routing, fewer missed `CARE` actions.

Closing prices in the mirror show exactly where the damage lands:

| | Milk | Wool | Strawberry | Melon | Egg | Wheat | Fertilizer |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Solo | $222 | $196 | $265 | $60 | $46 | $49 | $1 |
| Mirror | $53 | **$1** | $230 | **$4** | $44 | $49 | $1 |

Contested finite pools — melon, wool, fertilizer — collapse to the floor. The
deep log-curve pools (egg, wheat) barely move, and strawberry stays high because
neither side can physically saturate it. **Under contention, shift tiles from
wool and melon toward strawberry and eggs.**

### What the model does not capture

These numbers are an upper bound on a *correct* policy, not a prediction of a
built agent. The model assumes perfect routing, every animal fed and cared every
single day, no wasted actions, no weed spawns, clean shed management, and
frictionless harvest→shed→market flow. A real implementation loses ground to
pathing, the one-turn lag on newly hired hands, shed overflow, and mistimed
harvests against `max_held`.

Applying a judgement-based 25–40% friction haircut, a well-built agent should
realistically bank roughly **$60k–110k against strong opposition**, and
**$120k–170k against the weak agents** that populate an early leaderboard. Treat
those as ranges, not forecasts — they are my estimate on top of the model, not
model output.

### What survives contact

The *relative* ordering is stable across every configuration tested:

1. `CARE` every animal, every day — worth more than any other single decision.
2. Buy all three land quadrants — worth −$72k to skip.
3. Grow your own wheat — skipping it is fatal, not merely expensive.
4. Meter sales against town demand instead of dumping.
5. Win the day-10 melon race.
6. Animals over crops, except melon, strawberry, and feed wheat.

## Reproducing

```bash
python analysis/market_analysis.py    # price curves, town demand, unit economics
python analysis/verify_mechanics.py   # mechanics checked against the real interpreter
python analysis/portfolio_sim.py      # portfolio sweep, sensitivity, herd refinement
```
