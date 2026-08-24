# engine -- NOTES

What was tried, the numbers, and what was rejected and why.
A rejected experiment recorded here must never be silently re-run.

## 2026-08-22: Fast Discrete-Event Engine (Milestone 2 Pass)
- Pure Python simulator `FastGame` in `project_maestro/engine/fast_engine.py`.
- Benchmarked against `kaggle_environments.make("kaggriculture")` on 20 fixed seeds across all 720 turns.
- Result: 20 / 20 Exact Matches, Δ = $0.00, 14.3x–17.0x speedup (>6,200 steps/sec).
- Ground truth engine facts validated:
  - Turn execution order: Unit Actions -> Market Orders -> Shop AMM Drain (every 4 steps) -> Town Center Drain (every 24 steps) -> Plant Decay (odd steps past max lifespan) -> Midnight Refresh (`kaggriculture.py:935-946`).
  - Empty inventories delete zero keys (`del inv[item]`).
  - One-time crops gain yield immediately upon watering during the bonus window (`(max_yield_day + 1)//2 <= age <= max_yield_day`), capped at `max_yield`.
  - Ongoing crops yield at midnight refresh (`_daily_refresh_plants`), incrementing yield by 1 (or 2 if fertilized and watered that day) up to `max_yield` lifetime productions.
  - Animals escape after 2 consecutive unfed days at midnight refresh; structure remains (`kaggriculture.py:821`).
  - Weed spawn RNG: `(seed * 1_000_003) ^ day` consumes `rng.random()` per empty unlocked tile across both farms BEFORE `rng.choice(sorted(SHOPS))` unlocks town shops on day % 3 == 2 (`kaggriculture.py:870-891`).
