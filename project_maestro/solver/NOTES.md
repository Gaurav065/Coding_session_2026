# solver -- NOTES

## ⚠ CORRECTION (2026-08-23): Sections 1-4 below are REJECTED, not accepted

Everything below this notice describes the analytical valuation model's coverage table.
It reads as accepted ("True Competitive Outperformance", specific per-cluster numbers) but
**it was rejected during review and this file was never updated to say so** -- a real gap
against this project's own NOTES.md discipline (record what was rejected and why, so it
isn't silently re-trusted). Fixing that now.

**Why it's rejected**: the model's own `reference_reward` column disagreed with the real
per-cluster reference performance (from `results/meta_portfolio_summary.csv`) on all 15
clusters, and the claimed "Net Edge %" correlated **+0.918** with how much the model
mis-priced its own reference build. Where the model was accidentally close to correct
(3 of 15 clusters, calibrated to within -3.6% to +10.3%), claimed edges were 42-70%; where
it was most wrong (e.g. Cluster_03, understated by 4.01x), the claimed edge was the largest
in the table (+259.4%) -- the "edge" was mostly the calibration error, restated as a result.
Recomputing solved-portfolio scores against real measured cluster performance gave a mean
edge of +41.7%, not the claimed +81.9%, and Cluster_03's real edge was **-10.9%** (the
solved portfolio actually loses to real bots) despite carrying the table's largest claimed
number. See the main conversation log around the "Phase 2: Calibrated Simulation &
Coverage Table Deliverable" and "Phase 2: Calibrated Simulation & Coverage Table
Deliverable, third pass" messages for the full derivation, or re-derive it directly: diff
this file's `reference_reward` values against real per-cluster 10C/4S/0G means.

**Superseded by**: real per-cluster performance is now obtainable directly via the fast
engine (`engine/fast_engine.py`, verified 20/20 exact) instead of any analytical model --
see `eval/cluster_diagnostic.py` for the bucketing approach that replaced this. The
additive-goose claim in particular (section 4.3 below) is unverified for the same reason
and should not be treated as settled; see `agent/NOTES.md` for the (also inconclusive)
real-data evidence on additive geese.

---

## Phase 2 (REJECTED): Calibrated Portfolio Solver & 15-Cluster Coverage Table

### 1. Diagnosis & Resolution of the 4.4x Model Calibration Gap
The initial simplified discrete model scored the 10C/4S/0G reference build at ~\$20k, whereas the Kaggle official dataset shows median **\$87,592** / mean **\$88,109** (N=527).
The exact mathematical root causes identified in `kaggriculture.py`:
1. **CARE pending_care_bonus Multipliers (`kaggriculture.py:823-830`)**:
   - `interval = 2` for Cows: 2 days of feeding + caring accumulates `pending_care_bonus = 2`. Each yield produces **$1 + 2 = 3$ milk** ($3\times$ base).
   - `interval = 3` for Sheep: 3 days of feeding + caring accumulates `pending_care_bonus = 3`. Each yield produces **$1 + 3 = 4$ wool** ($4\times$ base).
   - `interval = 1` for Geese: Daily feeding + caring produces **$1 + 1 = 2$ eggs** ($2\times$ base).
2. **Daily Fertilizer Collection (`kaggriculture.py:831`)**:
   - `tile["fertilizer_available"] = True` every day an animal lives $\implies 1\text{ fert/animal/day}$.
   - For 14 animals over 24 days, $336\text{ units} \times \$60/\text{unit} = \mathbf{+\$20,160}$ additional revenue.
3. **Calibration Validation (`engine/test_calibration.py`)**:
   - Standard clusters (`Cluster_01`, `Cluster_07`, `Cluster_05`) simulate at **\$83.6k**, **\$80.9k**, and **\$89.8k** (within **-0.8% to -3.6%** of real Kaggle empirical averages of \$84.3k, \$83.9k, and \$91.5k).

---

### 2. Capital Feasibility & Phased Acquisition Schedule
- Starting capital: **\$3,000**.
- **Day 0**: Hire 5 farmhands (\$12), buy 4 Cow Pastures + 4 Cows (\$1,600) + 4 Wheat seeds (\$40), holding \$1,348 cash reserve.
- **Days 2–4**: First on-farm wheat harvests arrive, providing 100% internal feed.
- **Day 6**: NE quadrant unlocked (\$1,000).
- **Days 6–10**: Milk/wool/fertilizer revenues reinvested to buy remaining animals and plant cash crop plots.
- **Day 10**: Build 100% complete across all 15 cluster configurations.

---

### 3. Calibrated Phase 2 Coverage Table (`results/phase2_coverage_table.csv`)

| Cluster ID | Solved Asset Mix | Wheat Plots | Cash Crop | Dynamic Crew (D0/Maint/Peak) | Seasonal Labor Cost | Capital Cost | Build Done Day | Solved Reward | Ref Reward (10C/4S/0G) | Net Edge (\$) | Net Edge (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cluster_07** | 16 Cow / 6 Sheep / 8 Goose | 8 | Strawberry (4) | 5 / 6 / 10 | \$2,191 | \$11,800 | Day 10 | **\$115,005** | \$80,868 | +\$34,137 | **+42.2%** |
| **Cluster_01** | 16 Cow / 6 Sheep / 4 Goose | 7 | Carrot (4) | 5 / 5 / 9 | \$1,348 | \$10,600 | Day 10 | **\$119,270** | \$83,616 | +\$35,654 | **+42.6%** |
| **Cluster_09** | 16 Cow / 6 Sheep / 8 Goose | 8 | Strawberry (4) | 5 / 6 / 10 | \$2,191 | \$11,800 | Day 10 | **\$117,319** | \$80,135 | +\$37,184 | **+46.4%** |
| **Cluster_00** | 8 Cow / 6 Sheep / 8 Goose | 6 | Carrot (4) | 5 / 4 / 8 | \$826 | \$8,600 | Day 10 | **\$74,456** | \$36,715 | +\$37,741 | **+102.8%** |
| **Cluster_13** | 10 Cow / 14 Sheep / 4 Goose | 7 | Strawberry (4) | 5 / 5 / 9 | \$1,348 | \$12,200 | Day 10 | **\$106,741** | \$50,083 | +\$56,658 | **+113.1%** |
| **Cluster_11** | 10 Cow / 14 Sheep / 4 Goose | 7 | Carrot (4) | 5 / 5 / 9 | \$1,348 | \$12,200 | Day 10 | **\$104,463** | \$51,456 | +\$53,007 | **+103.0%** |
| **Cluster_14** | 8 Cow / 14 Sheep / 8 Goose | 8 | Strawberry (4) | 5 / 6 / 10 | \$2,191 | \$12,600 | Day 10 | **\$99,879** | \$40,420 | +\$59,459 | **+147.1%** |
| **Cluster_02** | 16 Cow / 14 Sheep / 0 Goose | 8 | Strawberry (4) | 5 / 6 / 10 | \$2,191 | \$13,400 | Day 10 | **\$168,716** | \$93,448 | +\$75,268 | **+80.5%** |
| **Cluster_06** | 16 Cow / 2 Sheep / 4 Goose | 6 | Strawberry (4) | 5 / 4 / 8 | \$826 | \$8,600 | Day 10 | **\$120,594** | \$74,385 | +\$46,209 | **+62.1%** |
| **Cluster_05** | 16 Cow / 14 Sheep / 0 Goose | 8 | Carrot (4) | 5 / 6 / 10 | \$2,191 | \$13,400 | Day 10 | **\$152,937** | \$89,833 | +\$63,104 | **+70.2%** |
| **Cluster_04** | 10 Cow / 6 Sheep / 12 Goose | 7 | Strawberry (4) | 5 / 5 / 9 | \$1,348 | \$10,600 | Day 10 | **\$85,162** | \$44,111 | +\$41,051 | **+93.1%** |
| **Cluster_10** | 12 Cow / 6 Sheep / 8 Goose | 7 | Carrot (4) | 5 / 5 / 9 | \$1,348 | \$10,200 | Day 10 | **\$114,239** | \$62,174 | +\$52,065 | **+83.7%** |
| **Cluster_08** | 16 Cow / 6 Sheep / 4 Goose | 7 | Strawberry (4) | 5 / 5 / 9 | \$1,348 | \$10,600 | Day 10 | **\$138,454** | \$90,608 | +\$47,846 | **+52.8%** |
| **Cluster_03** | 8 Cow / 6 Sheep / 12 Goose | 7 | Strawberry (4) | 5 / 5 / 9 | \$1,348 | \$9,800 | Day 10 | **\$70,503** | \$19,615 | +\$50,888 | **+259.4%** |
| **Cluster_12** | 12 Cow / 14 Sheep / 4 Goose | 8 | Carrot (4) | 5 / 6 / 10 | \$2,191 | \$13,000 | Day 10 | **\$135,604** | \$70,522 | +\$65,082 | **+92.3%** |

---

### 4. Key Takeaways
1. **Calibrated Reference Reproduction**: The reference 10C/4S/0G build accurately replicates real competitive performance (\$80k–\$93k on standard clusters).
2. **True Competitive Outperformance**: Solved cluster portfolios achieve **\$70.5k to \$168.7k**, beating the fixed reference across all 15 demand profiles.
3. **Additive Geese Save Adverse Clusters**: In poor shop draws (`Cluster_00`, `Cluster_03`, `Cluster_04`), additive Geese prevent collapse, delivering **\$70.5k–\$85.2k** (vs \$19.6k–\$44.1k for the rigid reference).

(All three points above are the rejected model's claims -- see the correction at the top
of this file. None are trustworthy as written.)

---

## Phase 2, real attempt: parameterized joint search over the dispatcher's knobs

`param_search.py` and `validate_candidates.py`: real infrastructure (kept, not scratch).
Parameterized `agent/dispatcher_agent.py`'s key knobs (`DEFAULT_PARAMS` dict: cow_cap_low,
sheep_cap, goose_cap, melon_seed_target, strawberry_target, crew_late, crew_mid) --
verified byte-identical to the pre-refactor agent on 4 seeds spanning both the disaster and
best-performing zones, so this is a pure additive capability, not a behavior change.

**Rationale**: three single-variable tests this session (agent/NOTES.md 2b, 2e, 2f) found
that isolated changes can't see resource-contention effects between knobs (capital, crew
attention) -- a joint search over the fast engine can, in principle, since it evaluates
combinations together.

**First-pass result: null, and a genuine overfitting demonstration, not a win.** Random
search, 24 candidates x 15 seeds (20000-20014) via the fast engine, self-play. Top 3
candidates beat the $39,625 baseline on THAT sample by up to +12.5%. Re-validated on the
independent 60-seed set (10000-10059, used throughout this session, known baseline
$49,708/floor $23,077): **all three were actually worse than baseline** -- top_by_mean
$47,748 (floor $15,792, worse), best_floor_and_mean $45,393 (floor $19,798, worse), third
$43,810 (floor $14,982, worse). None adopted; `DEFAULT_PARAMS` in `dispatcher_agent.py`
remains the accepted baseline ($41,917 official 20-seed / $49,708 60-seed fast-engine).

**What this establishes**: 15 seeds is not enough signal for this search space (24
candidates out of a 1,458-combination grid) -- a small-sample "winner" is essentially
noise. It also means the current hand-tuned defaults are more robust than this first-pass
search could beat, which is itself informative: after 4 total attempts today (3 isolated +
1 joint) with only 1 acceptance, the current chassis may be close to a local optimum FOR
ITS OWN architecture. Further gains most likely need either (a) a much larger seed sample
per candidate (expensive: each seed costs a full self-play match) or a smarter search
method (coordinate descent from the known-good baseline, or Bayesian optimization, rather
than blind random sampling), or (b) a structurally different approach -- genuinely
distinct per-cluster archetypes rather than tuning caps within one fixed architecture, or
the RL/shop-steering directions already on the roadmap.

**If revisited**: do not trust any search result validated on fewer than ~40-50 seeds per
candidate given the variance observed here, and always re-validate top candidates on an
independent seed set before adopting -- this session's one real methodological win from
this experiment.
