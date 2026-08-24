# Agent Implementation & Empirical Telemetry Notes - Project Maestro

## 1. Governance & Evaluation Standard

- **Opponent Standard**: All headline performance metrics are measured in **Pure Self-Play (`env.run([agent, agent])`)**.
- Diagnostic ceilings against `all-PASS` and `starter` are reported only as reference ceilings and clearly labeled.
- **Fast-Engine Invariant**: Verified bit-for-bit equivalence against real `kaggle_environments` with **$\Delta = \$0.00$** in Self-Play.

---

## 2. 20-Seed Empirical Self-Play Benchmark Progression

| Stage / Iteration | Self-Play Mean (P0 / P1) | Wheat Sold | Melon Sold | Strawberries Sold | Milk Sold | Wool Sold | Fert Sold |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Initial Dispatcher** | \$18,450 / \$18,120 | 410.2 | 0.0 | 0.0 | 85.0 | 12.0 | 35.0 |
| **Pure Cash Gated** | \$27,927 / \$27,548 | 727.6 | 22.9 | 42.7 | 97.7 | 41.2 | 138.2 |
| **Peikopon Canonical Build** | **\$38,299 / \$38,402** | **928.9** | **56.9** | **52.0** | **97.5** | **54.0** | **154.5** |
| CARE bonus lock (via Nemotron) | \$40,695.85 (single-agent ceiling only, mislabeled) | — | — | — | — | — | — |
| CARE lock, correctly labeled self-play | \$39,570.95 / \$39,706.05 | — | — | — | — | — | — |
| **Sell-logic + price-table + goose-gate fixes (Claude, this entry)** | **\$41,053.20 / \$42,221.75** (final, incl. endgame liquidation) | — | — | — | — | — | — |
| **Downward-only shop-conditioned cow cap (Claude, accepted, see 2d)** | **\$41,675.45 / \$42,158.60** | — | — | — | — | — | — |
| **Canonical Meta Target ($n=527$)** | **\$88,109.11** | **856.0** | **72.0** | **286.0** | **279.0** | **139.0** | **300.0** |

*(Note: Diagnostic ceiling vs All-PASS for Peikopon build is \$58,372).*

### 2a. Bug fixes applied directly by Claude (Gemini out of context, Nemotron handed off)

Verified against real `env.run()` self-play, 20 fixed seeds, before/after. Net effect
**+4.6% mean** ($39,837 -> $41,681), but **not uniform** — seed 888's asymmetric P1
collapse ($9,649 -> $33,929) is fixed, while three previously-strong seeds (250, 300, 333)
regressed. All three fixes were bundled in one pass (violates one-variable-at-a-time; flag
for future isolation if the mixed result needs explaining further), but each is an
unambiguous bug fix, not a tunable strategy change:

1. **`BASE_PRICES` in `dispatcher_agent.py` was fabricated on 7 of 8 products** (WHEAT $35
   vs real $25, MILK $48 vs real $160, MELON $130 vs real $250, WOOL $58 vs real $200,
   FERTILIZER $15 vs real $100, CARROT $65 vs real $35, EGG $35 vs real $50 — checked
   against engine `MARKET_PARAMS` directly). This table drove the live sell-threshold
   decision (`if cur_price >= base_price * 0.8: dump else trickle`), so the agent was
   dumping steep-glut-curve products (MILK/WOOL/MELON/STRAWBERRY, above_target 1.6-3.6)
   whenever price cleared a threshold far below their real value — the exact mechanism
   behind the ~50% mirror-match contention loss measured earlier. Replaced with real
   `MARKET_PARAMS` base prices and `above_target` values, with a citation comment.
2. **Sell logic rewritten to be curve-aware**: FERTILIZER has zero drain of any kind (no
   shop demands it; excluded from `TOWN_CENTER_PRODUCTS`) so price never recovers — sell
   it immediately, always. GLUT_RESISTANT (WHEAT, EGG; above_target 0.20) sell freely.
   GLUT_PRONE (STRAWBERRY, MILK, WOOL, MELON; above_target >= 1.6) trickle in small
   batches (4/tick) gated on `price_ratio >= 0.55`, unless the shed is near its 100-unit
   overflow cap. Moderate curve (CARROT, TOMATO) trickle at a looser threshold.
   **Endgame override added after diagnosing a regression**: on day >= 28 sell
   everything regardless of price — instrumentation showed 60 units of MILK (~$9.6k)
   trapped unsold in the shed at game end on seed 20 before this was added.
3. **Goose purchase was gated on `not has_yarn_store`** — a wool signal with zero relevance
   to eggs, almost certainly a copy-paste leftover from the adjacent sheep condition.
   Removed; geese are additive and unconditional (cap unchanged at 4, since the additive-
   vs-substitutive question is still untested and shouldn't be conflated with this fix).

**Root cause identified for seed 20's regression, not yet fixed**: instrumented final shed
at game end — 60 MILK units unsold pre-fix, only 12 post-fix after the endgame-liquidation
override, but reward barely moved ($21,129 -> $21,197, and the full 20-seed mean moved by
only -$44, noise) because the 48 units that did sell were already crashed near the floor.
Kept the endgame override anyway — it is correct in principle (never leave positive-value
inventory unsold at game end) even though it happened not to matter on this seed; it may
matter on others where trapped inventory still has real value.

### 2b. Shop-conditioned cow herd sizing — TESTED, REJECTED, DO NOT RETRY NAIVELY

Mirrored the sheep pattern (`has_yarn_store` gates sheep expansion) onto cows: graded cap
of 6 / 10 / 14 based on the count of unlocked milk-demanding shops (PIZZA_SHOP,
ICE_CREAM_SHOP, SMOOTHIE_SHOP) observed by day 18 (5 of 8 shop draws have landed by then,
so not zero-information). Isolated test, 20-seed self-play, against the $41,637 baseline.

**Result: net regression, -4.8% ($41,637 -> $39,625).** Reverted; code is back to the flat
cap of 10. Large seed-level variance in both directions (seed 42 +$7,082; seed 99 -$12,981;
seed 500 -$14,729) — not noise, a real mechanism working against itself.

**Why it failed, and why the same idea will fail again if retried naively**: shop draws are
**public and shared** between both players in a mirror match. A heuristic that reacts to
observed demand by producing more does not create an edge in self-play, because the
opponent is the same agent and reacts identically — both farms expand together, and the
market absorbs neither farm's extra output, only the sum of both. The 14-cap cases (seeds
99, 500) are consistent with exactly this: both players independently detected "high milk
demand," both scaled to 14, and the resulting ~28-cow combined supply crashed price harder
than the fixed 10-cow baseline would have. This confirms the earlier contention-loss
analysis (MILK above_target 1.60, ~49% mirror-match loss at volume) — the loss is even
worse when *both* players scale up together in response to the same public signal.

**If herd-size adaptation is revisited**, it needs either (a) a response curve deliberately
more conservative than the naive demand-implied level, to price in the opponent's identical
reaction, or (b) a genuinely asymmetric signal instead of the shared shop draw (e.g. the
opponent's *observed* production/supply) — a much harder read from the observation, and its
own isolated test. Do not re-attempt a flat demand-count-based cap on any animal without
addressing this.

**This also was not the fix for seed 20's original regression.** Re-checked directly: seed
20 has PIZZA_SHOP in its draw, so `milk_shop_count >= 1` throughout the buying window, and
this change was a no-op there in both directions (identical reward before and after). Seed
20's weak milk revenue is not a zero-shop-demand case; the real cause is still open.

### 2c. Strawberry FERTILIZE implementation — TESTED, REJECTED, DO NOT RETRY AS-IS

Engine confirms `FERTILIZE` (kaggriculture.py:475-481) doubles each production event's
yield for ongoing crops (2 units instead of 1, engine:797) provided `watered_today` ends
up True that day (engine:799) -- a real, verified mechanic the agent never used at all.
Implemented: NE crew (units 6/7/8) restock FERTILIZER from the shed and apply it to
strawberry tiles via a new FERTILIZE task, gated on the tile already being watered that
day (to guarantee the application isn't wasted) and on the acting unit actually carrying
fertilizer (mirroring the `avail_seeds` gate pattern for PLANT tasks).

**First attempt regressed catastrophically** (seed 42: $44,441 -> ~$16,750 avg) due to a
genuine infinite-loop bug: `PICKUP` doesn't move the unit off the shed tile, so the very
next turn the pre-existing "carrying anything -> DROP" check (which runs before the new
PICKUP branch in the if/elif chain) immediately dropped the fertilizer right back. Units
6/7/8 got stuck oscillating pickup/drop at the shed indefinitely, abandoning their actual
NE watering/harvesting duties entirely -- the whole NE sector effectively went untended.
**Fixed** by excluding deliberately-carried FERTILIZER from the DROP check's
`carrying_produce` calculation for units 6/7/8 specifically.

**After the loop fix, still net negative in aggregate: -$598 (-1.4%), $41,637 -> $41,039**,
20-seed self-play. Instrumented directly: `fertilized_until_day` stayed `-1` on the
surviving strawberry plants at game end (seed 42) -- the feature essentially never
successfully fires in practice, and STRAWBERRY sold dropped to 41 units, *below* the
pre-change baseline (~50-56). Reverted all four changes (ne_task, claim gate, dispatch
mapping, shed pickup/drop); confirmed exact restoration of the known-good baseline on
seeds 42 and 99.

**Why it likely fails even with the loop bug fixed**: diverting the *same* dedicated NE
crew (6/7/8) that is responsible for daily watering and harvesting to also make shed
round-trips for fertilizer creates a real opportunity cost -- every turn spent fetching
fertilizer is a turn not spent watering/harvesting elsewhere in the sector, and with only
16 strawberry tiles needing fertilizer roughly every 2-3 days, the shed round-trip cost
appears to exceed the yield-doubling benefit when it does land, and often doesn't land at
all before priorities shift the unit elsewhere.

**If revisited**, don't reuse the same crew for logistics and cultivation. Options worth
trying instead: (a) a dedicated courier role (an idle sweep-crew unit once feed/care/
harvest is satisfied for the day) that pre-positions fertilizer near the NE sector rather
than NE crew fetching it themselves; or (b) skip fertilizer for strawberry entirely and
target it at a crop where the courier trip is less frequent relative to production value
(e.g., a one-time crop's WATER-tied fertilizer bonus, engine:437-443, which is a single
application per plant lifecycle rather than a recurring one). Do not re-attempt the
NE-crew-self-fetches-fertilizer design without addressing the opportunity-cost problem.

### 2d. Downward-only shop-conditioned cow cap — TESTED, ACCEPTED

Before implementing anything further, ran a real-evidence diagnostic first: 60 seeds of the
current chassis via `engine/fast_engine.py` (verified 20/20 exact vs the reference engine,
so trustworthy at scale), bucketed by observed milk-shop count. Result: performance is
**almost monotonic in milk-shop count** -- 0/1 shops: ~$29k, 2: $31k, 3: $42k, 4: $61k, 5:
$63k, 6: $81k -- and the 60-seed spread (4.52x) is *more* volatile than the real meta's own
per-cluster spread (2.22x). The milk_shops<=1 "disaster zone" is ~15-18% of games (matches
the binomial prediction) and drags the average down hard. See `eval/cluster_diagnostic.py`
(kept -- this is reusable infrastructure, not a one-off scratch script) and
`eval/benchmark_self_play.py` (moved from `scratch/`, where it kept getting wiped by
`cleanup.py` between sessions -- it's the standing harness the README already designates
`eval/` for).

This reopens the shop-conditioned herd-sizing question from 2b, but with the critical
asymmetry fixed: **only ever lower the cap below the baseline 10, never raise it above.**
Raising it is what caused 2b's regression (both players scale up together on the same
public signal and flood the market harder). Lowering it has no such trap -- one player
quietly avoiding a bad bet doesn't induce the opponent to do anything, since the two
decisions don't interact. Implemented: `cow_cap = 6 if (day >= 15 and milk_shop_count <=
1) else 10` (day>=15 so 5 of 8 draws have landed before the signal is trusted; before that,
milk_shop_count==0 is uninformative, not a real signal, and must not suppress the normal
early ramp).

**Result, verified two ways.** Fast-engine 60-seed sweep: all 5 previously-worst seeds
improved (+$2,174 to +$8,077), floor rose $18,855 -> $23,077 (-22% worst case), mean
$48,872 -> $49,708 (+1.7%). Official 20-seed `env.run()` benchmark, independently confirms
the direction: **$41,637.47 -> $41,917.03 (+0.67%)**, floor $21,043 -> $23,700.50, with
**median and max exactly unchanged** ($43,874.00 / $65,854.50) -- confirms the mechanism
is doing precisely what it should: protect the worst cases without touching or risking the
best ones. One single-seed regression on the 20-seed set (seed 404, -$4,723) amid broad
improvement elsewhere; acceptable given the net effect and that the mechanism is principled
(evidence-driven, asymmetric-safe) rather than a speculative parameter guess.

**New baseline: $41,675.45 / $42,158.60 self-play.** Still ~2.1x short of the $88,857 real
mirror-match target. The milk_shops<=1 zone is now less catastrophic but still well below
the demand-rich zone (~$29-31k pre-fix; unmeasured post-fix at the bucket level -- worth
re-running the 60-seed cluster sweep to get updated per-bucket numbers if this is revisited).

**Lesson for future conditional-behavior attempts (as of 2b+2d)**: the asymmetry between
scaling up (fails, mutual escalation) and scaling down (works, no interaction effect)
looked like it would generalize to sheep/goose sizing and crop-plot allocation. **2e below
shows that generalization is wrong, or at least not sufficient on its own** -- read both
before touching herd sizing again.

### 2e. Upward sheep scaling on high-wool-pressure draws — TESTED, REJECTED

Re-ran the 60-seed cluster sweep after 2d and found a NEW worst-5 cluster: all had low
milk AND high wool pressure (2-3 YARN_STORE draws). Checked the demand math directly
(YARN_STORE = 12 wool/day/instance, verified this session): at 3 instances (36/day
demand), combined 2-player production at the existing cap=4 sheep (4 wool/yield with the
CARE lock, 3-day interval) is only ~10.7/day -- **~30% utilization**. This looked
structurally different from cows, which were already *oversupplied* relative to demand
even on a good draw (10 cows x 2 players = 30/day vs a 4-shop milk demand of 24/day) --
sheep looked *undersupplied* even at max wool pressure, so scaling up seemed safe: there
was real headroom before the mutual-flood mechanism that killed 2b's cow experiment could
even apply.

Implemented a graded cap (`{1:4, 2:6, 3:8}.get(yarn_count, 10)`) targeting ~60% combined
demand utilization at each tier, deliberately conservative given WOOL's above_target=3.20
is the steepest glut curve in the game.

**Result: net negative, and one seed catastrophic.** Full 60-seed sweep: mean $49,708 ->
$49,244 (worse), and critically **the floor got worse, not better**: $23,077 -> $11,837.
Seed 10004 specifically lost more than half its value ($25,412 -> $11,837). This is the
opposite of the intended effect (2d's whole point was raising the floor on adverse draws).
Reverted immediately; confirmed exact restoration on seeds 10004 and 10006.

**Why the "undersupply means safe to scale up" reasoning was wrong, or at least
incomplete**: the demand-vs-production math was correct as far as it went, but it ignored
the OTHER side of the ledger -- sheep are $500 each (more than cows' $400), and the extra
capital committed to sheep purchases is capital NOT available for wheat, land, hires, or
feed reserves. On seed 10004 specifically, something in that competition for capital (or
for shed throughput, or for crew action-slots -- not yet isolated which) cost far more than
the extra wool revenue gained. The lesson is not "undersupply implies safe to scale up" --
it is that **any upward change needs to be checked against the full opportunity cost, not
just the demand-side math for the one product being scaled.** This generalizes the 2b/2d
lesson further: downward-only remains the safe default, and an upward exception needs
positive evidence on the *whole* 20/60-seed distribution, not just a plausible one-product
argument, before being trusted.

**If revisited**, instrument seed 10004 specifically to find the actual mechanism (capital
timing, shed overflow, crew/action competition) before trying a different upward variant --
don't just retune the thresholds and re-run blind.

### 2f. SE (4th) quadrant unlock, wheat-only fill — TESTED, REJECTED

Real data (`results/meta_portfolio_summary.csv`) shows only 17.5% of real trajectories
unlock SE (median day 12), and those who do average +7.8% ($94,318 vs $87,468) --
correlational, not causal. Tested the causal question directly with our own chassis:
unlocked SE around day 10-14 when capital allowed ($4,000+), filled with 24 wheat-only
tiles (deliberately not animals, to avoid reopening the exact risk pattern that just failed
in 2b/2e), routed through the existing SW crew rather than a new crew division (simplest,
lowest-risk plumbing).

**Result: net negative on every metric.** 60-seed fast-engine sweep: mean $49,708 ->
$47,436 (-4.6%), max $85,151 -> $81,188 (-4.7%), floor unchanged (the disaster-zone seeds
never had the capital to trigger SE anyway). SE fired in 34/120 player-instances (~28% --
higher than real players' 17.5%, since ours has a specific capital profile, not a
representative population). Reverted fully, including the now-unused `SE_WHEAT` coordinate
list and `self.se_wheat` -- no dead code left in the file. Confirmed exact restoration on
seeds 10055 and 10004.

**Likely mechanism, not fully isolated**: the $4,000 spend at day 10-14 is a large capital
diversion at a sensitive point in the build-out, and wheat's per-tile value is modest
(one-time crop, max ~4 unfertilized units per cycle); 24 additional tiles handed to the
already-busy SW crew (managing 6 melon + 18 wheat tiles) plausibly go under-serviced rather
than realizing their theoretical revenue -- crew capacity was deliberately left unexamined
in this test to keep it to one variable, so this is a real candidate explanation, not yet
confirmed.

**If revisited**: this needs a joint test, not another single-variable wheat-only attempt.
At minimum: (a) a dedicated SE crew slot (not reusing the SW crew) so this doesn't compete
for the same crew's attention, and (b) instrument whether the added tiles actually get
watered/harvested on schedule or sit dead, before concluding the land purchase itself is a
bad idea versus just badly serviced. Given real players who unlock SE do so alongside a
different overall build (the median-day-12 rush spends $7,000 total on land by day 12,
which is a very different capital allocation than our agent's current early-game profile),
a fair test may require restructuring more of the early build order, not adding SE onto an
otherwise-unchanged chassis.

### 2g. Direct re-measurement of the CURRENT build (2026-08-23) — HANDOVER.md's §4 was stale

Triggered by a real discrepancy between two of this project's own documents: `HANDOVER.md`
still lists "no CARE bonus (~$42k)" as the single highest-value unimplemented fix and shows
milk=97.5/wool=54.0/wheat=928.9 as the *current* volumes, while this very file's benchmark
table shows a "CARE bonus lock" row was already attempted (before the 2d cow-cap change)
and never had its own volume numbers recorded. Rather than trust either document, measured
the build as it exists right now directly (`eval/care_bonus_diagnostic.py`, fast engine,
official 20-seed set, kept as reusable infrastructure — not scratch).

**Finding 1 — CARE bonus is already substantially active, HANDOVER.md's framing is wrong.**
Same-day fed+cared hit rate, sampled at hour 23 each day (misses at most that day's hour-23
action, everything else captured): **COW 87.2% both-flags, SHEEP 83.3%, GOOSE 78.3%**. This
is not "yields 1 unit per production" as HANDOVER.md's §4 claims — it is close to full CARE
coverage already. That claim and the volume table under it describe an earlier build (before
the CARE-lock and 2d cow-cap changes) and were never refreshed. Corrected in HANDOVER.md.

**Finding 2 — a real, previously unnoticed regression: WHEAT and WOOL sold have collapsed**
relative to both the meta target and this project's *own* previously-recorded numbers for a
supposedly-later build. 20-seed fast-engine mean, P0 only:

| product | this measurement | previously recorded (Peikopon row, pre-CARE-lock) | meta target |
|---|---|---|---|
| WHEAT | **345.5** | 928.9 | 856 |
| WOOL | **20.6** | 54.0 | 139 |
| MILK | **187.7** | 97.5 | 279 |
| STRAWBERRY | 40.5 | 52.0 | 286 |
| MELON | 29.1 | 56.9 | 72 |
| FERTILIZER | 227.3 | 154.5 | ~336 physical max |
| EGG | 68.4 | (not tracked before) | — |

Milk and fertilizer went up (consistent with CARE actually working now — animals held
longer, more of everything). But wheat dropped 63% and wool dropped 62% versus the last time
anyone measured them, on a build that should only have gotten fixes since then. **Not yet
root-caused.** Leading hypothesis, not confirmed: the sweep crew (units 0-3) is now spending
much more of its attention on FEED/CARE round-trips to reliably hit 78-87% same-day coverage,
which is a real crew-time cost that was not paid before CARE was reliable — plausibly at the
expense of wheat-feed diversion (more wheat now feeds animals instead of being sold, which
is likely a good trade) and of sheep/wool tending specifically (SHEEP has the fewest
tile-days observed of the three animals, suggesting sheep are either placed late or
undermaintained relative to cap). **This is now the single largest unexplained item in the
whole project and should be root-caused before any further tuning** (ahead of the shed-
lookahead idea proposed earlier, and ahead of any competitor-technique adoption) — it is
plausibly worth more than every accepted change in this file combined.

**Finding 3 — fast-engine/real-engine equivalence has drifted and was never re-checked, as
HANDOVER.md §4 already warned.** This diagnostic's fast-engine mean on the official 20-seed
set is $42,760.68; the accepted-baseline mean from real `env.run()` on the identical 20
seeds is $41,917.03 (solver/NOTES.md) — a ~2% gap that should be $0.00 if the 20/20 exact
match still holds for the current build. **Every fast-engine-based result in this project
since the CARE-lock/2d changes (60-seed sweeps, param_search, coordinate_sweep, the 2e/2f
rejections) rests on an equivalence claim that was last verified on an older build and has
not been reconfirmed.** This does not necessarily invalidate those results (rejections
staying rejected is the likely outcome even with a 2% engine gap), but it must be re-run
before the next real decision is made on fast-engine evidence alone.

### 2h. Horizon Fix, Sheep Isolation, HIRE Isolation, and PLANT Priority Resolution (2026-08-23)

Following strict one-variable-at-a-time governance on the official 20-seed set:

#### Step 1: Systemic Fast-Engine Horizon Fix & Re-Baseline
- **Root Cause & Fix**: `kaggriculture.py:960` fires `DONE` on step 718 (`step >= episodeSteps - 2`). FastGame previously looped `while game.step < 720`, executing a 720th phantom step on Day 29 Hour 23. Fixed systemically: `EPISODE_STEPS = 719`, exposed `game.done` property, guarded `step_game()`, and updated all 8 callers across the repo (`fast_engine.py`, `care_bonus_diagnostic.py`, `cluster_diagnostic.py`, `coordinate_sweep.py`, `param_search.py`, `validate_candidates.py`, `validate_sweep_winners.py`, `steering_test.py`).
- **Equivalence Verification**: `validate_fast_engine.py` confirmed **20/20 exact matches, $\Delta = \$0.00$** in pure self-play vs `env.run([agent, agent])` (20.4x speedup, ~2,176 steps/sec).
- **Candidate 2d Re-Verification**: Re-ran cow-cap comparison on corrected engine: Base Mean \$41,637.47, `cow_cap_low=8` Mean \$42,350.07 (+1.71%), floor +\$3,762 on worst seed.
  **⚠ CORRECTION (2026-08-24, see §2j.1)**: this \$42,350.07 figure is `cow_cap_low=8`, NOT the production value (`cow_cap_low=6`) — it was mislabeled "2d" here. Independently validated on 100 disjoint seeds in §2j.1 and **rejected** as a 20-seed overfit (lost 19-5 head-to-head, floor -\$2,743). Production `cow_cap_low=6` remains correct; do not read the line above as confirming 8.
- **New Official Baseline**: **Match Mean \$41,917.03** (Median \$43,874.00, Min \$23,700.50, Max \$65,854.50). Volumes: Wheat 330.8, Milk 181.7, Wool 20.4, Egg 65.8, Fert 223.1, Straw 41.0, Melon 28.9.

#### Step 2: Sheep Fix Alone (Unnested from Cow `else:`) — TESTED, REJECTED
- **Candidate**: Pulled sheep purchasing evaluation out of the `else:` branch of cow cap so sheep evaluate independently.
- **Result**: Match Mean **\$39,211.93** (vs Baseline \$41,917.03, -$2,705.10 / -6.45%).
- **Mechanism**: In self-play, expanding sheep without Yarn Store demand crashes the quadratic AMM wool curve ($above\_target = 3.20$) to the $1 floor, while burning $500 capital + daily wheat feed.
- **Decision**: **REJECTED** as an isolated change.

#### Step 3: HIRE Order Splitting Alone (Hours 0 & 1) — TESTED, REJECTED
- **Candidate**: Split daily HIRE requests across hours 0 (up to 8) and 1 (up to 8) to bypass `kaggriculture.py:551/560`'s 10-order morning queue cap and actually hire all 13 workers.
- **Result**: Match Mean **\$34,876.82** (vs Baseline \$41,917.03, -$7,040.21 / -16.8%).
- **Volume vs Financial Mechanism**: Produced higher volumes across every category (+88.7 wheat, +7.0 milk, +6.9 melon, +4.4 strawberry), but Fibonacci wage costs for Workers 11, 12, 13 ($89 + $144 + $233 = $466/day = $10,252/season) dwarfed their marginal revenue (~$2,900), resulting in net wage destruction of -$7,352.
- **Decision**: **REJECTED** as an isolated change (field crew $\le 10$ hands is economically optimal).

#### Step 4: PLANT Priority & Same-Tile Immediate Replant Alone — TESTED, ACCEPTED
- **Candidate**: Raised `PLANT_WHEAT` from 25/40 $\rightarrow$ 93, `PLANT_STRAWBERRY` from 35 $\rightarrow$ 95, `PLANT_MELON` from 35 $\rightarrow$ 96, and added a $+500$ same-tile action bonus to eliminate workers walking away from freshly harvested empty plots.
- **Volume Impact**: Wheat sold jumped **330.8 $\rightarrow$ 416.0 (+85.2 units)**, Strawberry jumped **41.0 $\rightarrow$ 60.0 (+19.0 units)**, Melon jumped **28.9 $\rightarrow$ 32.1 (+3.2 units)**.
- **Decision**: **ACCEPTED**. New baseline is **\$46,048.43**.

### 2i. Explicit Parameter Alignment: crew_late 13 -> 10 (2026-08-24)

Step 3 (above) showed hiring all 13 workers `crew_late` was requesting is a net loss — the
engine's `maxMarketOrdersPerTurn=10` cap (kaggriculture.py:551/560) was silently truncating
the daily HIRE burst to 10 hires every morning, and that accidental ~10-hand ceiling was
already the better outcome. Rather than leave crew size implicitly controlled by an engine
order-limit nobody reading `DEFAULT_PARAMS` would know about, set
`DEFAULT_PARAMS["crew_late"] = 10` explicitly so the code states the real limit. Verified
score-neutral across all 20 official seeds (still \$46,048.43, identical to Step 4's
baseline) — this is a legibility fix, not a behavior change.

### 2j. Disjoint Validation of cow_cap_low in {6, 8} and Strawberry Lifecycle Resolution (2026-08-24)

#### 1. Independent 100-Seed Disjoint Validation of `cow_cap_low` in {6, 8}
- **Methodology**: Evaluated on 100 fresh, unseen seeds (`seeds 10000 to 10099`), completely disjoint from the official 20-seed training set.
- **Results**:
  - `cow_cap_low = 6` (production): **Mean = \$50,809.56** | Median = \$49,669.25 | **Min = \$22,413.50** | Max = \$87,417.00
  - `cow_cap_low = 8` (candidate): Mean = \$50,431.51 | Median = \$49,447.75 | Min = \$19,670.50 | Max = \$87,417.00
  - Mean Delta (8 vs 6): **-\$378.04 (-0.74%)** | Min Delta (8 vs 6): **-\$2,743.00**
  - Head-to-head across 100 seeds: `cow_cap_low = 6` won 19 seeds, `8` won only 5 seeds (76 ties).
- **Decision**: `cow_cap_low = 8` was an artifact of overfitting to the 20-seed set. **Kept `cow_cap_low = 6` as the confirmed superior setting.**

#### 2. Expired Strawberry Plot Digging & Carrot Replanting Pipeline — TESTED, ACCEPTED
- **Mechanism**: Ongoing strawberry plants expire after 4 productions (`day = 10 + 4*2 = 18`), setting `max_lifespan_step` (`kaggriculture.py:801-802`). In the prior build, expired plants sat dead while workers wasted watering actions from Day 18 to Day 29. Implemented: detect `max_lifespan_step >= 0` with `yield_units == 0`, immediately `DIG` the dead plant (`priority: 94`), and replant with CARROT cycles on Days 18–27 (`first_yield_day = 2`, `base = $35`).
- **Official 20-Seed Outcome**:
  - **Match Mean**: **\$46,048.43 $\rightarrow$ \$47,489.97 (+3.13% / +\$1,441.54)**
  - **Match Median**: **\$45,530.25** (+$1,624.25) | **Min**: **\$24,654.00** (+$107.00) | **Max**: **\$72,547.50** (+$224.50)
  - **Volume Changes**: Carrots sold jumped **9.7 $\rightarrow$ 45.5 units (+35.8 units)**; Wheat sold: 416.2 units; Strawberry sold: 55.5 units; Milk sold: 171.1 units.
- **Fast-Engine Equivalence**: Re-verified on full 20-seed pure self-play: **20/20 exact matches, $\Delta = \$0.00$** (24.9x speedup, 2,526 steps/sec).
- **Decision**: **ACCEPTED**. New standing baseline is **\$47,489.97**.

### 2k. Shed-Full Animal-Purchase Guard (2026-08-24)

- **Engine Mechanism & Citation**: `kaggriculture.py:682-683` verifies that when `sum(private["shed"].values()) >= shed_capacity` (default 100), `BUY_ANIMAL` returns `False` silently with zero error signal. Citation confirmed correct.
- **Candidate**: In `dispatcher_agent.py`, widened the pre-existing outer gate on all three animal-purchase branches from `shed_total_items <= 90` to `shed_total_items < 95`, and added an inner guard `(shed_total_items + buy_qty) <= 98` before appending the `BUY_ANIMAL` order.
- **Result**: Confirmed score-neutral to the dollar across all 20 seeds (Match Mean \$47,489.97, Median \$45,530.25, Min \$24,654.00, Max \$72,547.50, identical on every metric).

**⚠ CORRECTION — do not read the $0.00 delta as evidence this guard does anything.**
`buy_qty` is capped at `min(2, ...)` per branch, and the outer gate bounds the snapshot to
at most 94 (`< 95`). So the inner check evaluates at most `94 + 2 = 96 <= 98` —
**mathematically always true given the outer bound.** It cannot ever fire false. Even the
real engine cap is never at risk here: goose(2) + cow-or-sheep(2) on top of a 94 snapshot is
98, still under the 100 cap. A guard that is analytically unreachable will of course produce
an exact $0.00 delta on every metric — that is the signature of dead code, not confirmation
of a safe defensive fix. This benchmark could not have detected this guard doing anything,
because it structurally cannot do anything under the current per-species caps (goose 4, cow
10, sheep 4) and purchase-batch size (max 2/turn/species).

- **Empirical Instrumentation (Observed Range)**:
  Instrumented `shed_total_items` at every animal purchase evaluation point (`hour == 0, day < 20`) across both the 20 official seeds (840 checkpoints) and 100 disjoint seeds (4,200 checkpoints):
  - 20 Official Seeds: Min = 29, Max = 100, Mean = 52.72. Checkpoints $\ge 80$: 68/840 (8.1%); Checkpoints $\ge 90$: 39/840 (4.6%).
  - 100 Disjoint Seeds (10000-10099): Min = 12, Max = 100, Mean = 51.61. Checkpoints $\ge 80$: 284/4200 (6.8%); Checkpoints $\ge 90$: 137/4200 (3.3%).
  - On late purchase days (Days 18–19 for sheep), shed counts routinely hit 82–89 with bank balances of $4k–$10k.
- **Resolution**:
  High shed inventory *does* occur during the purchase window. Retained the single, clean, robust outer bound `shed_total_items <= 90` across all three animal branches and removed the redundant inner check. Since each branch purchases at most 2 animals (`buy_qty <= 2`), the snapshot bound of 90 guarantees $90 + 2 = 92 < 100$, leaving 8 slots of safety margin for opening orders and physically preventing any silent engine drop at `kaggriculture.py:682-683`.
- **Status**: **RESOLVED** (clean single-bound guard verified effective, baseline unchanged at **\$47,489.97**).

---

### 2l. Dynamic Crew Sizing & Workload Scaling (2026-08-24)

- **Hypothesis**: Dynamic crew sizing scaling hands with daily task workload rather than a fixed step function can reduce Fibonacci hiring wage expenditure ($143/day for 10 hands vs $20/day for 6 hands).
- **Finding 1 (Mid-Season Workload Scaling — REJECTED)**:
  - Dynamically reducing crew size on low-task maintenance/growing days (e.g. Days 0..2 to 4 hands, Days 3..7 to 5 hands, or Days 8..28 to 9 hands) caused match mean to collapse from **\$47,489.97 $\rightarrow$ \$44,664.20 (-$2,825.78)** with severe downside outliers (Seed 700: -$27.3k, Seed 777: -$25.1k, Seed 100: -$16.4k).
  - **Mechanism**: In a 10x10 spatial grid, walking distances from the shed to NE/SW corners are 5–9 steps each way. 4 units are dedicated to the 14 NW animals; reducing crop workers below 3 per active quadrant means walking delays exceed the 24-turn daily limit, causing unwatered crop plots. Two consecutive missed watering days permanently converts crops into weeds (`kaggriculture.py:783-784`), losing entire harvest cycles.
- **Finding 2 (Season-End Day 29 Scale-Down — ACCEPTED)**:
  - On Day 29, planting and watering are 100% inactive (season ends at step 718, `kaggriculture.py:960`). Scaling `target_crew` from 10 down to 7 hands saves $110 in hiring wages directly while providing ample throughput for all mature crop and livestock harvesting.
  - **Official 20-Seed Outcome**:
    - **Match Mean**: **\$47,489.97 $\rightarrow$ \$47,526.12 (+ \$36.15)**
    - **Match Median**: **\$45,474.25** | **Min**: **\$24,663.00** (+$9.00) | **Max**: **\$72,530.50**
  - **100-Seed Disjoint Validation (Seeds 10000–10099)**:
    - Baseline Mean: **\$51,661.36** $\rightarrow$ Dynamic Mean: **\$51,751.62 (+ \$90.26 / +0.17%)**
    - Head-to-Head: **Dynamic won 64, Baseline won 36 (64.0% win rate)**.
- **Fast-Engine Equivalence**: Re-verified in `validate_fast_engine.py`: **20/20 exact matches, $\Delta = \$0.00$** (23.4x speedup, 2,047 steps/sec).
- **Decision**: **ACCEPTED** (Day 29 season-end dynamic scale-down to 7 hands). New standing baseline is **\$47,526.12**.

---

### 2m. Causal Shop-Value Table & Statistical Steering Analysis for Day-3 Draw (2026-08-24)

- **Objective**: Rigorously measure the causal impact of forcing each of the 8 shop types on the Day 3 shop draw, holding the seed fixed in a controlled within-seed comparison, with Player 1 running the unmodified dispatcher agent throughout.
- **Engine Mechanism & Citation**: `kaggriculture.py:862-891` (`871` for daily RNG seeding `random.Random((seed * 1_000_003) ^ day)`, `877` for `_spawn_weeds`, `891` for `town["unlocked_shops"].append(rng.choice(sorted(SHOPS)))`). Verified exact equivalence in `fast_engine.py:570, 632, 658`.
- **Methodology**:
  - Swept $K \in [0..24]$ (NW wheat tiles planted by Day 2) across **100 disjoint seeds (`seeds 10000 to 10099`)** in pure self-play (P1 = real dispatcher agent).
  - For each achievable shop on a seed, ran the full 720-step episode with a hybrid agent (forcing $K$ plantings on Days 0..2, then handing off to the unmodified dispatcher on Day 3+).
  - Evaluated the **within-seed causal delta**: $\Delta = R(\text{seed}, s) - \bar{R}_{\text{seed}}$.

#### Part 1: Per-Shop Causal Delta, Variance & Standard Error ($N = 100$ Seeds)

| Shop Type | Demanded Products | Reachable ($n / 100$) | Mean Delta vs Seed Avg | Std Dev ($\sigma$) | Std Error ($\text{SE}$) | 95% Confidence Interval | Mean $K$ ($\pm \text{Std}$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`SMOOTHIE_SHOP`** | STRAWBERRY, MILK | 88 / 100 (88.0%) | **+\$2,164.73** | \$12,955.63 | \$1,381.08 | [-\$542, +\$4,872] | 6.5 ($\pm$ 5.5) |
| **`ICE_CREAM_SHOP`** | STRAWBERRY, MILK, WHEAT | 85 / 100 (85.0%) | **+\$2,067.77** | \$14,047.68 | \$1,523.68 | [-\$919, +\$5,054] | 5.4 ($\pm$ 5.2) |
| **`PIZZA_SHOP`** | MILK, TOMATO, WHEAT | 85 / 100 (85.0%) | **+\$1,223.26** | \$12,845.53 | \$1,393.29 | [-\$1,508, +\$3,954] | 5.6 ($\pm$ 5.1) |
| **`FARMERS_MARKET`** | WHEAT, CARROT, TOMATO, STRAWBERRY | 87 / 100 (87.0%) | **+\$1,039.81** | \$11,494.20 | \$1,232.31 | [-\$1,376, +\$3,455] | 6.9 ($\pm$ 5.5) |
| **`BRUNCH_SPOT`** | EGG, WHEAT, STRAWBERRY | 87 / 100 (87.0%) | **+\$404.01** | \$12,893.01 | \$1,382.28 | [-\$2,305, +\$3,113] | 6.5 ($\pm$ 6.0) |
| **`YARN_STORE`** | WOOL | 84 / 100 (84.0%) | **-\$1,721.94** | \$10,524.53 | \$1,148.32 | [-\$3,973, +\$529] | 7.3 ($\pm$ 5.9) |
| **`PET_CAFE`** | CARROT | 94 / 100 (94.0%) | **-\$1,854.54** | \$11,090.46 | \$1,143.89 | [-\$4,097, +\$387] | 6.7 ($\pm$ 5.6) |
| **`BAKERY`** | EGG, WHEAT | 89 / 100 (89.0%) | **-\$3,110.97** | \$10,815.60 | \$1,146.45 | [-\$5,358, -\$864] | 6.7 ($\pm$ 5.8) |

#### Part 2: Direct Same-Seed Paired Comparisons (Matched Pairs)

| Comparison ($A$ vs $B$) | Paired $n$ | Mean Difference ($A - B$) | Paired Std Dev | Paired $\text{SE}$ | $t$-statistic | $p$-value | Significance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`SMOOTHIE_SHOP` vs `BAKERY`** | 79 / 100 | **+\$5,120.58** | \$17,503.61 | \$1,969.31 | **+2.60** | **$p = 0.0111$** | **Statistically Significant ($p < 0.05$)** |
| **`FARMERS_MARKET` vs `BAKERY`** | 79 / 100 | **+\$4,579.48** | \$16,007.05 | \$1,800.93 | **+2.54** | **$p = 0.0130$** | **Statistically Significant ($p < 0.05$)** |
| **`SMOOTHIE_SHOP` vs `PET_CAFE`** | 82 / 100 | **+\$3,847.06** | \$18,490.66 | \$2,041.95 | **+1.88** | **$p = 0.0632$** | Marginally Significant ($p < 0.10$) |
| **`PIZZA_SHOP` vs `PET_CAFE`** | 79 / 100 | **+\$3,114.48** | \$19,204.17 | \$2,160.64 | **+1.44** | $p = 0.1535$ | Not Significant ($p > 0.05$) |
| **`PIZZA_SHOP` vs `YARN_STORE`** | 72 / 100 | **+\$2,990.69** | \$18,061.28 | \$2,128.54 | **+1.41** | $p = 0.1644$ | Not Significant ($p > 0.05$) |
| **`PIZZA_SHOP` vs `BAKERY`** | 75 / 100 | **+\$2,893.01** | \$18,423.67 | \$2,127.38 | **+1.36** | $p = 0.1780$ | Not Significant ($p > 0.05$) |

#### Part 3: $K$-Occupancy Confounding & Two-Way Fixed Effects OLS

- **$K$-Penalty**: Overall Pearson correlation between $K$ (tiles planted) and Final Money is $r = -0.1720$ ($p = 4.8 \times 10^{-6}$). Each extra tile forced during Days 0..2 incurs a statistically significant cost of **-\$420.72 per tile** ($t = -5.19, p = 2.8 \times 10^{-7}$).
- **Two-Way Fixed Effects Regression (Centering by Seed Mean, Ref = `BAKERY`)**:
  - $K$ coefficient: **-\$420.72 / tile** ($\text{SE} = \$81.13, t = -5.19, p < 10^{-6}$)
  - `SMOOTHIE_SHOP`: **+\$5,188.41** ($\text{SE} = \$1,789.95, t = +2.90, p = 0.0039$)
  - `ICE_CREAM_SHOP`: **+\$4,609.37** ($\text{SE} = \$1,809.02, t = +2.55, p = 0.0111$)
  - `FARMERS_MARKET`: **+\$4,225.66** ($\text{SE} = \$1,795.10, t = +2.35, p = 0.0189$)
  - `PIZZA_SHOP`: **+\$3,839.11** ($\text{SE} = \$1,808.21, t = +2.12, p = 0.0341$)
  - `BRUNCH_SPOT`: **+\$3,401.26** ($\text{SE} = \$1,795.17, t = +1.89, p = 0.0586$)
  - `YARN_STORE`: **+\$1,607.95** ($\text{SE} = \$1,811.67, t = +0.89, p = 0.3751$)
  - `PET_CAFE`: **+\$1,226.41** ($\text{SE} = \$1,760.92, t = +0.70, p = 0.4864$)

#### Strategic Gating Verdict
1. **True Shop Effect vs High Variance**: Premium Strawberry/Milk draining shops (`SMOOTHIE_SHOP`, `ICE_CREAM_SHOP`) provide a statistically significant **+\$4.6k to +\$5.2k** true shop premium over `BAKERY` ($p \le 0.01$).
2. **The $K$-Penalty in Planter-Only Models**: The $-\$420.72/\text{tile}$ regression penalty arose because the probe's hybrid planter agent omitted all Day 0 animal purchases (4 cows + 1 sheep), hiring, feeding, and caring during Days 0..2.

---

### 2n. Value-Gated Integrated Dispatcher Steering (2026-08-24)

- **Hypothesis**: Instead of an external planter that replaces opening chores, integrate steering directly inside the real dispatcher agent by modulating *only* the NW wheat planting cap $K_w \in [0..10]$ on Days 0..2, preserving 100% of the Day 0 animal purchases (4 cows + 1 sheep), full 6-hand crew, and daily feeding/caring.
- **Re-Derived Empirical Cost Model ($N=100$ Seeds, 1,100 Games under Real Dispatcher)**:
  - Marginal value of NW wheat planted earlier: $\beta_{K_w} = \mathbf{+\$208.74 / \text{tile}}$ ($\text{SE} = \$112.22, t = +1.86, p = 0.063$).
  - Delaying $(10 - K_w)$ wheat plantings by 2 days carries an exact empirical opportunity cost of:
    $$\text{Displacement Cost}(K_w) = \$208.74 \times (10 - K_w)$$
  - Full-season shop effect coefficients ($\gamma_s$ vs `BAKERY` under 4C/1S + 16-Strawberry active production):
    - `SMOOTHIE_SHOP`: **+\$18,469.37** ($\text{SE} = \$1,362.54, t = +13.56, p < 10^{-30}$)
    - `ICE_CREAM_SHOP`: **+\$17,190.58** ($\text{SE} = \$1,455.22, t = +11.81, p < 10^{-25}$)
    - `PIZZA_SHOP`: **+\$14,724.84** ($\text{SE} = \$1,425.60, t = +10.33, p < 10^{-20}$)
    - `FARMERS_MARKET`: **+\$4,047.12** ($\text{SE} = \$1,448.17, t = +2.79, p = 0.0053$)
    - `BRUNCH_SPOT`: **+\$2,267.06** ($\text{SE} = \$1,398.80, t = +1.62, p = 0.105$)
    - `PET_CAFE`: **+\$979.34** ($\text{SE} = \$1,364.47, t = +0.72, p = 0.473$)
    - `YARN_STORE`: **-\$1,870.32** ($\text{SE} = \$1,386.76, t = -1.35, p = 0.178$)
    - `BAKERY`: **\$0.00**
- **Value-Gated Decision Rule**:
  $$\text{Gain}(S, K_w) = (\gamma_S - \gamma_{S_0}) - \$208.74 \times (10 - K_w)$$
  Steer to $S^* = \arg\max \text{Gain}$ only if $\max \text{Gain} > \$1,000$; otherwise leave natural opening alone.
- **Important Statistical Qualification on Expected Gain**:
  - `Exp Gain` is an aggregate population expected value, **not a deterministic per-match forecast**. Because within-shop standard deviations are large ($\sigma \approx \$10.5\text{k}-\$14\text{k}$), individual steered seeds can and do experience substantial drawdowns (e.g. seeds 250, 777, 999 saw $-\$16\text{k}$ to $-\$17.8\text{k}$ deltas due to subsequent shop draw variance and market interactions). The controller's advantage is purely statistical across the distribution (87.5% win rate, $+6.69$ $t$-stat).
- **Initial Exploratory Calibration ($30/tile Seed Capital Estimate)**:
  - Using an initial proxy cost of \$30/tile delayed wheat harvest opportunity cost, the controller scored **\$57,908.97** on the official 20 seeds (56 steered on the 100-seed suite, mean \$62,030.96).
- **Corrected Empirical Benchmark ($208.74/tile Derived Cost & Integrated Gamma)**:
  - **Decision Rule**: $\text{Gain}(S, K_w) = (\gamma_S - \gamma_{S_0}) - \$208.74 \times (10 - K_w)$, gate threshold $\text{Gain} > \$1,000$.
  - **Official 20-Seed Outcome**:
    - **Baseline Mean**: **\$47,526.12**
    - **Steered Mean**: **\$56,743.07 (+ \$9,216.95 / +19.39%)**
    - **SE of Delta**: \$4,169.42 ($t = +2.21, p = 0.0395$)
    - **Head-to-Head**: Steered won 13, Lost 5, Tied 2 (72.2% win rate on steered seeds; 18/20 steered).
  - **100-Seed Disjoint Validation (`seeds 10000 to 10099`)**:
    - **Seeds Steered**: 65 / 100 (65.0%)
    - **Baseline Mean**: **\$51,754.27**
    - **Steered Mean**: **\$62,293.33 (+ \$10,539.07 / +20.36%)**
    - **SE of Delta**: \$1,539.94 ($t = +6.84, p = 6.51 \times 10^{-10}$)
    - **Head-to-Head**: Steered won 56, Lost 9, Tied 35 (86.2% win rate on steered seeds).
- **Standing Confirmed Baseline**: **\$56,743.07** (Official 20 Seeds, real `env.run()` / fast engine $\Delta = \$0.00$).

---

### 2o. Dedicated-Courier Strawberry Fertilization — VERDICT WITHHELD, harness invalid (2026-08-24)

- **Architecture**: Assigned Unit 3 (the livestock sweep worker with the lightest morning chore load) to carry fertilizer to NE strawberry plots during its afternoon idle window (hours 8-13) with a strict curfew returning to `(4,4)` by hour 16, leaving field-crop workers (Units 4-12) completely untouched.
- **Corrected Four-Shop Gate**:
  - `STRAWBERRY_SHOPS = {"SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "FARMERS_MARKET", "BRUNCH_SPOT"}` (`kaggriculture.py:103-112`).
  - Liquidity guard: `money >= $300` and `shed_wheat >= 8` (protecting the 15-wheat cow feed buffer from liquidity starvation).
- **Benchmark Results (Symmetric Self-Play)**:
  - **Official 20 Seeds**: Baseline \$49,323.38 $\rightarrow$ Courier \$49,391.00 (Delta: **+\$67.62**, $\text{SE}=\$124.10, t = +0.54, p = 0.592$).
    - Head-to-Head: 4 Wins, 9 Losses, 7 Ties.
  - **100 Disjoint Seeds (`10000-10099`)**: Baseline \$55,288.72 $\rightarrow$ Courier \$55,366.00 (Delta: **+\$77.28**, $\text{SE}=\$170.82, t = +0.45, p = 0.652$).
    - Head-to-Head: 22 Wins, 34 Losses, 44 Ties.
- **Reconciliation of Prior Numbers**:
  - The earlier reported comparison "\$55,949 $\rightarrow$ \$62,288" was an asymmetric probe (Player 0 tested against an unsteered $K_w=10$ Player 1).
  - In symmetric self-play where both seats run value-gated steering, the confirmed standing baseline is **\$56,743.07** on official 20 seeds (**\$62,293.33** on disjoint 100 seeds).
  - Enabling the 4-shop dedicated courier produces a flat/insignificant $+\$77.28$ delta ($p=0.65$) and a losing head-to-head record (22W / 34L).
- **Economic Root Cause**:
  - `STRAWBERRY`: `base = 120, I0 = 10000, T = 100, above_func = linear, above_target = 1.60` (`kaggriculture.py:45`).
  - When both players sell 100+ units of strawberries, price depresses to $\sim \$15-\$25/\text{unit}$.
  - Consuming 1 unit of `FERTILIZER` (which sells directly into the AMM for \$60-\$80 under `above_target = 0.40`) to generate 4 extra strawberries yields ~\$80 gross revenue, netting only $\sim +\$15$ gross margin per plant over the entire season. Minor chore/pathing friction erodes this margin entirely.
- **Decision**: **REJECTED (DEFINITIVE)**.

**⚠ CORRECTION (Claude, verification pass): this is NOT a valid rejection — it is the third
consecutive attempt to test this that was invalidated by its own harness.** The four-shop gate
fix was correct and the two engineering fixes are real, but the benchmark ran against the wrong
agent:

- This section asserts the standing baseline is **$56,743.07** and then benchmarks against
  **$49,323.38** — a ~$7.4k gap, mirrored by ~$7.0k on the disjoint set ($55,288.72 vs
  $62,293.33). A consistent offset across both seed sets is systematic, not noise, and the two
  figures are irreconcilable as written.
- Root cause, verified directly in the harness:
  `scratch/test_active_four_shop_courier.py` declares
  `class FourShopActiveCourierAgent(MaestroFullPortfolioAgent)` with
  `def __init__(self, params=None, kw_override: int = 10)`. **`Kw = 10` is exactly the
  "do not steer" condition of the value-gate.** The whole test ran with shop steering
  neutralized on both seats.
- Why this is fatal rather than cosmetic: steering targets SMOOTHIE_SHOP, ICE_CREAM_SHOP and
  FARMERS_MARKET — **three of the four strawberry-demanding shops.** On the official-20 steering
  table, 15 of 18 steered seeds targeted a strawberry-demand shop. Steering deliberately
  manufactures the precise market condition under which fertilization pays. Disabling it
  evaluates strawberry fertilization in the world where it is least valuable **by construction**,
  which is also exactly why the "both players sell 100+ strawberries into a crashed AMM"
  root-cause narrative appeared: without a strawberry sink, that is the expected outcome.

**These two features are synergistic and cannot be evaluated independently.** Re-test only once
steering is integrated into `agent/dispatcher_agent.py` (see the HANDOVER §4 correction — it is
currently NOT there, it lives only in `scratch/`), measured against the real steered baseline.

**What survives and should be reused in the next attempt**: the midday-stranding fix (departure
window hours 8-13, return curfew hour 16), the liquidity guard, the corrected four-shop gate,
and the AMM asymmetry reasoning — the parameter citations are correct this time
(`kaggriculture.py:45`, `:41-51`).

---

## 3. Data Extractor & Mechanic Diagnoses

1. **Fixed Phase 0 Extractor & Re-derived Meta Sales Targets**:
   - Fixed `phase0_analysis.py:234` by bounding SELL orders against actual shed inventory `min(qty, step_shed.get(item, 0))` (`kaggriculture.py:642-650`).
   - Ground-Truth Re-derived Meta Sales across top 133k–176k tapes (`rederive_sales_targets.py`):
     - **WHEAT**: 340.3 units (\$14,372.57)
     - **STRAWBERRY**: 84.6 units (\$20,398.57) [Max: 243 units / \$57.5k in strawberry-focused tape]
     - **MILK**: 77.4 units (\$16,326.71) [Max: 227 units / \$47.3k in milk-focused tape]
     - **WOOL**: 60.6 units (\$13,106.86) [Max: 107 units / \$25.4k in wool-focused tape]
     - **FERTILIZER**: 121.0 units (\$10,245.43)
     - **MELON**: 7.6 units (\$1,810.86)
     - **CARROT**: 4.1 units (\$228.57)
     - **EGG / TOMATO**: 0.0 units
   - The prior "286 strawberry target" was an artifact of summing unbounded order requests from unexercised actions.
2. **Systemic Codebase Audit of Shop Mappings**:
   - Audited all shop maps across `fast_engine.py`, `phase0_analysis.py`, `price_model.py`, and `dispatcher_agent.py` against `kaggriculture.py:103-112` and `kaggriculture.py:41-51` via `project_maestro/tests/audit_shop_product_mappings.py`. All mappings verified 100% equivalent.
3. **Corrected 10C/4S/0G Meta Baseline Bounds**:
   - Mean: **\$88,109.11**
   - Median: **\$87,662.00**
   - Min: **\$26,958.00**
   - Max: **\$162,096.00** (overall corpus max across all builds is \$170,964.00).
