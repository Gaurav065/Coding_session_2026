# Project Maestro

Goal: a **master agent** for Kaggriculture that is correct across the *entire* town-shop
space, not one path through it — strong enough to train human players against. A master
that does not lose, but makes the student better.

This project starts **fresh**. It inherits no tapes, no prior agents, no prior benchmarks.

## Hard rules (read before writing any code)

1. **Engine source is the only authority.**
   `C:/Users/GauravPatel/AppData/Local/Programs/Python/Python313/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py`
   Verify every mechanic against it with a line reference. Do not trust prose in any
   dossier, handoff, or chat summary — including this file. Re-check before relying.
2. **No tapes.** No recorded/replayed action sequence as a strategy. A tape is a single
   point in the shop space; the thesis of this project is that the answer is a *function*
   over that space.
3. **The old local replay folders are not evidence.** `C:/Coding` holds a mixed bag of our
   own old agents plus assorted bots — not a representative population. They may be used
   *only* as syntactic fixtures for a parser smoke-test ("does this JSON load"). **No
   reported number, table, or conclusion may be derived from them**, and no code may
   default to their path — a missing input must fail loudly instead. Use the official
   public dataset (Phase 0) and self-play. A rule in this file that a default value in
   code quietly contradicts is how this project went in circles before.
4. **Test with `env.run()`**, never manual `env.step()` polling.
5. **One variable at a time**, against a freshly-run baseline on a fixed seed set.
   Independently-positive changes have repeatedly interfered destructively here.
6. **Report failures honestly.** A partial run is not a result. Always state n, and state
   whether the run actually finished.

## Verified engine ground truth

Confirmed against engine source. Line refs are to `kaggriculture.py`.

- **Reward is final money**: `s.reward = float(obs0.farms[s.observation.player]["money"])`
  (963). Any claim that real scores sit near $3,000 is confusing money with Elo rating.
- **720 steps** = 30 days x 24 turns. Starting money $3,000. `shedCapacity` 100.
  `LAND_PRICES = [1000, 2000, 4000]` (97) for NE/SW/SE; NW free.
- **Shed**: personal inventories flush to the shared shed once per day via
  `_drop_inventories_to_shed` (843), called from `_end_of_day` (878). The cap is
  **combined across all products** (`current = sum(v for k, v in shed.items())`) and
  overflow is **silently discarded** (`del inv[item]` runs unconditionally). Seeds are
  tracked separately and never pass through the shed.
- **Town shops** (`SHOPS`, 103): 8 types. One instance drawn **uniformly at random with
  replacement every 3 days**, max 8 total (886-891) — days 3,6,...,24. That is 8^8 =
  16.7M ordered sequences, 6,435 multisets.
- **Shops create scarcity; they do not buy from you.** `_town_consume` (727) runs every
  `townShopSellInterval` = 4 steps and *decrements market inventory* for each instance's
  products; single-product shops use **multiplier 2**. The town center decrements every
  product except FERTILIZER once per day (`townCenterSellInterval` = 24). Prices are an
  AMM in which scarcity raises price — so shop demand is what holds a product's price up.

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

- **Animals** (`ANIMALS`): GOOSE $300 / COOP / first yield day 4 / every day / max_held 4
  / EGG. COW $400 / PASTURE / day 8 / every 2 days / max_held 6 / MILK. SHEEP $500 /
  PASTURE / day 6 / every 3 days / max_held 6 / WOOL. All animals must be fed WHEAT daily
  or they escape after two missed days.
- **Farms are independent.** Tiles are per-player. The *only* coupling between players is
  the shared market and town demand. Production is effectively single-agent optimization;
  only sell timing is genuinely competitive. This is what makes RL affordable here.
- **Nightly wipe**: hands cleared, farmer returned to spawn, `hires_today` reset,
  inventories emptied. Hire cost is Fibonacci with `FARM_HAND_COST_MULT = 1` and resets
  daily, so a full crew each morning costs about $20 — crew size is not a real constraint.
- **`env.run()` syncs `obs["step"]` for both seats.** The `None` step visible in stored
  replay JSON is a serialization artifact of the saved file, not what a live agent sees.

### Two open hypotheses to settle early

- **Melon trap**: melon has the best base value per tile-day ($250 x 0.55) but appears in
  **zero** shop demand lists, so only the town center (-1/day) supports its price. Expect
  collapse under real supply. Quantify before anyone builds a melon line.
- **Goose undervalued**: highest production rate in the game (1.00 unit/tile/day,
  indefinite), cheapest animal, earliest first yield (day 4) — but EGG is demanded only by
  BAKERY and BRUNCH_SPOT. A strong shop-conditional play. Quantify it.

## Architecture

"Cover all shop cases" is not 6,435 tapes. The 8 draws collapse to a **9-dimensional
demand-pressure vector** over products, and that vector determines the optimal portfolio.
The target object is:

    policy(demand_pressure_vector, day, capital, opponent_supply)
        -> portfolio + build/plant schedule + sell timing

Shops reveal progressively (days 3,6,...,24), so the policy must commit under partial
information and re-plan as the vector fills in.

## Phases and gates

| phase | dir | deliverable | gate to pass |
|---|---|---|---|
| 0 | `data/` | analysis of the official public Top Episodes dataset: what the current meta actually plays, which portfolios win, realized price paths | a documented picture of the live meta, from a dated rating-selected sample — not from our old replays |
| 1 | `oracle/` | realized-price model: price vs own supply x shop pressure x opponent supply | predicts held-out prices within a stated error bound; melon/goose hypotheses settled with numbers |
| 2 | `solver/` | per-archetype optimal portfolio. Cluster the 9-d pressure vector into ~15 classes; search animal mix, land timing, crew, sell schedule | a coverage table with a solved portfolio for every archetype, each beating a fixed reference on its own archetype |
| 3 | `rl/` | self-play policy for the adaptive layer only: when to commit as shops reveal, and sell timing against a dumping opponent. Phase-2 solutions seed the curriculum | beats the best static Phase-2 portfolio on mixed archetypes, both seats |
| 4 | `agent/` | distilled deterministic guarded agent + submission bundle | win rate >= target on **every** archetype, both seats, zero exceptions across the full seed set. No archetype may regress. |

`engine/` holds a fast vectorized reimplementation, needed before Phase 3 — 720-step
episodes at ~10s each will not supply enough RL samples. It must reproduce the reference
engine exactly on a fixed seed set before any RL result is trusted.

"Undefeated" is not provable against an unbounded human. The achievable, auditable form is
**no known exploitable shop archetype**, verified per archetype on both seats.

### Score target — calibrated against real data, not aspiration

**A uniform 180k+ floor across all seeds is not realistic. Do not design toward it.**
Verified from `project_doppelganger/ryo_matches_summary.json` — 104 of #1-ranked real
player Ryo Hasegawa's actual matches, extracted directly from real Kaggle replay JSON (no
computation, plain field reads: `ryo_reward`, `opp_reward`, real opponent names, real
episode IDs). His record: 95W-9L. His reward distribution: mean $98,383, median $95,856,
**max $168,259**, min $55,785 — **never once above $168,260 in 104 real games**, let alone
$180,000. His best-ever game is not an outlier we should expect to exceed as a floor; it's
a rare peak even for the strongest real player on the ladder. The wider 1,394-trajectory
official dataset (`results/meta_portfolio_summary.csv`) tells the same story: mean $88,667,
median $87,592, max $170,964, **zero trajectories at or above $180,000 out of 1,394**.
Also worth internalizing: in Ryo's best game ($168,259), his opponent (Atakan Aldemir)
also scored $154,495 in the *same* match — a rich shop draw lifts both competent players
together, it is not zero-sum, so "beat this specific historical score" is the wrong target
shape regardless of its magnitude.

**Realistic target**: push the self-play mean meaningfully above the real top-tier average
($88,667), and raise the floor on adverse shop draws specifically — that is where this
project's agent is currently weakest (see `agent/NOTES.md` 2b-2d) and where real players
clearly still leave value on the table (median wins by real players are often narrow, per
the point above). Treat $140-170k as an achievable *peak* on favorable draws, matching what
real top players actually hit, not as an average or a floor.

**A caution on numbers already in this codebase**: `MASTER_DOSSIER.md` Part 40 (the
"5-route Archetype Grid Benchmark Matrix", peaks up to $180,116) does not disclose its test
opponent anywhere in the surrounding text, and the same document explicitly labels a
nearby, similarly-scaled section as "Vs Starter Agent: 134,703... Vs Random Agent: 130,931"
— i.e. not real opponents. Treat Part 40's table as **unverified and likely inflated**
until someone re-runs those five routes in real self-play or against real opponent tapes
via `env.run()`. Do not design toward its numbers either.

## Folder layout and file hygiene

    data/     Phase 0 public-dataset analysis + derived summary tables
    engine/   fast vectorized engine + its equivalence tests
    oracle/   Phase 1 price model
    solver/   Phase 2 portfolio search
    rl/       Phase 3 training code
    agent/    Phase 4 final agent + submission packaging
    eval/     shared evaluation harness, archetype definitions, seed sets
    results/  committed result tables (CSV/JSON summaries ONLY)
    scratch/  ALL temporary files: debug scripts, logs, partial runs, one-off probes

Rules:

1. Anything temporary goes in `scratch/`. Nothing temporary anywhere else.
2. `scratch/` is emptied at the end of every session — run `python cleanup.py`.
3. `results/` holds only small summary tables. No raw replays, no large binaries, no
   per-step dumps.
4. No file lands in a phase dir until it is the real deliverable. No
   `analyze_this_one_loss_v3.py` sprawl — that pattern is what buried the previous effort.
5. One canonical file per job. If you supersede a file, delete the old one in the same
   change rather than leaving `_v2` / `_backup` / `_old` beside it.
6. Every phase dir keeps a short `NOTES.md`: what was tried, the numbers, what was
   rejected and why — so a failed experiment is never silently re-run.
