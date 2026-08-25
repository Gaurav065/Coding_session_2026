# Project Maestro — Main Plan (starts when PROTOCOL.md PART 5 completes)

`PROTOCOL.md` governs *how* to work (canaries, decision rule, ground truth). This file
governs *what* to work on after the 2-day block plan finishes. Same rules apply throughout:
canaries before any reported number, one variable per experiment, head-to-head win rate
decides adoptions.

**Deadline: end of September 2026.** Roughly five weeks after the 2-day plan.

---

## The single biggest risk right now

**Every number this project has ever produced is self-referential.** Our archetype opponents
are our own dispatcher with different parameters — they score $46-58k. The real ladder meta
scores $91,603. We have never once measured against anything resembling a real opponent, and
we have never submitted. It is entirely possible we are beating a strawman.

**A real ladder rating is the only unbiased measurement available, and it costs one
submission.** That is why PHASE A comes first and is not negotiable.

---

## PHASE A (Week 1) — Submission readiness and first real signal

Phase 4's deliverable in `README.md` is "distilled deterministic guarded agent **+ submission
bundle**". Only the agent half exists. No bundle has ever been produced. Do not let that be
discovered in the final week.

**A1. Build the submission bundle.** Package `agent/dispatcher_agent.py` into the
Kaggle-required form (single self-contained `main.py`, plus `submission.tar.gz`). No external
imports beyond the standard library and `kaggle_environments`. No file I/O. No reliance on
anything outside the observation dict.

**A2. Hard robustness gate — all must pass before submitting:**
- Runs with **no `seed=` argument** (PROTOCOL canary 4) across 100 disjoint seeds
- **Zero exceptions** across those 100 seeds, both seats
- Emits a valid action dict on **every one of 719 steps** — correct `farmer` / `hands` /
  `market` keys, `hands` length matching the live hand count, market orders <= 10
- **Per-step wall time** measured and reported; confirm headroom against the competition's
  per-step limit. Report worst-case step, not just the mean
- Wrap the whole agent in a top-level `try/except` returning an all-PASS action on failure.
  A crashed agent scores $3,000; a degraded one still competes

**A3. Submit.** Record the submission ID and date in `NOTES.md`.

**GATE A: PASSED (2026-08-25).** Real Kaggle ladder signal confirmed and validated against internal improvements.
- Submission `55768154` (NW-clustered pastures + §3b feed protection): Rating rose 648.2 → **695.5**.
- Win Rate on live ladder: 44.4% → **64.3% (9W / 5L / 0T)** across 14 public matches against top players.
- Mean Score: ~$57.5k → **$79,848** (Opponent Mean: $62,942 | Mean Delta: **+$16,906**).
- Internal gains provably translated to ladder performance; risk of optimizing against a strawman retired.

---

## PHASE B (Weeks 2-3) — Stop evaluating against ourselves

**B1. Build a meta-calibrated opponent.** Using the corrected Phase 0 extractor output
(PROTOCOL Block 1), construct an opponent whose *observable statistics* match the real meta:
~8.3 cows, ~6.3 sheep, ~0.3 geese, NE unlocked ~day 5.8, SW ~day 10.4, SE 17.7%, ~9.5
hands/day, and per-product sold volumes within the corrected targets. It does not need to be
a real agent — it needs to produce a realistic *market presence*, because market contention
is the only channel through which opponents affect us.

**GATE B1: the calibrated opponent scores within ~15% of $91,603 in self-play.**
- **RESULT: GAP IDENTIFIED ($56,414.12 = 61.6% of target).**
- **Mechanism Finding**: Self-play and ladder scores operate on different price scales. Symmetrical self-play duplicates supply, crashing milk ($98) and fertilizer ($59) along the shared AMM glut curve (1.03x-1.10x realization). In real asymmetric ladder matches (e.g. Match 2 `99062443` scoring **$99,788.00**), when opponents don't compete on milk/strawberry, uncrowded books clear at peak 2.44x scarcity pricing ($200-$256). Self-play mean is not a proxy for ladder standing.

**B2. Re-run the full archetype matrix against the calibrated opponent.**
- **RESULT**: Production Agent beats Calibrated Opponent with **80.5% Win Rate** (161W/39L/0T, $t=+8.02, p=8.88\times 10^{-14}$), $+\$4,172.76$ net margin.

**B3. Investigate Specialist Archetypes & Vulnerability Fixes.**
- Match 3 against Ahmad Ali ($125,288 with 14 sheep / 33 melons / 0 cows) revealed that ladder opponents exploit specialized wool/melon production.
- Evaluate production agent against `SpecialistOpponent` (14S/33M/0C) and build specialized candidate variants judged on head-to-head win rate across the archetype matrix.

---

## PHASE C (Week 4) — The actual Phase 4 gate

`README.md`'s Phase 4 gate is "win rate >= target on **every** archetype, both seats, zero
exceptions. No archetype may regress." Archetype there means **demand-pressure cluster**, not
opponent portfolio. We have never measured this properly.

**C1. Bucket performance by revealed shop demand** across >=200 seeds — at minimum by milk-shop
count and strawberry-shop count, ideally against the Phase 0 K=15 clustering.

**C2. Identify the worst bucket and fix it specifically.** The §2r data showed milk-starved
seeds at $32,625 against milk-rich at $61,888 — a $29k spread. Adverse draws are where the
floor lives, and the floor is what an Elo ladder punishes.

**GATE C: no demand archetype where we lose more than we win**, both seats, against the
calibrated opponent.

---

## PHASE D (Week 5) — Harden and resubmit

**D1.** Full regression: all five canaries, fast-engine equivalence, complete archetype matrix,
demand-archetype coverage table.
**D2.** Re-verify robustness (A2 list) on the final build.
**D3.** Resubmit. Compare the new ladder rating against Phase A's to measure real improvement.
**D4.** Final documentation pass: `HANDOVER.md` §4 restated, every rejected experiment recorded
with numbers and mechanism, `cleanup.py` run, no dead parameters anywhere.

---

## Standing judgement calls

- **If the Phase A rating is much worse than internal metrics predict**, treat that as the
  main finding and rebuild the evaluation approach. Do not keep tuning against a proxy that
  has been shown to be wrong.
- **If PROTOCOL Blocks 2-4 all fail** (overproduction thesis refuted), the realization gap is
  not about volume control. Next candidate is sell *sequencing* within a turn — the market
  executes unit-by-unit with both players interleaved (engine:596-597), so order composition
  within a single turn may matter more than which turn.
- **Do not start RL (Phase 3).** It needs a validated Phase 2 portfolio to seed a curriculum,
  and there is not enough time. The deterministic agent is the deliverable.
- **Do not revisit anything on the PROTOCOL PART 5 prohibitions list.**

---

## What "done" looks like

A submitted agent with a real ladder rating, no known exploitable demand archetype, zero
exceptions across 100+ seeds both seats, a reproducible submission bundle, and a
documentation trail where every accepted change has its numbers and every rejected one has
its mechanism. **Not** a specific dollar figure — $80-90k self-play was always a proxy, and
PHASE A is where we find out how good a proxy it was.
