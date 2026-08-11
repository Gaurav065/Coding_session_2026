# Target 100k+ Score Implementation Plan

Our current GA-optimized strategy peaked at **23.5k**. This is a great improvement, but you are right: to hit 80k–100k+, our current strategy is mathematically insufficient. 

To break 100k, we must tap into the game's exponential profit mechanic: **Fertilizer + Melons**.

## Why Our Current Strategy Isn't Enough
1. **Unused Fertilizer**: Our agent assigns `COLLECT_FERTILIZER`, but we never implemented the logic to `FERTILIZE` crops! Every day, crops grow by 1 unit if watered. If fertilized, they grow by **2 units**, effectively doubling crop velocity.
2. **We aren't planting Melons**: Melons have a massive margin (cost 80, sell for ~1000-2000). However, they take 12 days to grow normally. If we apply fertilizer, they take only **6 days**. 
3. **Market Deflation**: If we plant 100% Melons, the market price crashes. We need a dynamic threshold that stops selling Melons when the price crashes, and optionally utilizes the randomly unlocked Town Shops (e.g., selling Wheat/Melon bundles if required).

## Proposed Changes

### Strategy Engine (`strategy.py` & `state.py`)

#### [MODIFY] `state.py`
- Expose crops that need fertilizer. The engine tracks `tile["fertilized_until_day"]`.
- Create a `state.crops_needing_fertilizer()` method that filters for high-value crops (like MELON) where `fertilized_until_day < current_day`.

#### [MODIFY] `strategy.py`
- Add a new Job dispatcher rule in `_sync_world_jobs`:
  - **Priority 4.5 (Just below FEED/CARE)**: `FERTILIZE` job targeting high-value crops (MELON, STRAWBERRY).
- Update `_attempt_job` to handle `job.type == "FERTILIZE"` properly, ensuring the agent picks up Fertilizer from the shed if their inventory doesn't have it.
- **Dynamic Crop Shift**: Modify `plan.crop_targets` to heavily favor MELON (e.g., 50-60%) while keeping WHEAT around 20-30% to feed the cows/sheep that produce the fertilizer.

### Open Questions for You

> [!IMPORTANT]
> **Market Crash Strategy**
> When we harvest 200 fertilized Melons, selling them all at once will crash the price down to 1 coin. Our current logic sells up to 30 items per turn if the price is > 60% of base. Should we add logic to **hoard** Melons in the shed until the price recovers (the Town consumes 1 item per 24 steps automatically), or should we rotate to STRAWBERRY/TOMATO when Melon prices drop below a threshold?

> [!TIP]
> **Recommendation:** We should rotate crops dynamically. If Melon price drops below 60% base, our agent should automatically switch to STRAWBERRY seeds for the next batch, allowing the Melon market to heal.

Please review this plan. If you approve, I will implement the FERTILIZE logic and the crop rotation triggers to push for 100k!