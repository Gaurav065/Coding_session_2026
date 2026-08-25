# Project Maestro — Self-Repair Protocol & 2-Day Autonomous Plan

**Authority: this file + the engine source. Everything else — NOTES.md prose, HANDOVER.md
prose, prior chat — is a claim to be re-verified, not evidence.**

Written 2026-08-25. Last session, ten distinct classes of error were caught only because a
second party independently checked every number. That reviewer is now largely unavailable.
This file replaces that function: it encodes what went wrong, how to detect it
automatically, and what to do next. **Re-read PART 1-3 before every experiment.**

---

# PART 1 — GROUND TRUTH (never re-derive from memory, never guess a line number)

Engine path:
`C:/Users/GauravPatel/AppData/Local/Programs/Python/Python313/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py`

Every reference below was read directly from that file and confirmed. **If you need a line
number that is not on this list, open the file and read it. Do not infer it.** Six wrong
citations were issued last session (126, 590, 619, 734, 750-775, and a repeat) — every one
was a guess that "looked right".

| Mechanic | Line(s) | Content |
|---|---|---|
| `MARKET_PARAMS` (base/T/curves) | **41-51** | STRAWBERRY at 45, MILK at 48 |
| `SHOPS` (shop to products) | **103-111** | 8 shops |
| `MAX_SHOP_INSTANCES = 8` | 118 | |
| `FERTILIZE` op | **475-482** | sets `fertilized_until_day = day+2` |
| `_process_market` | 544 | |
| Order cap `maxMarketOrdersPerTurn` | **551**, **560** | default 10; `q[:max_orders]` |
| `BUY_PRODUCT` shed-full check | **667-668** | returns False |
| `BUY_ANIMAL` + shed-full check | **679-687**, check **682-683** | returns False silently |
| `_town_consume` | **728-747** | shop drain every 4 steps; town centre every 24 |
| Missed watering to WEED | **783-784** | `consecutive_unwatered >= 2` |
| Fertilised yield doubling | **799-800** | requires `was_watered` |
| Crop expiry `max_lifespan_step` | **801-802** | |
| `_drop_inventories_to_shed` | **843** | auto-deposit; overflow silently discarded |
| `_end_of_day` | **862-891** | |
| Daily RNG | **871** | `Random((seed * 1_000_003) ^ day)` |
| `_spawn_weeds` (one `rng.random()` per EMPTY tile, BOTH farms) | **877** | runs before the shop draw |
| Nightly wipe; **hands deleted** | **878-882**; `farm["hands"] = []` at **880** | |
| Shop draw | **891** | `rng.choice(sorted(SHOPS))` |
| Episode DONE / reward | **960-963** | `step >= episodeSteps - 2`; reward = final money |

## Facts that have already cost real work — do not rediscover them

1. **The agent never receives the seed.** Verified: `OBS KEYS = [day, farms, hour, market,
   player, private, remainingOverageTime, step, town]`. The seed exists only in `env.info`.
   Any strategy requiring it is unshippable. **Never inject `seed=` into an agent in a
   benchmark and report the result as production performance.**
2. **Only 719 actions are ever taken** (DONE fires at `episodeSteps - 2`). `EPISODE_STEPS = 719`.
3. **Hands are deleted every night** and respawn on shed-access tiles. Workers always begin
   the day at the shed; there is no carry-position-overnight optimisation.
4. **Inventories auto-flush to the shed at midnight from anywhere on the board.** Walking to
   the shed only buys same-day selling.
5. **FERTILIZER has zero drain of any kind** — no shop demands it and it is excluded from
   `TOWN_CENTER_PRODUCTS`. Its price only ever falls. No sell-timing strategy rescues it.
6. **Shop draws depend on both farms' tile occupancy**, so shop-matched seed selection is invalid.

## Physical ceilings — assert on any extracted or reported volume

A number violating these is a bug, not a discovery. Compute and check; do not eyeball.

```
FERTILIZER_sold <= n_animals * producing_days        # ~358 for 14.9 animals over 24 days
MILK_sold       <= n_cows  * 12 * (1 + care_bonus)   # cow: first yield d8, interval 2 => <=12 yields; CARE => 3/yield
WOOL_sold       <= n_sheep *  9 * (1 + care_bonus)   # sheep: first yield d6, interval 3 => <=9 yields; CARE => 4/yield
EGG_sold        <= n_geese * 27 * (1 + care_bonus)   # goose: first yield d4, interval 1 => <=27 yields; CARE => 2/day
WHEAT_sold      <= wheat_seeds * (6 if fertilised else 4) + wheat_bought - wheat_fed
STRAWBERRY_sold <= strawberry_plants * 4 * (2 if fertilised else 1)
units_from_one_order <= that order's requested quantity   # <-- fixes the fertilizer 755/1538 artifact
```

## Realization ceiling

`price = base + (target*base/shape(T,T)) * shape(|inv - I0|, T)`. Under realistic town-drain
volumes, per-product realization tops out near **1.5x-1.9x base**. **A basket-average
realization above ~1.9x is impossible** and indicates an extraction error, not a strategy
insight. (The reported meta figure of 2.44x is such an error.)

---

# PART 2 — SELF-REPAIR: THE SIX CANARIES

**Every harness producing a number you will report must run canaries 1-2 and 6 first** — prototypes
and one-off scripts included. All three seat-construction bugs last session were in scripts
that skipped them.

| # | Canary | Required result | Detects |
|---|---|---|---|
| 1 | Production agent vs `pass` | Opponent **exactly $3,000.00**, WR **100.0%** | seat mis-construction, opponent substitution, mis-aggregation |
| 2 | Identical params both seats | WR **50.0%**, Delta **$0.00** | seat asymmetry, param leaking into the opponent |
| 3 | `validate_fast_engine.py` | 20/20 exact, Delta **$0.00** | fast-engine drift (has drifted silently once) |
| 4 | Agent built with **no** `seed=` | Runs; steering stays inert | harness-only results posing as production |
| 5 | Physical-ceiling assertions (PART 1) | No violations | extraction / attribution inflation |
| 6 | Archetype execution floor | Every opponent **scores > $20,000** in control run | broken opponent replay/agent, all-pass fallthrough, harness failure |

**If a canary fails, stop.** Fix the harness before interpreting anything from it. A number
from a harness with a failing canary is not data.

## The ten failure modes, each with its detection rule

All ten occurred last session. Each is a check to run, not advice to remember.

1. **Guessed line citation** — open the file and read the line before citing it.
2. **Seat-construction bug** — canaries 1-2.
3. **Tautological validation** — if the quantity you are checking was *derived* from the
   quantity you are checking it against, the check cannot fail. Ask: **what input would make
   this test report failure?** If none exists, the test is worthless. (Defining revenue as
   `delta_money + costs` makes `start + revenue - costs = reward` an identity.)
4. **Physically impossible value accepted** — canary 5.
5. **Wrong decision metric** — see PART 3. Win rate decides, never self-play mean alone.
6. **Comparing different n** — both arms must use the same seed set and the same n. Never
   compare an n=40 arm against an n=200 arm.
7. **Stale or wrong baseline** — state the baseline's exact value AND which build produced
   it. If it differs from the standing baseline, explain why before proceeding.
8. **Dead code after rejection** — a rejected feature is deleted, not disabled by a flag
   (§2f precedent). `grep` the parameter name; expect zero hits outside NOTES.md.
9. **Harness-only capability reported as production** — canary 4.
10. **Overclaiming** — "definitively rejected" needs a powered negative, not p=0.65.
    "Pareto optimum" needs no other option dominating on any criterion. When unsure, write
    the weaker claim.

## Reporting template — use verbatim for every experiment

```
EXPERIMENT: <id> <one-line description>
SINGLE VARIABLE CHANGED: <exactly one thing>
BASELINE: $<value> (<which build>, <which seed set>, n=<N>)
CANARIES: 1 PASS/FAIL  2 PASS/FAIL  3 PASS/FAIL  4 PASS/FAIL  5 PASS/FAIL  6 PASS/FAIL
RESULTS (same seed set, same n, both seats):
  self-play mean  : $X (baseline $Y, delta $Z)
  self-play floor : $X (baseline $Y, delta $Z)
  H2H vs Dominant Meta : WR%, delta $, t, p, W/L/T     <-- DECIDING METRIC
CEILING CHECK: all volumes within PART 1 limits? YES/NO
VERDICT: ADOPT / REJECT / INCONCLUSIVE   (per PART 3)
FALSIFIER: what result would have made me reject this? <must be answerable>
```

---

# PART 3 — DECISION RULE (this was got wrong four times)

This competition is an **Elo ladder scored on match outcomes, not money margin.**

**Primary metric: head-to-head win rate vs Dominant Meta (10C/4S/0G), n=200, both seats.**
Dominant Meta is 37.8% of real ladder trajectories.

**Secondary tie-breakers, in order: Disjoint-100 p5 floor, then Disjoint-100 self-play mean.**

**Self-play mean alone NEVER decides an adoption.** It is structurally blind to free-rider
and public-good effects, because both seats make identical moves and pay identical costs.

Adoption requires **all** of:
- H2H vs Dominant Meta improves, or is unchanged within noise while a secondary improves
- Disjoint-100 **p5** does not regress more than 5%  ← see methodology note below
- All five canaries pass
- Exactly one variable changed
- The FALSIFIER line is answerable

If primary and secondary disagree, **run the two candidates directly head-to-head.** That
settles it without relying on either proxy (this resolved Cand1-vs-Cand2 correctly).

**Floor gate methodology (corrected 2026-08-25, not retroactive):**
The original gate used `min` over 100 seeds — the noisiest possible estimator of tail risk.
During the NW+3b investigation, the gate correctly stopped and sent the run to investigation,
but the breach was 2 seeds out of 100 sharing a pre-existing adverse-draw vulnerability
(no-milk-shop draw; also present in the baseline). The p5 for NW+3b *improved* by +5.7%
while the min fell by 11%. Min is retained as an **investigation trigger** (it correctly
fired and pointed to the right place), but **p5 is the adoption criterion** — it is a
stable estimator of tail risk that is not dominated by a single outlier. Document any
min-gate trigger with: seed IDs, scores, shop draws, and whether the cause pre-exists
in the baseline.

---

# PART 4 — WHERE WE STAND (2026-08-25)

**Standing baseline: $51,042.55 (Official 20) / $57,002.58 (Disjoint 100).**
Floor $33,376 / $32,123. vs Dominant Meta 88.0%. Target $80-90k. Real meta $91,603.

**The central diagnosis (§3c) is trustworthy** — measured on our own agent in our own engine,
no extractor in the path:

| product | units/game | realized | ratio | status |
|---|---|---|---|---|
| WHEAT | 1213.0 | $37.08 | **1.48x** | healthy |
| STRAWBERRY | 81.6 | $190.88 | **1.59x** | healthy |
| CARROT | 67.1 | $63.83 | **1.82x** | healthy |
| WOOL | 23.0 | $207.09 | 1.04x | neutral |
| MELON | 33.6 | $259.22 | 1.04x | neutral |
| **MILK** | **196.9** | **$98.24** | **0.61x** | **broken** |
| **FERTILIZER** | **174.7** | **$59.57** | **0.60x** | **broken** |

We are **not** volume-constrained — we meet or exceed meta volume on five of six products.
We are **realization**-constrained, and the loss sits in exactly two products.

**Correct framing is overproduction, not timing.** Meta sells 50.5 milk; we sell 196.9.
Selling 196.9 units *is what crushes the price* — marginal units are worth ~$1 whenever sold.
FERTILIZER has zero drain (PART 1 fact 5), so no schedule can rescue it.

**Open defect:** the Phase 0 extractor still inflates units by dividing cash by a floor price
(fertilizer 755 / 1538 against a ~358 ceiling). Meta targets are untrustworthy until fixed.

---

# PART 5 — TWO-DAY PLAN

Work blocks in order. Do not start the next block until the current gate is answered YES, or
the block is explicitly recorded as failed in NOTES.md. Commit after every block. Use the
PART 2 template for every experiment.

## BLOCK 1 (blocking, do first) — Fix the extractor

**Why:** every meta comparison depends on it, and it currently reports impossible values.

1. Bound each SELL order by its own requested quantity:
   `units = min(cash_attributed / unit_price, requested_qty)`. This makes 755 and 1538
   structurally impossible.
2. Add the PART 1 physical-ceiling assertions; log violating episodes rather than silently
   including them.
3. Re-run the 10 validation episodes. **Replace the tautological check**: assert each
   product's units fall within its physical ceiling, and report the pass fraction.
4. Re-run the full 697-episode corpus on Kaggle Cloud.

**GATE 1:** zero episodes violate a physical ceiling AND the meta basket realization lands in
**1.2x-1.9x**. Outside that band means the extractor is still wrong — fix before proceeding.
Publish the corrected meta targets table.

## BLOCK 2 — Cow cap ladder (primary hypothesis: overproduction)

**Why:** we sell 196.9 milk at 0.61x; meta sells 50.5. We run `cow_cap_base=10`, meta 8.3.

Single-variable ladder: `cow_cap_base` in **{10 (control), 9, 8, 7, 6}**, everything else fixed.
Per arm: self-play Official-20 + Disjoint-100, H2H vs Dominant Meta n=200. Also record
realized milk price and milk units sold per arm.

**GATE 2:** report the full ladder even if every arm loses. Expect an interior optimum — if
milk realization rises as cows fall while total revenue holds, the thesis is confirmed.
Adopt per PART 3. If the control wins, record the thesis as refuted and say so plainly.

## BLOCK 3 — Fertilizer: is collecting it even worth the action?

**Why:** 0.60x realization, zero drain, price only falls. `COLLECT_FERTILIZER` consumes a
crew action that could water or harvest instead.

Three arms, one variable each, against the Block-2 winner:
- **3a** control (current behaviour)
- **3b** never `COLLECT_FERTILIZER` at all — free those crew actions entirely
- **3c** collect, but sell 100% on the earliest possible turn each day (price only falls, so
  earliest is optimal by construction)

**GATE 3:** adopt per PART 3. **3b is the interesting arm**: if freeing the crew actions beats
the fertilizer revenue, that is a large structural win and it also relieves shed pressure.

## BLOCK 4 — Milk sell scheduling (only if Block 2 did not resolve it)

**Why:** separate *how much we make* from *when we sell it*.

Against the Block-2/3 winner, sell milk only in turns immediately after a `_town_consume`
shop-drain tick (every 4 steps, engine:728-747) versus current behaviour. Sweep the
per-batch cap over {2, 4, 8, unlimited}.

**GATE 4:** adopt per PART 3. If Block 2 already fixed milk realization by producing less,
record timing as secondary and move on — do not force a win here.

## BLOCK 5 — Consolidation and regression sweep

1. Re-run the **full archetype matrix** (Dominant Meta, Wool-Heavy, Balanced Pasture, Old
   Baseline, Pass) at n=200 with all five canaries.
2. Re-run `validate_fast_engine.py`.
3. Confirm **no dead parameters** remain from any rejected arm (`grep` each name).
4. Update `HANDOVER.md` §4 and `NOTES.md` with the new standing baseline and every rejected
   arm, with numbers and mechanism.
5. Verify the agent runs with **no `seed=` argument** (canary 4) and emits a valid
   submission-shaped action dict on every step.

**GATE 5:** all canaries pass; standing baseline restated with build, seed set and n.

## If you finish early, or a block fails outright

Do **not** invent new directions. In priority order:
- Re-run any adopted change on a **fresh disjoint seed set** (e.g. 20000-20099) to confirm it
  was not an overfit. Two apparent wins have already died this way.
- Strawberry is at 1.59x and healthy — test one more NE conversion step only if Block 2 freed
  pasture tiles.
- Re-examine melon (33.6 units, 1.04x, zero shop demand) for removal on the same
  overproduction logic as milk.

## Standing prohibitions — tested and rejected, do not retry

Shop steering (requires the seed; unshippable) · geese (`goose_cap=0` is final) · sheep/wool
expansion (§2e, §2x) · melon expansion (§2x) · SE quadrant (§2f) · NE/SW tile pruning (§3a) ·
crew above 10 (§2h, order cap) · same-crew fertilizer courier (§2c, §2j, §2o) · tapes · old
`C:/Coding` replay folders as evidence · all-PASS or `starter` as a headline opponent.
