# data -- NOTES

## Phase 0: Official Kaggle Dataset Meta Analysis (Completed & Verified)

- **Dataset**: Official Kaggle competition dataset (`kaggriculture-episodes-index` and `kaggriculture-episodes-2026-08-21`).
- **Execution**: Run in-place on Kaggle cloud kernel (`gaurav065/project-maestro-phase-0-analysis`), exporting summary CSVs directly to `project_maestro/results/`.
- **Sample Size**: **$N = 697$ distinct full 720-step episodes ($1,394$ player trajectories)**.

---

### 1. Reward & Cash Distribution in Real High-Tier Matches (engine:963)
- Mean Reward: **\$88,666.7**
- Median Reward: **\$87,592.0**
- 25th Percentile: **\$69,803.8**
- 75th Percentile: **\$105,509.3**
- Min / Max: **\$26,555.0 / \$170,964.0**

---

### 2. Labor & Crew Size Distribution (kaggriculture.py:99-101, 539)
- **Day-0 Hires**: Mean 4.92, Median **5 hands** (1,109 / 1,394 trajectories hire exactly 5 on Day 0; 124 hire 4; 80 hire 6).
- **Total Lifetime Hires**: Median **277.0 hires** ($\approx 9.2\text{ hands/day}$ average crew size), 90th percentile = 298.0, Max = 318.0.
- Daily hire cost Fibonacci with $\text{FARM\_HAND\_COST\_MULT} = 1$: 6 hands = \$20, 10 hands = \$143, 12 hands = \$376.

---

### 3. Macro Meta Portfolio Distribution Across 1,394 Trajectories
| Observed Animal Portfolio | Trajectory Count | % Share of Field | Mean Reward | Max Reward | Meta Characteristic |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10 Cow / 4 Sheep / 0 Goose** | **527** | **37.8%** | \$88,109 | \$162,096 | Dominant opening baseline across public bots |
| **6 Cow / 12 Sheep / 0 Goose** | **181** | **13.0%** | \$94,447 | \$143,344 | Heavy wool/sheep expansion build |
| **8 Cow / 6 Sheep / 0 Goose** | **110** | **7.9%** | \$73,996 | \$130,675 | Legacy animal variant |
| **6 Cow / 8 Sheep / 0 Goose** | **73** | **5.2%** | \$93,775 | \$143,275 | Balanced pasture build |
| **9 Cow / 4 Sheep / 0 Goose** | **58** | **4.2%** | \$88,499 | \$149,559 | Derivative variant |
| **6 Cow / 6 Sheep / 2 Goose** | **29** | **2.1%** | \$74,846 | \$108,742 | Rare mixed coop variant |
| **11 Cow / 4 Sheep / 0 Goose** | **18** | **1.3%** | **\$106,040** | \$146,311 | Aggressive cow-heavy variant |

#### Goose Cohort Analysis:
- Total trajectories with $\ge 1$ Goose: **102 / 1,394 (7.3% share)**.
- Goose cohort win rate: **56.9% Win Rate** vs 49.1% for non-goose trajectories (+7.8% win-rate premium), despite lower mean money (\$77,647 vs \$89,537).
- Confounding Factor: Current meta builds substitute cows for geese (e.g. 6/6/2 vs 10/4/0). Additive goose testing in `solver/` is required.

#### Density & Land Expansion Inefficiency:
- Median total animals per trajectory: **14** (max 26) on 100 available grid tiles.
- **82.5% of trajectories never unlock the SE quadrant**, leaving 25 tiles unexploited.

---

### 4. Demand Pressure K=15 Clustering (`demand_profile_outcomes.csv`)
Standardized 8-d non-fertilizer pressure vectors clustered into $K=15$ balanced archetypes:
- Cluster count: exactly **15 clusters**.
- Cluster sizes: **Min = 31, Max = 65, Median = 46** (zero clusters under 30).
- Outcome variation: Average player reward ranges from **\$60,412.9 (Cluster 00)** to **\$127,156.2 (Cluster 08)** across different shop demand profiles.

---

## ⚠ REJECTED: "re-derived meta sales targets" from local tapes (2026-08-24)

`data/rederive_sales_targets.py` was written to re-derive Phase 0 sale targets after the
`phase0_analysis.py:234` unbounded-SELL-qty fix. **Its output must not be used.** It violates
four separate standing rules at once, and its headline claim is wrong:

1. **Forbidden corpus.** It hardcodes 7 paths under `C:\Coding\kaggriculture-agent\`
   (`best_tape_143k.json`, `second_best_tape_133k.json`, `top_tape_143954.json`, …).
   README rule 3: "No reported number, table, or conclusion may be derived from them, **and no
   code may default to their path — a missing input must fail loudly instead**." This script
   both defaults to those paths and fails *silently* (`if not os.path.exists: return None`).
2. **Those tapes are our own old agents**, not the meta. Labelling them "top meta action tapes"
   is wrong — several are literally prior Maestro/kaggriculture-agent output.
3. **All-PASS opponent** (`# Replay tape for Player 0 (and empty PASS for Player 1)`) — a
   closed door per HANDOVER §6, and it removes all market contention, so realized prices are
   inflated relative to any real match.
4. **Every tape replayed on `FastGame(seed=0)`** regardless of the seed it was recorded on.
   Shop draws and weed spawns are seed- and occupancy-dependent, so the tape's actions execute
   against a world they were never recorded for and desync. This is the most likely explanation
   for the implausible spread in the output (strawberry min=1, max=243, mean 84.6 across N=7).

**The claim "the previous 286 strawberry target was an artifact of summing raw unexercised
order requests" is false.** 286 was a **median** over 1,394 official-dataset trajectories, and
HANDOVER §3 already assessed medians as robust to that bug — the bug inflated the *means*
(strawberry 7,945, milk 7,877), which is exactly why the medians were the figures adopted.
Replacing a 1,394-trajectory median with a 7-tape mean from a forbidden corpus is a large step
backwards in evidence quality, not a correction.

**What is still genuinely open:** the `phase0_analysis.py:234` fix itself looks correct, but it
has **not been re-run on the official Kaggle dataset**, which is the only valid source for these
targets. Until it is, the pre-existing official-dataset medians (wheat 856, strawberry 286,
milk 279, wool 139, melon 72) remain the best available numbers, with the known caveat that
fertilizer's 2,750 is an artifact against a ~336 physical ceiling.
