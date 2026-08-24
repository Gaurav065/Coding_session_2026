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

**⚠ READ THIS BEFORE QUOTING ANY BASELINE NUMBER (added 2026-08-24, after verification).**

**The production agent `agent/dispatcher_agent.py` contains NO shop-steering code.** Verified
directly: zero matches for `steer` / `target_shop` / the gamma table / `208.74` in that file.
Every steering implementation lives in `scratch/` — which `cleanup.py` deletes at session end
per the hygiene rules in §7. So:

- **$56,743.07 is a scratch-harness result, not the shippable agent's score.** It was produced
  by test wrappers in `scratch/`, subclassing the production agent from outside.
- **The production agent — the thing that would actually be submitted — is still at
  ~$47,526.12**, the pre-steering level.
- The whole `project_maestro/` tree is also still **untracked in git** (`?? project_maestro/`),
  so the steering work currently exists in exactly one place: a directory designed to be wiped.

**Highest-priority action, ahead of everything else: integrate the value-gated steering
controller into `agent/dispatcher_agent.py`, then re-verify $56,743.07 against the real
production agent via `env.run()`.** Until that is done, treat the deliverable's true baseline
as ~$47,526.12 and every §2n number as provisional.

**Current baselines, stated precisely:**
- Production agent, no steering: **$47,526.12** (official 20 seeds, real `env.run()`).
- Scratch harness with value-gated steering ($208.74/tile, integrated gamma): **$56,743.07**
  (official 20), **$62,293.33** (100 disjoint). Statistically strong (t=6.84, p=6.5e-10 on the
  disjoint set) and independently arithmetic-checked, but **not in the deliverable**.

**Target: $80-90k in self-play — currently ~66-70% of target (up from ~48% two days ago).**

**Biggest single win of the project so far: value-gated day-3 shop steering (§2n, 2026-08-24).**
The weed-spawn/shop-draw RNG mechanism (`kaggriculture.py:862-891` — RNG seeded at 871,
`rng.choice(sorted(SHOPS))` at 891) is steerable via controlled tile occupancy on days 0-2,
and the value of doing so was quantified with a proper two-way fixed-effects regression
(controlling for the tiles-planted confound, `K`) rather than a naive mean comparison —
SMOOTHIE_SHOP/ICE_CREAM_SHOP/FARMERS_MARKET/PIZZA_SHOP all beat BAKERY by $3.8k-$5.2k at
matched K (p≤0.034). The deployed controller only redirects planting toward a target shop
when the computed expected gain exceeds $1,000, otherwise leaves the natural opening alone
(verified as an exact no-op on non-triggered seeds). Result: $47,526.12 → $57,908.97 on the
official 20 seeds (+21.85%), independently confirmed on 100 disjoint seeds (mean
+$10,276.69, paired t=6.69, p=1.33×10⁻⁹, floor $24,083→$31,098.50). This is real and
strongly validated — but note per-seed "expected gain" is a weak individual predictor given
~$10-14k per-shop standard deviations (some steered seeds lost $16-18k despite a positive
point estimate); only the aggregate is trustworthy at the seed level.

**Open, blocking one small follow-up test before this is fully closed out**: the cost model
has been re-derived properly (2026-08-24) under the corrected integrated-dispatcher
methodology — true cost is **+$208.74/tile** (SE $112.22, p=0.063), not the $30/tile the
*deployed* policy actually used to produce the $57,908.97 result. $208.74 is ~7x *higher*
than what was deployed (the "$2,087.40 not $4,200" framing in `agent/NOTES.md` §2n compares
against the old, separately-wrong $420.72 estimate — it does not validate the $30 that was
actually run). **The $57,908.97 result was measured with the $30/tile version. The
corrected $208.74/tile version has not been benchmarked.** Re-run the same 20-seed and
100-seed tests with `$208.74` substituted for `$30` in the gain formula before treating this
line of work as finished — displacement is now understood to be pricier, so fewer seeds
will likely clear the $1,000 gate; confirm whether the result holds, improves, or changes
materially, and update §2n so it's unambiguous which cost model produced which reported
number (right now the write-up could be misread as $208.74 having produced $57,908.97).

Since the $38,299 build, in order: fixed the fabricated `BASE_PRICES`/sell-curve/goose-gate
bugs (2a); accepted a downward-only shop-conditioned cow cap (2d, `cow_cap_low=6`); found
and fixed a systemic fast-engine horizon bug present in 8 files (`EPISODE_STEPS` off-by-one
— real engine fires DONE at `episodeSteps-2`, so only 719 actions are ever taken, not 720;
fixed structurally via a `game.done` property, not a patch); rejected an unnested-sheep
candidate and a HIRE-order-splitting candidate (both real, well-understood negative results
— see `agent/NOTES.md` §2h); made `crew_late` explicit at 10 instead of relying on the
engine's own `maxMarketOrdersPerTurn=10` cap to silently enforce it (§2i); independently
validated `cow_cap_low=8` on 100 seeds disjoint from the official 20 and correctly rejected
it as an overfit, keeping `cow_cap_low=6` (§2j.1); and accepted an expired-strawberry-plot
dig+carrot-replant fix (§2j.2, +3.13%). A second strawberry-fertilization attempt (NE crew
self-fetching fertilizer) was rejected for the exact reason `agent/NOTES.md` 2c already
predicted (crew-reuse opportunity cost) — **do not attempt a third self-fetch design; if
strawberry fertilization is revisited, it needs the dedicated-courier role 2c specified, not
another variant of the crew doing double duty.**

CARE bonus is confirmed already active (78-87% same-day fed+cared hit rate) — no action
needed there. Fast-engine/real-engine equivalence is fixed and reconfirmed exact (20/20,
Δ=$0.00) on the corrected 719-step horizon; treat any *new* fast-engine result with the same
skepticism until it's been checked once more, since this has now drifted silently once
already.

**Shed-full animal-purchase guard**: investigated and closed — the scenario is real (~4-8%
of purchase checkpoints hit shed≥90) but the correct guard is just the outer bound the code
already had (`shed_total_items <= 90`); no score change, see §2k.

**Next candidates, not yet attempted, roughly in priority order**:
1. Re-derive the shop-steering controller's per-tile cost under the corrected methodology
   (see "open, not blocking" above) — cheap, and firms up the $1,000 gate threshold.
2. Extend value-gated steering to the later shop draws (days 6-24) — day-3 alone was the
   proven case; the same mechanism and value-table approach should generalize, but each
   later draw's occupancy baseline is different and needs its own reachability sweep.
3. Dedicated-courier strawberry fertilization (the redesign 2c/§2j.3 both said was needed,
   not another same-crew variant) or dynamic crew sizing beyond the day-29 case already
   banked (§2l) — both flagged as "high-certainty agronomic" work by the same investigation
   that found the steering win.

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
