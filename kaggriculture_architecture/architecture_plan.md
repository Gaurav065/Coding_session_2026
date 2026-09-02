# Kaggriculture Top-Tier Agent Architecture

## A. Best architecture
The most robust and competitive architecture for Kaggriculture is a **Hybrid Heuristic + Opponent-Simulation (Frontrunning) Layer**.
1. **State Parser:** Wraps the raw JSON observation into typed, easy-to-query objects (e.g., parsing 2D tiles into a list of `Plant` and `Animal` objects).
2. **Action Planner (Field):** A priority-queue-based task allocator for the Farmer and hired hands. Tasks (Watering, Harvesting, Planting, Feeding) are scored by urgency, and units greedily claim the highest priority task they can reach via Manhattan distance.
3. **Market Policy (The Decider):** This is the core differentiator. Because market prices are shared and dynamic, the agent uses a 1-to-2 step lookahead simulation. It simulates the baseline "greedy" opponent to predict when they will sell or dump their inventory.
4. **Safety Fallback:** A top-level `try/except` block that defaults to `PASS` for all units to ensure the agent never crashes on Kaggle (which otherwise causes a silent 3000.0 coin tie).

*Why this is the best starting point:* End-to-end RL is too difficult to train safely given the 720-step horizon and strict rules. Pure heuristics are easily exploited by market dumpers. A heuristic core augmented with a market simulator allows us to perfectly time our sells to maximize profit and frontrun opponents.

## B. Opening strategy
- **Day 1-3 Focus:** Immediate land expansion and fast cash. Buy the NE quadrant immediately for $1k. 
- **Crop Selection:** Heavily bias towards fast-yielding crops (Wheat, Melon) to build early liquidity. 
- **Hiring:** Hire exactly 1-2 hands early on to maximize planting coverage. The Fibonacci cost scaling means hiring more than 2-3 per day is economically disastrous in the early game.

## C. Midgame decision rules
- **The Town Shop Insight:** Town shops **do not pay players**. They simply consume items from the market, which artificially lowers market inventory and drives prices *up*. **Never hoard items in your shed for the Town Shop.** 
- **Selling Rhythm:** Instead of holding items, sell them continuously in small batches (e.g., 1-2 per turn). This prevents you from crashing your own price. When the Town Shop inevitably consumes from the market, the price will automatically recover, and your next small batch will benefit from the premium.
- **Animal Husbandry:** Transition into Cows/Sheep by midgame, ensuring you have a steady stream of Wheat to feed them. Their yields (Milk/Wool) are highly profitable if sold steadily.

## D. Endgame liquidation rules
- **The Frontrunning Dump:** The game ends precisely at step 718. Shed inventory does *not* auto-sell. Most top clones (e.g., Malyshev Danil) will attempt a massive inventory dump at step 717 or 718 to liquidate. 
- **Our Rule:** We track the current step. At `step == 716` (or one step before the opponent's predicted dump), we execute a massive `SELL` of all non-animal assets. Because Kaggriculture processes market orders in lockstep, selling *one turn earlier* guarantees we get the high prices for all our items, leaving the opponent to sell into a flooded, $1-floor market.

## E. Risk controls and failure modes
- **Kaggle Bundler Crashes:** Kaggle's `exec()` runner strips the `__file__` attribute. Many agents crash silently on step 0 because they rely on `__file__` for relative imports. We will use a safe base85 bundler that explicitly avoids `__file__`.
- **Seed Starvation:** If we spend all money on land/animals and have no seeds, the farm stalls. Rule: Always maintain a minimum cash reserve of $50 or at least 10 seeds in inventory.
- **Weed Cascade:** Weeds spawn randomly (0.5% chance per empty tile). Unchecked, they block expansion. Rule: Idle hands default to `DIG` on weeds.

## F. Step-by-step MVP build order
1. **Scaffolding:** Create `agent.py` with a safe `try/except` wrapper and basic JSON parsing.
2. **Field Execution:** Implement a greedy assignment loop: Harvest > Water (if not watered today) > Plant (Wheat) > Pass.
3. **Market Execution:** Sell all harvested Wheat immediately to the market.
4. **Local Testing:** Bundle into a single file and run a 5-seed benchmark against the `starter_agent` using `kaggle_environments`.

## G. What to test first against the starter/random agent
- **Stability:** Does the agent survive 720 turns across 10 random seeds without throwing a single exception?
- **Positive ROI:** Does the agent finish with significantly more than the starting $3000?
- **Mechanics Check:** Do any crops die (turn into weeds) due to missed watering? If yes, the task allocator is flawed.

## H. What improvements to add after the first working submission
1. **Opponent Simulation:** Plug in a copy of the MVP agent to simulate the opponent's shed inventory and predict their market dumps.
2. **Crop Diversification:** Implement logic to switch from Wheat/Melon to premium crops (Strawberry) if the market is saturated with Wheat.
3. **Optimized Watering Bonus:** Time watering strictly during the bonus window (`ceil(max_yield_day / 2)`) rather than blindly watering every day, saving hand actions.
