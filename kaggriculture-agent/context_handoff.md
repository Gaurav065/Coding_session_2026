# Agent Context Handoff — Aug 12, 2026

## 1. Goal and Domain
We are building an automated agent for the **Kaggriculture** Kaggle competition. The agent operates a farm in a 30-day simulated economic environment with dynamic market pricing, exponential labor scaling (Fibonacci hiring costs), crops, and animals. The goal is to maximise final asset value (money + shed contents + farm value).

## 2. Architecture Overview
- **Single file**: `src/main.py` (~1800 lines)
- **Key functions**: `build_plan()` → `market_orders()` → tile actions
- **EV Engine**: `compute_crop_mav_exact()` and `compute_animal_mav_exact()` provide exact expected-value calculations with proper action cost accounting (feed, care, harvest, collect)
- **Strategic Layer**: `run_strategic_mcts()` + `apply_strategic_action()` adjusts `crop_boost_adj` and `max_animals_adj` multipliers
- **Market Saturation**: `headroom = max(0, expected_drain * 1.5 - opp_production)` caps production to prevent price crashes
- **Replay Opponent Analysis**: `REPLAY_DUMP_STATS` tracks average dump quantities/days for known opponent dumping patterns

## 3. Current State (End of Day 2 — Aug 12)

### Score Progression
| Version | Opponent | Score (us) | Score (opp) | Result |
|---------|----------|-----------|-------------|--------|
| Pre-saturation fix | replay_opponent | ~86k | ~110k | Loss |
| Post-saturation (strict headroom) | replay_opponent | ~37k-50k | ~52k-84k | Loss |
| With max_animals_adj=1.0 floor | replay_opponent | ~50k-64k | ~65k-82k | Loss |

### What We Fixed Today
1. **Exact EV Integration**: Replaced heuristic `elastic_mav` with `compute_crop_mav_exact` and `compute_animal_mav_exact` — proper action cost accounting (feed, care, harvest, collect)
2. **Market Saturation Fix**: Changed `head[p]` to use strict `headroom` (1.5x town drain minus opponent production) instead of adding `units_sellable`, preventing the agent from flooding markets
3. **Animal Cap Removal**: Set `max_animals_adj` floor to 1.0 (was 0.7), removed penalty in `pivot_to` branch of `apply_strategic_action`
4. **Dynamic Liquidity Buffer**: Land buying now estimates 25-tile planting cost instead of fixed $2000 buffer
5. **Debug Cleanup**: Removed all temporary debug file-logging injected during investigation

### The Core Problem Identified
**"Tragedy of the Commons" in a competitive market:**
- Both agents prioritise Cows → 25+ Cows combined → Milk price crashes from $200 to $11 by Day 21
- Our `headroom` logic is **too polite**: when the opponent overplants 41 Strawberry plants, we detect saturation and voluntarily stop planting → opponent monopolises the high-margin crops
- The opponent sells aggressively on Days 18-20 *before* the crash, banking massive revenue while we're stuck with Wheat

### Known Code Issue
- Lines ~900 area: Manually deleted 8 lines (an accidentally-injected `for item in CROPS:` debug block) that broke the `elif k in ("COOP", "PASTURE"):` chain in the `opp_production` loop. The deletion was verified correct but could benefit from a manual review to confirm the `opp_production` parsing loop is intact.

## 4. Strategic Bottlenecks (Next Session Priority)

### P0 — Market Competition Strategy
The agent needs to stop being "polite" to a saturated market. Options:
1. **Race to sell first**: If opponent is overproducing Strawberries, we should also overproduce and sell *faster* (sell in smaller batches earlier in the day cycle)
2. **Asymmetric pivot**: If opponent monopolises crop X, pivot hard to crop Y that they're ignoring (Melons, Tomatoes)
3. **Hybrid**: Match production on the opponent's best crop but sell more aggressively, while also diversifying

### P1 — Sell Timing Optimisation
Currently the agent sells everything greedily. On shared markets, **timing** is critical — selling at Hour 0 gets a better price than Hour 4 after the opponent has dumped.

### P2 — Late-Game Liquidation
The agent stops buying animals on Day 25 (`stop_animals_day`), but doesn't aggressively liquidate shed contents. Days 26-28 should focus on converting all inventory to cash.

## 5. Files & Config
- `src/main.py` — The agent (single file, ~1800 lines)
- `src/replay_opponent.py` — Replay opponent that mimics top leaderboard agents
- `test.py` — Test harness: `python test.py -n 3 -o src/replay_opponent.py`
- `test_replays.py` — Extended benchmark against multiple replay files
- `replays/` — Directory with replay JSON files from top competitors

## 6. Key Parameters (in `P` dict at top of main.py)
- `max_animals`: 12 (total animal cap)
- `stop_animals_day`: 25
- `invest_frac`: 0.85
- `feed_reserve_days`: 4
- `max_geese`: 8
- `land_slack`: 6
