# Project Maestro — Engineer Handover

**For the build engineer (Gemini).** Read this whole file before writing code. Then read
`README.md` (spec, phase gates) and `CLAUDE.md` (role split). This is a living document,
kept current every round — last updated 2026-08-24. §4 is authoritative for current state
and next steps; §7 ("Next actions") has been removed as superseded — §4 supersedes it.

Claude remains **Simulation Architect & Adversarial Verifier**: it owns the spec, the
engine ground truth, and accept/reject on every deliverable. It does not build. You build.
Neither role reviews its own work.

---

## 0. Why this project is paranoid about verification

Before Maestro, this codebase spent weeks on agents whose reported results were wrong:
benchmarks run against near-inert opponents, features reported as shipped that silently
crashed to all-PASS, win rates inflated by mis-sorted folders, and a headline "finding"
that real games end near $3,000 (it was an Elo column misread as money — real games end
near $88,000). Maestro was started clean to escape that.

So the standing rules are non-negotiable:

1. **Engine source is the only authority.** Cite a line reference for every mechanic.
   `C:/Users/GauravPatel/AppData/Local/Programs/Python/Python313/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py`
   Do not trust prose in this file without re-checking it.
2. **State n, and state whether the run finished.** A partial run is not a result.
3. **Name the opponent on every benchmark.** See §4 — this rule exists because a whole
   benchmark round was invalidated by an unnamed do-nothing opponent.
4. **One variable at a time** against a freshly-run baseline on a fixed seed set.
5. **Say plainly when a gate fails.** Do not reframe a miss as a discovery. Do not invent
   pass thresholds after seeing results (this happened; it cost a review cycle).
6. **No tapes.** No recorded action sequence as strategy.
7. **The old `C:/Coding` replay folders are not evidence** — mixed bag of our own old
   agents plus assorted bots. Parser smoke-tests only; no reported number from them.

---

## 1. The goal

A **master agent** that is correct across the *entire* town-shop space, not one path
through it — strong enough to be a training benchmark for human players. The target object:

    policy(demand_pressure_vector, day, capital, opponent_supply)
        -> portfolio + build/plant schedule + sell timing

Shops reveal progressively, so the policy must commit under partial information and
re-plan. "Cover all shop cases" is not 6,435 tapes: the 8 draws collapse to a
**9-dimensional demand-pressure vector** over products, and that vector determines the
optimal portfolio.

"Undefeated" is not provable against an unbounded human. The auditable form is **no known
exploitable shop archetype**, verified per archetype on both seats.

Deadline: end of September 2026.

**Score target, calibrated against real data (see `README.md` for the full writeup): a
uniform 180k+ floor across all seeds is not realistic and must not be a design target.**
Ryo Hasegawa (#1 real player), 104 real matches, 95W-9L: mean $98,383, max **$168,259**,
never above that. Wider 1,394-trajectory official dataset: max $170,964, **zero** at or
above $180,000. Target instead: push the self-play mean well above the real top-tier
average ($88,667) and raise the floor on adverse shop draws; treat $140-170k as an
achievable peak on favorable draws, not an average or a floor. `MASTER_DOSSIER.md` Part 40
("5-route Archetype Grid Benchmark Matrix") is unverified — no disclosed opponent, and a
nearby section in the same document with similar-magnitude numbers is explicitly labeled
vs-starter/vs-random. Do not design toward it either.

---

## 2. Verified engine ground truth

Every item below was checked against engine source this session. Line refs are to
`kaggriculture.py`.

### Core
- **Reward is final money**: `s.reward = float(obs0.farms[s.observation.player]["money"])` (963).
- 720 steps = 30 days x 24 turns. Starting money $3,000. `shedCapacity` 100.
  `LAND_PRICES = [1000, 2000, 4000]` (97) for NE/SW/SE; NW free.
- `env.run()` syncs `obs["step"]` for **both** seats. The `None` step seen in stored replay
  JSON is a serialization artifact of the saved file, not what a live agent receives.
- Episode horizon is steps 0..719. Stepping to 720 adds a phantom morning step on day 30 —
  this caused a spurious $787 fast-engine mismatch. Do not off-by-one this.

### Shed (a real throughput bottleneck)
- Personal inventories flush to the shared shed **once per day** via
  `_drop_inventories_to_shed` (843), called from `_end_of_day` (878).
- The cap is **combined across all products**: `current = sum(v for k, v in shed.items())`,
  and overflow is **silently discarded** (`del inv[item]` runs unconditionally).
- Seeds are tracked separately and never pass through the shed.
- `HARVEST` puts yield in the actor's own inventory. `DROP` (shed-adjacent, whole
  inventory) or `PLACE` (specific item/qty) moves it before the nightly flush.

### Town shops
- `SHOPS` (103-118), 8 types. `MAX_SHOP_INSTANCES = 8` (118).
- One instance drawn **with replacement every 3 days**, so **days 3, 6, 9, 12, 15, 18, 21,
  24 only** — eight draws, never nine (886-891). 8^8 ordered sequences; 6,435 multisets.
- **Shops create scarcity; they do not buy from you.** `_town_consume` (727) runs every
  `townShopSellInterval` = 4 steps and *decrements market inventory* per instance;
  single-product shops use **multiplier 2**. Town center decrements every product except
  FERTILIZER once per day (`townCenterSellInterval` = 24).

| shop | demands |
|---|---|
| BAKERY | EGG, WHEAT |
| PIZZA_SHOP | MILK, TOMATO, WHEAT |
| BRUNCH_SPOT | EGG, WHEAT, STRAWBERRY |
| YARN_STORE | WOOL (x2) |
| ICE_CREAM_SHOP | STRAWBERRY, MILK, WHEAT |
| PET_CAFE | CARROT (x2) |
| SMOOTHIE_SHOP | STRAWBERRY, MILK |
| FARMERS_MARKET | WHEAT, CARROT, TOMATO, STRAWBERRY |

P(zero demand across all 8 draws) = ((8 - supporting_shops)/8)^8:

| product | shops | P(zero demand) | E[drain/day] |
|---|---|---|---|
| WHEAT | 5 | 0.04% | 31 |
| STRAWBERRY | 4 | 0.39% | 25 |
| MILK | 3 | 2.33% | 19 |
| CARROT | 2 | 10.01% | 19 |
| TOMATO | 2 | 10.01% | 13 |
| EGG | 2 | 10.01% | 13 |
| WOOL | 1 | 34.36% | 13 |
| MELON | 0 | 100% | 1 |
| FERTILIZER | 0 | 100% | 0 |

### THE BIG ONE: shop draws are agent-dependent
`_end_of_day` builds one RNG: `rng = random.Random((seed * 1_000_003) ^ day)` (871). It
then calls `_spawn_weeds(farm, board_size, weed_chance, rng)` for **both farms** — which
calls `rng.random()` once per **empty** tile — *before* `rng.choice(sorted(SHOPS))`
(872-891). So how far the stream advances before each shop pick depends on tile occupancy
on both farms.

Verified empirically on seed 42: an all-PASS agent draws FARMERS_MARKET, PET_CAFE,
YARN_STORE, YARN_STORE, PET_CAFE, PET_CAFE, FARMERS_MARKET, ICE_CREAM_SHOP; `starter` on
the identical seed draws ICE_CREAM_SHOP x4, YARN_STORE, BAKERY, BRUNCH_SPOT,
FARMERS_MARKET. Six runs across two seeds produced six different shop sets.

Three consequences:
1. **Shops are steerable — CONFIRMED empirically, not just theoretically** (2026-08-23,
   `eval/shop_steering_probe.py`, see `eval/NOTES.md`). Swept planted-tile-count K (0-24)
   against a fixed opponent across 3 seeds: different K reliably produce different shops,
   deterministically, with real redundancy (multiple K values often hit the same target
   shop — e.g. seed 777, SMOOTHIE_SHOP at K in {11,20,21,22,23,24}). Real limitation: this
   requires knowing the opponent's occupancy contribution to the same RNG stream (self-play
   mirror or a known opponent tape both work; an unknown adaptive opponent only allows
   probabilistic, not precise, steering). **Still unexploited in the live agent, and a
   first attempt at an in-agent controller was inconclusive, not just "not yet built."**
   An additive-only wrapper (only redirect otherwise-idle unit actions into extra
   plantings, never displace a real decision) turned out to have zero room to operate —
   confirmed by direct instrumentation that the crop-crew units responsible for NW_WHEAT
   are continuously busy throughout days 0-2, never idle. See `eval/NOTES.md`
   ("First attempt at an in-agent controller") before retrying — a working version needs
   to accept displacing a real action (delay a water/plant by a turn), not just fill
   gaps, and that has not been attempted. The core question — does steering toward a
   deliberately-chosen shop improve self-play score end-to-end — remains untested.
2. **Cluster-matched seed benchmarking is invalid.** You cannot pick a seed to hit a target
   shop profile independent of the agent. Control the agent, or evaluate over seed
   *distributions*.
3. A benchmark number is meaningless without naming the opponent.

### Market / AMM
- `MARKET_I0 = 10000`, `PRICE_FLOOR = 1`. `_shape` at 61; price computation at 195-207:
  `amp = target * base / _shape(f, T, T)`, `price = base -/+ amp * _shape(f, |inv - I0|, T)`.
- Per-product glut penalty differs enormously (`MARKET_PARAMS`, 41-51 — corrected
  2026-08-24, was miscited as 126 since early in the project; 126 is a blank line between
  two unrelated helper functions). Realized average
  price when dumping N units from I0, computed from the engine's own `market_price`:

| product | base | T | above curve | above_target | avg@50 | avg@200 | spot@400 |
|---|---|---|---|---|---|---|---|
| WHEAT | 25 | 400 | log | 0.20 | 22.5 | 21.5 | 20.0 |
| CARROT | 35 | 450 | sqrt | 0.70 | 29.6 | 24.2 | 12.0 |
| TOMATO | 60 | 200 | sqrt | 0.60 | 48.2 | 36.1 | 9.0 |
| STRAWBERRY | 120 | 100 | linear | 1.60 | 73.0 | 19.7 | 1.0 |
| MELON | 250 | 300 | **sq** | **3.60** | 242.0 | 132.6 | 1.0 |
| EGG | 50 | 332 | log | 0.20 | 44.9 | 42.5 | 40.0 |
| MILK | 160 | 122 | linear | 1.60 | 108.6 | 31.5 | 1.0 |
| WOOL | 200 | 105 | **sq** | **3.20** | 153.1 | 40.3 | 1.0 |
| FERTILIZER | 100 | 200 | linear | 0.40 | 95.1 | 80.1 | 20.0 |

Below-curves matter too: CARROT is `hinge` with `below_target` **1.00**, so PET_CAFE (x2
carrot) can roughly double carrot price — the sharpest scarcity play available. Observed in
real data: carrot reached $91 from base $35.

- **The market executes unit by unit**, re-quoting at current inventory each unit
  (596-597), and **both players are interleaved one unit at a time** — the code comments
  "Both players see the same pre-commit inventory for this unit." Realized price therefore
  depends on the opponent's concurrent sells. This is the real front-running mechanic, and
  it means single-agent price paths overestimate revenue.
- `BUY_PRODUCT` quotes at `market_price(item, inventory - 1)`.
- WHEAT is the **keystone**: only product with ~0% zero-demand risk, highest drain
  (31/day), and log/0.20 glut curve so it never really gluts. Simultaneously the cheapest
  feed source and the most reliably sellable product. Real games show mean wheat ~$39.4,
  i.e. it trades *above* base.
- MELON is a trap: zero shop demand *and* the worst glut curve.
- FERTILIZER has **zero drain of any kind** (no shop, excluded from `TOWN_CENTER_PRODUCTS`),
  so its price only ever falls — and both players produce it simultaneously.

### Animals
`ANIMALS`: GOOSE $300 / COOP / first_yield_day 4 / interval 1 / max_held 4 / EGG.
COW $400 / PASTURE / day 8 / interval 2 / max_held 6 / MILK.
SHEEP $500 / PASTURE / day 6 / interval 3 / max_held 6 / WOOL.

- **Lifetime yields** (engine schedule `days_since_first = next_day - placed_day -
  first_yield_day`, yield when `>= 0 and % interval == 0`, next_day 1..30): placed day 0 →
  GOOSE 27, COW 12, SHEEP 9. Placed day 1 → 26, 11, 8.
- `FEED` consumes exactly **1 WHEAT per animal per day** (`_inv_take(inv,"WHEAT",1)`, 505).
  Animal **escapes** after 2 consecutive unfed days (`consecutive_unfed >= 2`, 821);
  structure remains.
- `CARE` is **once per day** (527-529), sets `cared_today`.
- **THE CARE BONUS — this is the single largest revenue mechanic.** (829-830):
  `if cared_today and fed_today: pending_care_bonus += 1`, every day. On a yield day
  (826-828): `bonus = pending_care_bonus` (only if `fed_today`), `yield_units += base +
  bonus` capped at `max_held`, then reset. Order matters: consume-then-increment.
  Steady state with daily feed+care:
  - **COW: 3 milk per yield** (1 + 2)
  - **SHEEP: 4 wool per yield** (1 + 3)
  - **GOOSE: 2 eggs per day** (1 + 1)
  Without CARE you get 1 unit per yield — a 2-4x revenue loss. This is currently the
  agent's biggest deficit (see §4).
- `fertilizer_available = True` is set **daily per animal** (831). Physical ceiling for 14
  animals over ~24 producing days is **~336 units** lifetime.
- `BUY_ANIMAL` deposits into `private["shed"]` (679-685) — animals must be PICKUP'd, walked
  to the target tile, and PLACE'd. **It returns False if
  `sum(private["shed"].values()) >= shed_capacity`, so a full shed silently blocks all
  animal purchases.** Guard this explicitly.

### Crops
- `consecutive_unwatered` initialises to **1 on the planting day** (222); a tile becomes a
  WEED at `>= 2` (783). So plants must be watered **essentially every day from planting**.
  Any scheme that waters only in a later window destroys the crop.
- Fertilizer bonus applies **only on watered days** (799).
- Wheat: seed $10, first yield day 2, max yield 4 unfertilized / 6 fertilized.
- Strawberry: seed $100, first yield day 10, every other day x4 yields (days 10,12,14,16),
  then decays to weed. Tomato: day 8, daily x4. Both are capped at 4 scheduled yields.
- Melon bonus window ages 6-12 but caps at age 10 (age 8 fertilized).

### Labour
- Nightly wipe: hands cleared, farmer returned to spawn, `hires_today` reset, inventories
  emptied. Hire cost is **Fibonacci, resets daily**, `FARM_HAND_COST_MULT = 1` (101).
- `_apply_unit_action` is identical for farmer (idx 0) and every hand (idx i+1) — hands can
  FEED/CARE/BUILD_PASTURE/BUILD_COOP/PICKUP/PLACE/DROP/COLLECT_FERTILIZER/HARVEST. The
  restricted `farmer_ops` list near the bottom of the file is only a sampling list for the
  reference `random_agent`, not a real restriction.
- Per-actor inventory indexing: `private["inventories"][0]` = farmer, `[i+1]` = `hands[i]`.
- Shed-access spawn tiles: (4,4), (5,4), (4,5), (5,5).

Cost of a flat crew across a 30-day season:

| hands/day | cost/day | cost/season | % of $87.6k |
|---|---|---|---|
| 5 | $12 | $360 | 0.4% |
| 9 (the meta) | $88 | $2,640 | 3.0% |
| 10 | $143 | $4,290 | 4.9% |
| 12 | $376 | $11,280 | 12.9% |
| 13 | $609 | $18,270 | 20.9% |
| 14 | $986 | $29,580 | 33.8% |

**Labour is NOT free to scale** — it is Fibonacci and compounds daily. The meta sits at
9.23 hands/day, almost exactly at the knee. **Dynamic crew sizing** (many hands on
harvest-heavy days, few on maintenance days) is the real lever: Gemini's solver estimated
$826-$2,191/season versus $11,280 flat. Aggregate replay data cannot reveal it, and nobody
appears to do it deliberately.

---

## 3. Verified empirical facts (official Kaggle public dataset)

Source: Kaggle Top Episodes Dataset, analyzed in-place in a Kaggle notebook (~20GB/day, so
never downloaded). Outputs in `results/`. All figures below were independently
re-verified by Claude from those CSVs.

- **N = 697 distinct episodes / 1,394 player trajectories.** Mean reward $88,666.7, median
  $87,592.0, p25 $69,787, p75 $105,557, min $26,555, max $170,964.
- The manifest's `top_avg_score` / `median_avg_score` columns are **agent rating (Elo), not
  money**. Do not ever conclude that real games end near $3,000.
- **Reference build 10C/4S/0G**, n = 527 (37.8% of all trajectories): mean **$88,109**,
  median $87,662, min **$26,958**, max $162,096.
- Portfolio distribution: 10C/4S/0G 527, 6C/12S 181, 8C/6S 110, 6C/8S 73, 9C/4S 58,
  6C/6S/2G 29, 11C/4S 18.
- **Median total animals = 14** (max 26) out of ~100 tiles. **82.5% never unlock SE.** The
  entire top meta plays sparse builds on three quadrants.
- Hires: day-0 median **5** (1,109 of 1,394 hire exactly 5); lifetime median **277**
  (~9.23 hands/day).
- Geese appear in **7.3%** of trajectories (102/1,394). Goose cohort: mean money $77,647
  vs $89,537 (worse) but **win rate 56.9% vs 49.1%** (better). Confounded — those builds
  *substitute* geese for cows (6/6/2 vs 10/4/0) rather than adding them. **The additive
  goose question is untested, not settled.** Since the ladder scores wins not margin, the
  win-rate signal is the one that matters.
- Demand-pressure clustering (K=15 on standardized 8-d vectors, 697 episodes): sizes min
  31 / median 46 / max 65. Reward spread across clusters **2.10x**
  (Cluster_00 $60,412.9 → Cluster_08 $127,156.2). Per-cluster reporting is mandatory; a
  single average across clusters is meaningless.
- Real 10C/4S/0G by cluster ranges $57,674 (cluster 0) to $128,050 (cluster 8) — a 2.22x
  spread.
- **Product sale medians for the reference build** (targets to steer by): wheat **856**,
  melon **72**, strawberry **286**, milk **279**, wool **139**.
- **Fertilizer caveat:** the extractor's `fert_sold` median of 2,750 is a **parsing
  artifact** — it summed `qty` from raw SELL orders without bounding by shed contents, so
  bots emitting `["SELL","FERTILIZER",100]` were credited with phantom units. The physical
  ceiling is ~336. The same artifact inflates the *means* of strawberry (7,945) and milk
  (7,877) while their medians (286/279) remain plausible. **Fix the extractor and re-derive
  all sale targets before steering by them.**
- Wheat and strawberry are how the meta funds itself: 856 wheat (~$33.7k) + 286 strawberry
  (~$41.6k) is the bulk of $88k, and both stay above base because season drain (930 and
  750) exceeds those volumes.

---

## 4. Current agent state — where you are picking up

`agent/dispatcher_agent.py` (`make_spatial_dispatcher_agent()`), a spatial task dispatcher.

**⚠ Everything in this section describes the build as of 2026-08-24. The version of this
section written 2026-08-22/23 (the $38,299 build, then the wheat/wool-collapse
investigation) is now history — see `agent/NOTES.md` §2g-2j for the full trail. Do not read
old copies of this section from memory; the numbers below are current.**

**Benchmark standard (established the hard way): pure self-play, `env.run([agent, agent])`.**
Report vs-all-PASS only as a clearly labelled diagnostic ceiling, never as the headline.

**Production Agent Integration Status (2026-08-24): COMPLETE & VERIFIED.**

Value-gated shop steering (`GAMMA_INTEGRATED`, `K_COST_CORRECTED = 208.74`, `STEERING_GAIN_THRESHOLD = 1000.0`) is **fully integrated directly into `agent/dispatcher_agent.py` (`MaestroFullPortfolioAgent`)**, and the entire `project_maestro/` tree is safely tracked and committed in git.

- **Standing Production Baseline (Fully Integrated)**:
  - **Official 20 Seeds (real `env.run()` / FastEngine $\Delta = \$0.00$)**: **$56,743.07** (+19.39% / +$9,216.95 over unsteered $47,526.12, SE $4,169.42, $t = +2.21$).
  - **100 Disjoint Seeds (`10000-10099`)**: **$62,293.33** (+20.36% / +$10,539.07 over unsteered $51,754.27, SE $1,539.94, $t = +6.84, p = 6.51 \times 10^{-10}$).
  - Head-to-Head win rate on steered seeds: **86.2%** (56W / 9L / 35T).

**Completed Verification & Architecture Milestones:**
1. **Dedicated-Courier Strawberry Fertilization (TESTED, DEFINITIVELY REJECTED, §2o)**:
   - Re-tested on top of the genuinely steered baseline (`eval/benchmark_steered_strawberry_courier.py`).
   - Official 20 Seeds: Baseline $56,743.07 $\rightarrow$ Courier $56,505.30 ($\Delta = -\$237.78, t = -0.33, 6\text{W}/14\text{L}$).
   - 100 Disjoint Seeds: Baseline $62,293.33 $\rightarrow$ Courier $62,440.11 ($\Delta = +\$146.77, t = +0.31, 14\text{W}/84\text{L}/2\text{T}$).
   - Economic mechanism confirmed: Consuming early fertilizer internally forfeits high-compounding capital for Day 4–12 livestock acquisition in exchange for late-game strawberries selling into depressed post-glut AMM curves.
2. **Per-Archetype Evaluation Suite (`eval/archetype_evaluation_harness.py`, §2p)**:
   - Evaluated production agent across 280 official `env.run()` matches spanning 7 archetypes.
   - Vs Standing Unsteered Mirror: $56,477.40 vs $57,298.07 ($\Delta = -\$820.67, t = -1.63, 40.0\%$ win rate, measuring the asymmetric public-good property of town shop unlocking).
   - Vs Starter Baseline: $72,565.07 vs $3,529.18 (100% win rate, $+69.0k margin).
   - Vs Random Baseline: $71,196.52 vs $19.25 (100% win rate, $+71.2k margin).
   - Vs Pass Baseline: $72,535.70 vs $3,000.00 (100% win rate, $+69.5k margin).

**⚠ CRITICAL CAVEAT ON THE STEERING RESULT (Claude, verification pass 2026-08-24) — read
before treating $56,743.07 as the agent's competitive strength.**

The archetype harness produced one result that is far more consequential than its placement
above suggests: **against an unsteered copy of itself, the steered production agent LOSES
head-to-head — 40.0% win rate (16/40), margin -$820.67.**

The mechanism Gemini identified is correct and important: **steering produces a public good.**
The steerer pays the full early-wheat displacement cost ($208.74/tile) to unlock a
high-demand shop, but that shop is a *shared* market sink — the opponent gets the same
price support for free while keeping all 10 NW wheat tiles. The free-rider profits more than
the payer. Note the opponent's $57,298.07 in that matchup exceeds **both** mirror baselines
($47,526.12 unsteered mirror, $56,743.07 steered mirror), which is exactly the free-rider
signature.

**Why this matters more than the mirror number:** this competition is an **Elo ladder**, and
§3 of this file already records the governing principle — "since the ladder scores wins not
margin, the win-rate signal is the one that matters." The +19.39% mirror gain was measured in
the one configuration where the public-good cost is symmetric and therefore invisible. Against
a ladder full of agents that do not steer, we would be paying to raise our opponents' scores.

**Statistical honesty:** -$820.67 with SE $504.29 (t=-1.63, p=0.11) and 16/40 wins are **not**
significant. The correct claim is *"steering shows no head-to-head advantage, with a negative
point estimate"* — not that it definitively loses. But it can no longer be described as the
project's biggest win without this qualifier.

**Systematic methodological consequence — this is the durable lesson.** Pure self-play mirror
benchmarking has a structural blind spot: **it cannot detect public-good / free-rider
asymmetries, because both seats make identical moves and so pay identical costs.** Any change
touching a *shared* resource (the AMM, the town shop sink, the shared weed/shop RNG) will look
better in mirror than it performs in real asymmetric play. Changes that are purely internal to
our own farm are unaffected.

Re-validation audit list (head-to-head vs an opponent NOT making the same change):
- **Shop steering (§2n)** — confirmed affected; see above.
- **Downward-only cow cap (§2d)** — suspect. We cut milk supply on weak-demand draws; an
  opponent who does not cut enjoys the firmer price we paid for. Same free-rider shape.
- **Curve-aware sell logic (§2a.2)** — suspect. We trickle GLUT_PRONE goods to protect price;
  an opponent who dumps sells into the price we protected.
- **Internal-only and therefore safe**: PLANT priority (§2h.4), strawberry dig+replant (§2j.2),
  day-29 crew scale-down (§2l), `crew_late` (§2i), the horizon fix (§2h.1).

**Full 7-Archetype Head-to-Head Matrix (all rows now complete):**

| Archetype | Prod Mean | Opp Mean | Δ | t | p | Win % |
|---|---|---|---|---|---|---|
| Unsteered Mirror | \$56,477.40 | \$57,298.07 | -\$820.67 | -1.63 | 0.111 | 40.0% |
| Dominant Meta (10C/4S/0G) | \$55,681.03 | \$58,225.85 | -\$2,544.82 | -1.57 | 0.126 | **30.0%** |
| Wool-Heavy (6C/12S/0G) | \$58,548.60 | \$52,188.32 | +\$6,360.27 | +2.95 | 0.005 | 67.5% |
| Balanced Pasture (6C/8S/0G) | \$58,554.85 | \$53,024.18 | +\$5,530.68 | +2.62 | 0.013 | 65.0% |
| Starter Baseline | \$72,565.07 | \$3,529.18 | +\$69,035.90 | +21.21 | <0.001 | 100.0% |
| Random Baseline | \$71,196.52 | \$19.25 | +\$71,177.27 | +22.00 | <0.001 | 100.0% |
| Pass Baseline | \$72,535.70 | \$3,000.00 | +\$69,535.70 | +21.99 | <0.001 | 100.0% |

**Dominant Meta** (10C/4S/0G) is 37.8% of real ladder trajectories. Against it, we lose (30.0% win rate). The mechanism is confirmed: the steerer opens a high-demand shop, the Dominant Meta opponent keeps 10 wheat plots and free-rides the sink. p=0.126 → the correct framing is *"no head-to-head advantage, with a negative point estimate"* — not that it definitively loses.

**Asymmetric Shared-Resource Validation (`eval/validate_shared_resource_features.py`, §2q):**
- Downward Cow Cap: Δ=-\$31.43, t=-0.07, p=0.94 on 100-seed suite. **No free-rider penalty — KEEP.**
- Curve-Aware Sell: Δ=+\$1,436.69, t=+1.85, p=0.066 on 100-seed suite. **Positive, borderline sig — KEEP.**

**Demand-Pressure Harness (`eval/shop_archetype_harness.py`, §2r):**
- Milk-Rich (\$61,888) vs Milk-Starved (\$32,624): \$29.3k spread — largest single demand driver.
- Wool-Dead (\$64,071) vs Wool-Active (\$49,221): \$14.8k gap from sheep capital drag.
- Overall self-play mean ~\$54,295 vs meta target \$88,109 → **\$33,814 gap** (~61% of target).

**⚠ OPEN QUESTION — STEERING KEEP/REMOVE/CONDITION:**

The Dominant Meta row (30.0% win rate, p=0.126) and the free-rider analysis make the keep/remove/condition question live. **This has not yet been decided.** Options:
1. **Keep as-is** — accept the free-rider cost; rely on winning against non-Dominant-Meta opponents for positive Elo.
2. **Remove steering** — revert to unsteered \$47,526.12 baseline; eliminates free-rider risk but loses the +\$9.2k mirror gain.
3. **Condition on opponent archetype detection** — steer only when the opponent is detected as non-Dominant-Meta (e.g. via Day-3 wheat tile observation). Complex; requires co-design validation.

**Target: \$80–90k in self-play — currently ~66–70% of target (up from ~48% two days ago).**

**Next Priority Milestones:**
1. **⚠ Decision Required**: Keep / Remove / Condition steering, given 30.0% win rate against Dominant Meta (37.8% of real ladder trajectories). Await user judgment.
2. **Multi-Shop Steering Extension (Days 6–24)**: Generalize value-gated steering to later 3-day draw windows using post-Day-3 farm occupancy states — **blocked pending steering decision**.
3. **Phase 0 Dataset Extractor Re-run on Kaggle Cloud**: Execute corrected bounded-SELL extractor on the full 20GB `/kaggle/input/` dataset to update meta sales targets. Must run in a Kaggle notebook kernel — local execution invalid.
4. **Demand-Pressure Cell Expansion**: Increase per-cell sample from ~30 to ≥100 for significance on the milk/wool regime gap; prioritize milk-regime-aware portfolio switching.

---

## 5. Infrastructure status

- **`engine/fast_engine.py`: PASS.** 20/20 exact match vs the reference engine, Δ = $0.00,
  ~14.3x speedup, ~6,200 steps/sec. Claude independently reproduced this. Run it as
  `PYTHONPATH=C:/Coding python project_maestro/engine/validate_fast_engine.py` (there are no
  `__init__.py` files; it relies on namespace packages, so the repo root must be on the path).
- `data/phase0_analysis.py` — Kaggle-notebook dataset analysis. **Phase 0: conditional
  pass.** Known bug: unbounded SELL quantity summation (see §3 fertilizer caveat).
- `oracle/price_model.py` — **Phase 1: signed off.** Price model reproduces the engine's
  `market_price` exactly on all 27 checked values.
- `solver/portfolio_optimizer.py` — **Phase 2: rejected twice.** See §6.
- `results/` — committed summary tables only.

---

## 6. Closed doors — do not re-attempt these

- **The analytical valuation model.** It was recalibrated twice; each time the error
  *moved* rather than shrank (first understating the reference build by 4.4x, then
  overshooting the previously-correct clusters by +32% while still being -39% on
  Cluster_03). Max error 39%, mean 16.6%. That pattern indicates the model class is wrong,
  not its parameters. Superseded by the fast engine — evaluate portfolios by simulation.
- **The Phase 2 coverage table as delivered.** Its claimed edges (+98.6% to +178.3%, then
  +39.5% to +165.9%) correlated **+0.918** with per-cluster reference understatement — the
  "edge" was largely the calibration error measured twice. Recomputed against real data the
  mean edge was +41.7%, and the largest claimed edge (Cluster_03, +165.9%) was actually
  **-10.9%**, i.e. worse than ordinary real bots. Regenerate from real simulation only.
- **Tapes.** A tape is one point in the shop space.
- **The old `C:/Coding` replay folders as a benchmark.** Mixed bag; excluded.
- **all-PASS or `starter` as the headline benchmark opponent.** `starter` finishes at
  ~$3,482 from a $3,000 start; all-PASS competes for nothing. Self-play is the standard.
- **Cluster-matched seed benchmarking.** Invalid — shop draws depend on the agents (§2).
- **Inventing pass thresholds after seeing results.** If a gate cannot be met, say so.

---

## 7. File layout and hygiene — enforced

    data/     Phase 0 dataset analysis
    engine/   fast engine + equivalence tests
    oracle/   Phase 1 price model
    solver/   Phase 2 portfolio search
    rl/       Phase 3 training
    agent/    Phase 4 agent + submission packaging
    eval/     shared evaluation harness, archetype definitions, seed sets
    results/  committed summary tables (CSV/JSON only)
    scratch/  ALL temporary files: debug scripts, logs, partial runs, one-off probes

1. Anything temporary goes in `scratch/`. Nothing temporary anywhere else. A previous round
   left 12 probe files (`diff_tiles_146.py`, `inspect_step_146.py`, `probe_match.py`,
   `trace_agent.py`, …) in `engine/` and `agent/`; `cleanup.py` then correctly reported "0
   transient items" because they were in the wrong place. That is the exact sprawl pattern
   that buried the previous effort.
2. Run `python cleanup.py` at session end.
3. `results/` holds only small summary tables. No raw replays, no per-step dumps.
4. One canonical file per job. Delete superseded files in the same change — no
   `_v2`/`_old`/`_backup`.
5. Every phase dir keeps `NOTES.md`: what was tried, the numbers, what was rejected and
   why, so a failed experiment is never silently re-run.

---

## 8. Corrections Claude has made to its own claims

Recorded so they are not inherited as fact:

- Claimed `fert_sold` target was 2,750 and the gap was larger than reported. **Wrong** — it
  is a parsing artifact; physical max is ~336 and the original ~300 estimate was about right.
- Derived shop draws from the seed alone. **Wrong** — the RNG is shared with weed spawning
  across both farms, so draws are gameplay-dependent.
- Claimed the meta runs ~6 hands/day and that 10-12 was a large free lever. **Wrong** — it
  runs 9.23, and Fibonacci cost makes 12 hands a 12.9% tax.
- Claimed a `TypeError` bug in a prior agent from `obs.get("step", 0)` returning `None`.
  **Wrong** — `env.run()` syncs `step` for both seats.
- Reported a 66% win rate for a prior agent against "real opponents". **Wrong twice** — the
  run was still in progress, and the corpus was a mixed bag of our own old agents.
- Suspected the solver's per-cluster ratios were a separable closed form. **Wrong** — they
  varied legitimately by cluster.
- Suspected differing shop lists for one seed were an inconsistency. **Wrong** — explained
  by the agent-dependent RNG above.
