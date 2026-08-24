# eval -- NOTES

What was tried, the numbers, and what was rejected and why.
A rejected experiment recorded here must never be silently re-run.

## Competitive intelligence — decoded a real competitor's public notebook (2026-08-23)

User pasted a public Kaggle notebook ("V21-R1 | Public-State Route Portfolio") that packages
its submission as a hash-pinned, base64+zlib-compressed self-materializing `main.py` +
`submission.tar.gz`. Decoded read-only (never `exec()`'d) in
`C:\Users\...\scratchpad\v21r1_decode\` -- outside this project, not copied in here for
copyright reasons. Findings, described structurally (no verbatim source kept in-repo):

- The outer payload itself embeds **three more independently-compressed sub-modules**
  (base85+zlib this time), each `exec()`'d at load into its own module namespace: one
  genuinely-computed strategy ("MOON") and **two literal captured real-match action tapes**
  (their own docstrings self-identify as `ScoreBand-2200-2299-Rank368` and
  `ScoreBand-2600-2699-Rank58` -- i.e. real high-rank replays scraped and replayed step by
  step). This is direct, concrete confirmation of this session's own "80-1800 rank band runs
  tape agents" observation, from an actual top-tier competitor.
- Both tape modules patch two real weaknesses of a frozen tape replayed against a *different*
  seed/opponent than it was recorded on: (1) a **weed-repair check** -- if the tape's next
  scheduled PLANT/BUILD_PASTURE step would land on a tile that is currently a WEED (which
  wouldn't match the original recording), substitute DIG and replay the original intended
  action ~8 steps later; (2) a **front-running sell overlay** -- if a step-ahead scheduled
  SELL's item currently has zero live town demand and there's already enough shed stock, pull
  that sell one step earlier and cancel/reduce the original tape step's sell so it never
  double-counts. Neither patch touches the frozen physical movement/build actions themselves.
- The genuinely-computed "MOON" module independently confirms several mechanics we verified
  this session from the engine source directly: it tracks the same weed/RNG state, keeps its
  own `MARKET_PARAMS`-equivalent price model, and treats STRAWBERRY/MELON/MILK/WOOL as a
  distinct "premium"/glut-prone bucket -- matching our own `GLUT_PRONE` set in
  `agent/dispatcher_agent.py`. It additionally runs a **preemptive selling** scheme (clone a
  future planned sell action early, active only steps 120-680, batches up to 12, clone
  distance up to 6 tiles) and an **adaptive opponent model** with exponential decay
  (0.999/step, evidence-weighted, horizon 6) that we have not built or tested.
- The top-level dispatcher picks between the 3 modules using **only public information**:
  opponent's day-0/1 hires+money (rush detection -> counter-tape), the first 2-3 town shop
  draws (specific shop regimes -> the higher tape or MOON), and a late-game
  (step >= 217) opponent-spend trend that triggers grafting the front-run tape's sell-timing
  delta onto MOON's own actions without adopting the tape's build order. This is the literal
  mechanism behind the notebook's "public-state route portfolio" name.

**Not yet acted on** -- this is intelligence, not a validated improvement. Preemptive
selling and the adaptive-opponent-decay model are candidate techniques worth a real,
independently-validated test (same discipline as every other change in this file); the
weed-repair idea is directly reusable if we ever build a tape-based route ourselves.

## Shop steering — CONFIRMED real and practically exploitable (2026-08-23)

Long-hypothesized (README.md, HANDOVER.md) mechanism, now empirically tested and
confirmed: `_end_of_day` builds one RNG per day, consumes it via `rng.random()` once per
EMPTY tile across BOTH farms during weed-spawn, then calls `rng.choice(SHOP_NAMES)`.
`shop_steering_probe.py` sweeps our own planted-tile-count K (0-24, the farmable non-shed
NW tiles before any land purchase) against a fixed all-PASS opponent, for 3 seeds, and
records the shop drawn at the first unlock (day 3).

**Result: fully deterministic and genuinely exploitable, not just theoretically true.**
Different K reliably produce different shops for a fixed seed, and there is real
redundancy -- multiple K values often land the same target shop, giving execution slack:

- seed 42: YARN_STORE only at k=9 (narrow); ICE_CREAM_SHOP at k in {2,13,14,15,16} (robust).
- seed 100: YARN_STORE at k in {9,10,11,13} (robust); ICE_CREAM_SHOP only at k=19 (narrow).
- seed 777: SMOOTHIE_SHOP at k in {11,20,21,22,23,24} (very robust); YARN_STORE at k in {0,15}.

The mapping is NOT monotonic or simple (expected -- it's PRNG state advancement, not a
designed function), but it is a fixed, computable lookup per seed: same K always gives the
same shop, since the engine is deterministic. Confirmed identically in `engine/fast_engine.py`
(already verified 20/20 exact vs the reference engine) and by direct code reading of
`kaggriculture.py:145-158` for the LOCKED-vs-None tile semantics this depends on.

**Real limitation, not yet resolved**: this probe holds the opponent at all-PASS (fully
known occupancy) to isolate the mechanism cleanly. In a real match, the opponent's
occupancy contributes to the SAME RNG stream, so precisely targeting a shop needs either
(a) a self-play mirror, where both farms run the identical agent and therefore produce the
identical occupancy, making the outcome jointly computable, or (b) a *known* opponent
tape/build order, letting us compute their occupancy contribution and solve for the K that
gives us the shop we want. Against a genuinely unknown adaptive opponent, our own K still
shifts the outcome, but not precisely -- we'd need to pick K values that are robust across
a plausible range of opponent occupancy rather than targeting one exact shop.

**Why this matters**: this connects directly to the tape-detection idea (identify a known,
non-adaptive opponent build early in a match, per the "80-1800 rank band mostly runs tapes"
observation) -- detection plus this steering mechanism together would let the agent both
predict AND partially choose the shop draw against exactly the opponent population where
it matters most.

## First attempt at an in-agent controller (`steering_test.py`) — INCONCLUSIVE, not rejected

Tried to build the end-to-end validation the note above calls for: a wrapper that
redirects otherwise-idle unit actions during days 0-2 into extra NW_WHEAT plantings
(chosen because the real agent already intends to plant those tiles regardless -- no
conflict with COW_PASTURES/GOOSE_COOPS animal-placement logic, which needs tile is None).
Deliberately additive-only and safe: never displaces a real decision, only fills moments
where the wrapped agent would otherwise PASS.

Caught and fixed one real bug along the way: the first version intercepted
`action["farmer"]`, but NW_WHEAT is planted by dedicated crop-crew HAND units (`hands[3]`,
`hands[4]`, corresponding to u_idx 4/5 in `dispatcher_agent.py`'s sector_tasks
assignment), not the farmer (u_idx 0, animal-sweep crew). Confirmed via direct
instrumentation that the farmer-targeting version's override branch did fire but on the
wrong unit, so it never accumulated the multi-turn control needed to complete a
walk-then-plant sequence -- explaining the observed exact no-op across all extra_k values
and 100 seeds (mean/median/min/max AND the day-3 shop distribution all byte-identical).

**After retargeting `hands[3]`, still an exact no-op** -- but for a different, more
fundamental reason, confirmed by direct instrumentation (traced hands' actions turn by
turn for seed 42): **`hands[3]` and `hands[4]` are never idle during days 0-2.** They are
continuously moving toward, watering, or planting NW_WHEAT tiles the entire window --
10 tiles is enough work to keep 2 dedicated units busy for the full ~48-72 hours available.
There is no idle moment to redirect. This is itself a real, useful finding: **the current
agent's early-game crew already has essentially zero slack during days 0-2**, so a purely
additive ("only fill gaps, never displace anything") steering controller has no room to
operate against this specific agent, regardless of extra_k.

**Not rejected, because the real hypothesis was never actually tested** -- "does steering
the day-3 draw improve the score" still has no evidence either way; what was tested and
failed was one specific *implementation* (additive-only, no displacement). A genuine test
needs a controller willing to accept a real cost: delay one existing water/plant action by
a turn to fit in a steering plant instead, and measure whether the resulting shop-draw
benefit outweighs that small displaced-action cost. That is a materially larger
implementation than what's built here (real decision logic, not just PASS-filling) and
was not attempted in this session given the size of investment already made on this one
mechanism -- multiple diagnostic rounds, a full N=100 run that turned out to be entirely
inert twice, before the root cause was found. If revisited, build the displacement-capable
version directly rather than another additive-only variant; the additive approach is now
demonstrated to have no room to operate in this agent's current early-game structure.
