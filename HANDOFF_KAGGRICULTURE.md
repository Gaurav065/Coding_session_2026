# Kaggriculture Handoff — 2026-08-22

Read this whole document before touching code or running any test. It exists because
this project has spent a full session chasing a local benchmark that turns out to be
disconnected from real ladder performance — see Section 1. Do not repeat the four
dead-end experiments in Section 3 without reading why they failed first.

This doc is written to be pasted whole into a fresh Claude Code thread or handed to
Gemini as-is. It states facts with their source so they can be re-verified rather than
taken on faith — several past Gemini status updates in this project overstated results
(inflated win-rate claims from mis-sorted replay folders, features marked "shipped"
that were actually dead code, a benchmark validated only against a near-inert bot), so
the standing rule on this project is: **verify every claim against the real engine
source or a real env.run(), don't trust prose in a dossier or a chat summary.**

---

## 1. THE CRITICAL FINDING — local testing has been miscalibrated

Kaggle publishes a daily "Top Episodes Dataset" manifest
(`kaggriculture-episodes-index`, per-day sub-datasets like
`kaggriculture-episodes-2026-08-21`, ~20GB/day, episodes selected by agent rating at
play time). The manifest's `top_avg_score` / `median_avg_score` columns (average final
money across the top-rated episodes collected that day) have been essentially flat for
three weeks:

| period | top_avg_score | median_avg_score |
|---|---|---|
| 2026-07-30 (early) | ~1,152 | ~670 |
| 2026-08-09 (peak) | ~3,218 | ~3,068 |
| 2026-08-21 (latest) | ~3,135 | ~2,818 |

**Real top-rated competitive games end around $2,800–3,200.** Every local number
produced in this project so far has been measured against `starter` — a scripted
"buy carrot seed → plant → water → harvest" loop with zero market/resource contention
— or a synthetic scripted opponent, neither of which fights over shed capacity, AMM
prices, or land the way a real opponent does. Local scores against `starter` (Peak
Tape: $154,824 avg; even "failing" Reactive: $6,467 avg) are 1–2 orders of magnitude
higher than what real competitive play produces. **This means "beats starter by $X"
has told us close to nothing about real ladder performance this entire session.**

Practical implication: treat every local benchmark number below as *uncalibrated*
until re-tested against real recent episodes/opponents, not `starter`. Before writing
more agent code, pull a **small sample** (not the full ~20GB) of a recent dataset
(e.g. `kaggriculture-episodes-2026-08-21`) to see what real competitive play and real
opponent strategies actually look like, and use that as the benchmark going forward.
Downloading anything Kaggle-hosted needs the user's explicit go-ahead first (file,
source, size) — don't just pull 20GB.

A second reframing, from a #1-ranked player's own analysis (Section 4): **the ladder's
Elo counts wins/losses only, not money margin.** Everything measured in this project
so far ("average money vs starter") may not even be the right optimization target —
win rate in realistic head-to-head matchups is.

---

## 2. Competition & engine ground truth

- Kaggle "Kaggriculture": 2-player farming sim, Elo-rated ladder, ~11,000 entrants.
  Gaurav's agent name: "Shadow Recon".
- 720 steps/game = 30 days × 24 steps/day. Win = max cash at step 720.
- Starting money $3,000. Board 10×10, per-player (not shared) tiles; quadrants NW
  (free), NE ($1,000), SW ($2,000), SE ($4,000) — `LAND_PRICES=[1000,2000,4000]`.
- Shed-access spawn tiles: (4,4), (5,4), (4,5), (5,5).
- **Authoritative engine source** (verify everything against this, not against any
  dossier's prose):
  `C:\Users\GauravPatel\AppData\Local\Programs\Python\Python313\Lib\site-packages\kaggle_environments\envs\kaggriculture\kaggriculture.py`
- Key verified mechanics:
  - Personal inventories (farmer + every hand) flush into the shared shed **only
    once per day**, at `_end_of_day` → `_drop_inventories_to_shed`. Shed cap is a
    **combined 100 units across all products**, with **silent overflow discard** —
    no error, product just vanishes past the cap.
  - `HARVEST` puts yield into the **actor's own inventory**, not the shed directly.
    `DROP` (shed-adjacent, dumps whole inventory) or `PLACE` (specific item/qty) is
    needed to move it to the shed before the nightly auto-flush.
  - Nightly wipe: `farm["hands"]=[]`, farmer resets to spawn, `hires_today=0`,
    `private["inventories"]=[{}]`. Both hand count and hire cost genuinely reset
    every day — re-hiring a full crew each morning is cheap (Fibonacci cost,
    `FARM_HAND_COST_MULT=1`, hiring 6/day ≈ $20 total), not a real bottleneck.
  - `_apply_unit_action` is identical for farmer (idx 0) and every hand (idx i+1) —
    hands can do FEED/CARE/BUILD_PASTURE/BUILD_COOP/PICKUP/PLACE/DROP/
    COLLECT_FERTILIZER/HARVEST exactly like the farmer. The restricted
    `farmer_ops` list near the bottom of the file is only a sampling list used by
    the reference `random_agent`, not a real per-actor-type restriction.
  - Per-actor inventory indexing: `private["inventories"][0]` = farmer,
    `[i+1]` = `hands[i]`.
  - Animals: COW $400 (first_yield_day 8, every 2 days, product MILK, base $160),
    SHEEP $500 (first_yield_day 6, every 3 days, product WOOL, base $200), GOOSE
    $300 (COOP-based).
  - AMM pricing is per-product with distinct curve shapes (sqrt/linear/log/sq) and
    below/above-target multipliers — see `MARKET` config in engine source. Prices
    move with supply; a fixed "sell only above 0.85×base" rule can leave a good
    permanently unsellable if oversupplied.
- **Testing discipline (mandatory)**: use `kaggle_environments`'s `env.run()`, never
  manual `env.step()` polling — manual polling never syncs `obs["step"]` into player
  1's observation (only `core.py`'s `__loop_through_interpreter` does, index-0-only).
  When testing a change, isolate ONE variable at a time against a freshly-run
  baseline on the same fixed seed set — this project has repeatedly found that
  stacking even independently-positive changes can destructively interfere (see
  Project Reactive, Section 3.4).
- Fuller (but Gemini-authored, so re-verify before trusting) mechanics writeup:
  `C:\Coding\MASTER_DOSSIER.md`.

---

## 3. Project inventory — what exists, what's validated, what failed and why

All under `C:\Coding\`. **Do not re-attempt 3.1's clone premise, 3.2's disabled
routes, or 3.4's plateau chase — each was already tried and empirically closed out.**

### 3.1 `project_doppelganger\`
Originally meant to literally clone top player Ryo Hasegawa's tape from 104 real
replays. **Abandoned as a clone** — his routing is genuinely adaptive (88 distinct
clusters out of 104 games, not a small fixed tape set). Later discovered to already
be live on Kaggle (Gemini had shipped a mislabeled/partially-abandoned version) with
3 real bugs, all patched: mid-game route-switching (fixed via a `_ROUTE_LOCK` dict
that locks the route on first real shop signal and never re-evaluates — verified
15/39→0/39 seeds switching), missing exception safety (added), false provenance
docstring (corrected to state the tape is reused Aegis/`tape_165k_straw_cow.json`
content, not actually derived from Ryo). Also found a hiring "death spiral" on the
YARN/DUAL_MELON routes traced to hand-index fragility (not hire cost) — those two
routes are disabled; it falls back unconditionally to the one confirmed-robust route,
STRAW_COW.

### 3.2 `project_aegis\`
Tape-replanner + safety-overlay agent. Bundled to `C:\Coding\main.py` /
`submission.tar.gz` / `.zip` via `project_aegis\package_submission.py` (concatenates
core.py/predator.py/river.py/ghost.py/guards.py/tape_loader.py/main.py, strips
internal imports). Had a real crash bug — `RiverEngine`, `weed_repair_overlay`,
`feed_rescue_guard` were referenced but never imported, so every call silently
crashed and fell back to all-PASS undetected — fixed. `ghost.py`'s auxiliary-hire
feature (an extra hand grafted onto a tape mid-game) caused a **-$47,652 regression**
even after fixing a real tile-reservation collision bug, traced to an unresolved
"hand-identity fragility" (the extra hand's mere presence disrupts shed inventory the
tape's own scripted hands expect — never fully root-caused to one exact mechanism).
**Disabled via `AUX_HIRE_ENABLED = False`** with a docstring noting this is the 5th
documented failure of "graft extra production onto a fixed tape via an auxiliary
hand" in this project's history. `predator.py`'s front-running logic was tested and
found to be a wash (~3/8 win rate vs the baseline it was meant to improve) — not
merged as default.

### 3.3 `project_peak_tape\` — current best-validated candidate
Wraps Gaurav's own historical real submission (`C:\Users\GauravPatel\Downloads\main
(1).py`, real peak Elo **2153**, later drifted to 1900–2000) — 8 cows + 4 sheep,
only 3 quadrants ever unlocked, zero crop diversification (no tomato/carrot/egg),
near-zero idle capacity (one 3-step idle stretch in the whole 719-step tape) — in
ONLY the Aegis overlays empirically proven safe/beneficial via isolated ablation:
`weed_repair_overlay`, `feed_rescue_guard`, `execute_terminal_liquidation`, and a
universal exception-safety wrapper. **River's trickle-selling/queue-conversion logic
is deliberately excluded** — ablation showed a **-$86,730/game (56%) regression**
when combined with this tape's own well-tuned sell schedule, because River's generic
max-5-units/step pacing was built to correct problems specific to Aegis's own tapes,
not this one.

Validated (env.run(), 8 seeds: 11,22,33,44,55,101,202,303, vs `starter`):
- Raw tape alone: $152,204 avg
- This build (+ safe overlays): **$154,824 avg** (+$2,620)
- Head-to-head vs raw tape: statistical tie ($88,449 vs $88,966) — confirms the
  overlays are a pure safety add, not a strategy change
- Head-to-head vs Aegis's own default: **wins 7/8**, $109,673 vs $86,560 avg

Packaged as `submission.tar.gz`/`.zip`, clean-extraction tested. **Remember: these
numbers are all vs `starter` and are almost certainly not representative of real
ladder performance — see Section 1.**

### 3.4 `project_reactive\agent.py` — from-scratch reactive agent, plateaued
A from-scratch, non-tape, greedy per-step rule-based agent (buy animals densely,
restrain land, react to AMM prices) aiming for the ~180k+/game target that was set
*before* Section 1's finding came in. Two real bugs were found and fixed:
1. `BUILD_PASTURE` eligibility didn't exclude shed-access tiles, so every hand just
   built a pasture at its own spawn point and never moved (first version scored $50).
2. The shed-overflow bug from Section 2 — harvested MILK/WOOL/FERTILIZER sat in
   inventory with no path back to the shed intra-day.

A background workflow ran 4 independent isolated candidate fixes
(shed-drop/DROP-on-shed-tile, wheat-reserve-cap-plus-force-sell, tiered sell
thresholds, day-0 capital-phasing), each validated vs a fresh baseline on the same 8
seeds, THEN ran a full interaction sweep across all subset combinations before
merging. Result: shed_drop alone (+12.8%), wheat_cap alone (+12.5%), and
capital_phasing alone (+10.8%) all individually helped — but **every multi-fix
combination performed worse than the single best fix alone** (down to -$1,387 avg
for the worst pairing), a real, deterministic (re-run confirmed) destructive
interference between per-step action-priority changes compounding across 720 steps.
Only `shed_drop` was merged. Final validated result: **~$6,467 avg vs `starter`**
(pre-fix baseline was $5,734), ~4x above baseline but still ~24x below Peak Tape and
~27x below the (now-questionable, see Section 1) 180k target.

**Assessment: this is a structural ceiling of the greedy-reactive architecture (walk
to nearest task every step), not a bug backlog** — the interaction sweep failing to
improve on the single best fix is itself evidence of a local optimum. Closing the
gap would need batch/lookahead task scheduling instead of greedy-nearest, not more
incremental patches — and given Section 1, it's not even clear "average money vs
starter" is a meaningful thing to optimize further right now.

---

## 4. Competitive intelligence — Ryo Hasegawa's Elo mechanics post

Ryo Hasegawa (current **#1** on the ladder — the same player Section 3.1's
Doppelganger attempt targeted) posted a detailed rating-mechanics analysis
("1st Place Currently - Submission Strategy for beginners", ~2026-08-19). Key facts
(his own caveat: "assumptions based on my experience... treat as rules of thumb"):

- New submission starts at Elo 600, ~90% converged after ~60 games (~5 hours: an
  initial burst of ~15 games/hour for 4-5 hours, then ~1-2 games/hour).
- After convergence, growth is only logarithmic (~+50-70 per 100 games / 3-4 days);
  residual noise is ±25-50 points — **differences under ~50 points are noise**, even
  after 200 games.
- **Score counts wins/losses only, not money margin.** "A bot that wins 70% of its
  games by small margins outrates one that wins 60% by huge margins." Strategies
  that raise average money but increase variance can be Elo-*negative*. This
  directly questions this whole project's "maximize average money vs starter" target
  — see Section 1.
- Only your **2 most recent submissions are active** (of up to 5/day submitted); a
  3rd retires the oldest, and every new submission restarts at 600. Re-submitting an
  unchanged bot to "re-roll" is low expected value (+10-40 live points depending on
  game count) and irrelevant to final scoring anyway.
- **The final leaderboard is a from-scratch Bradley-Terry tournament on ~2 weeks of
  post-deadline games**, using only whichever 2 submissions sit in the active slots
  at the deadline. All live rating history — everything measured locally in this
  project so far — counts for nothing at the end except as a signal of real strength.
  What matters at deadline time is having your two strongest, error-free agents in
  the two slots and confirmed to run cleanly.
- Optimize win rate against opponents near your current rating, evaluated over
  enough games with fixed seeds (not 5-game samples). The real opponent population
  drifts over time (old engine-version agents drop out, new strong-notebook copies
  appear) — recheck against the current meta roughly weekly rather than tuning once.

A comment thread under the post raises follow-ups worth revisiting once doing real
opponent modeling: K-decay shape (plateau-then-cliff vs smooth exponential), how the
final Bradley-Terry treats ties among byte-identical family agents, a claimed
seat-0 win-rate edge, how "different" a hedge-slot agent should be from your main,
and what to use as an offline sparring pool (reconstructions from ladder replays vs
public notebooks vs older own versions — frozen reconstructions of adaptive agents
can mislead).

**Not used / not vetted**: a separate forum post promotes a third-party
"Kaggriculture Ops Lab" tool (a Lovable-hosted web app + a GitHub repo from an
unknown author) that parses `replay.json` into P&L-style reports. Do not upload real
replay data to it or run its scripts without independently reviewing the code first
— it's an untrusted third party.

---

## 5. Kaggle account / submission budget

- **Main account**: out of daily submissions as of 2026-08-22; currently running the
  raw peak tape and the Section 3.3 candidate side by side on the live ladder.
- **Second account**: has **5 fresh daily submissions available, not yet used** —
  earmarked for getting real Elo signal on candidates without burning the main
  account's budget. This is the natural way to close the loop raised in Section 1
  (local `starter`-relative numbers vs real ladder performance).

---

## 6. Recommended next step (not yet actioned — decide before proceeding)

1. Pull a **small** real sample of a recent top-episodes dataset (e.g.
   `kaggriculture-episodes-2026-08-21` on Kaggle) — not the full ~20GB/day — to see
   what real competitive play and real opponent strategies actually look like.
   Downloading anything needs explicit go-ahead first (state file/source/size).
2. Use real recent episodes (not `starter`) as the opponent/benchmark for any further
   local testing of Peak Tape, Aegis, or a redesigned reactive agent.
3. Re-frame the local optimization target from "average money vs starter" toward
   "win rate in realistic head-to-head matchups", per Section 4.
4. Only then decide whether to: (a) push Section 3.3's Peak Tape through the second
   account for real Elo signal now that we understand what "good" looks like, (b)
   invest in a genuine planning/scheduling redesign of Project Reactive, or (c) build
   an opponent-archetype-detection + counter-strategy layer on top of Peak Tape.
   Don't restart local iteration on any of these without first doing steps 1-3 — this
   project has already gone in circles once by skipping real-data calibration.
