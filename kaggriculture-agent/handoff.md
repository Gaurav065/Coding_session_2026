# Deep Context Handoff: Kaggriculture Agent

This document serves as a comprehensive context handoff for any future agent or developer taking over the `kaggriculture-agent` project. It contains all game mechanics, economic theories, discovered exploits, current agent architectures, and the roadmap for the final unexploitable strategy.

## 1. Game Environment & Constraints
**Kaggriculture** is a turn-based farming simulation (720 episodes/steps = 30 days) where two players compete on separate boards to maximize total profit. 
- **The Market:** A shared, dynamic global market. If a player sells a massive amount of a single crop (e.g., Strawberries), the global price crashes for both players.
- **Labor (Farmhands):** Hands are required to execute tasks (plant, water, care, harvest). Their daily salary follows the **Fibonacci Sequence**: $1, $1, $2, $3, $5, $8, $13... up to bankrupting amounts (e.g., the 15th hand costs $610/day).
- **Land Expansion:** Players start with 1 quadrant (25 tiles). They can buy up to 3 more quadrants ($1k, $2k, $4k).
- **Animals:** Provide high-yield recurring products (Milk, Wool, Eggs) but require daily feeding (Wheat) and caring. If uncared for, their production time doubles. If unfed, they eventually die.

## 2. Core Economic Discoveries (The Math)
Through intense testing, we discovered the mathematical boundaries of the game:
1. **The Fibonacci Ceiling:** Because hand costs scale exponentially, hiring more than 13-14 hands is mathematically suicidal. The 14th hand costs $377/day ($29 per action), which is barely profitable for animals (Cow = ~$32/action) and entirely unprofitable for premium crops (Strawberry = ~$22/action).
2. **Travel Time Penalty (Scalability Flaw):** Expanding the board increases the physical distance between tasks. On a 1-quadrant board, a hand can perform ~13 actions/day. On a 4-quadrant board, this efficiency drops to ~7-8 actions/day due to travel overhead.
3. **The Static Trap:** Top leaderboard agents (like THUNDER THUNDER) use a static approach: limit the board to 3 quadrants, cap animals at 24, cap hands at 13, and blindly plant Strawberries and Melons. 

## 3. The `version_beta` Architecture (Current State)
We branched from the static `main.py` into a fully dynamic agent in `version_beta/main.py`. This agent strips all hardcoded limits and relies entirely on a **Marginal Economics Engine**.

### A. Dynamic Crop Pivoting (The THUNDER Exploit)
Instead of forcing Melons/Strawberries, the agent calculates the **Marginal Action Value (MAV)** of every crop based on the *real-time* market price. If the opponent uses the static THUNDER strat and crashes the Strawberry market, our agent instantly detects the crash and pivots to monopolizing high-priced Carrots or Tomatoes. 

### B. Dynamic Task Prioritization (The Weed Bug Fix)
We discovered a fatal flaw in early versions: hands were prioritizing pulling weeds ($130 value) over caring for cows ($72 value). This caused animal production to halve.
**The Fix:** 
- Weed pulling is now dynamically de-prioritized to a rock-bottom $15 value if there is plenty of empty space on the board. It only scales up to $180 if the board is completely full.
- Animal Feed and Care are floored at a massive $200+ priority, guaranteeing animals are serviced instantly.

### C. Smooth Fibonacci Scaling
The agent dynamically scales its operation by simulating fractional labor costs. Before buying a Cow, it projects the Fibonacci cost of the *additional fractional hands* needed to service it over the season. If `Projected Profit > Projected Marginal Labor Cost`, it buys. Otherwise, it stops naturally—no hard limits required. 

**Testing Results:** In a 10-seed head-to-head sweep against the static THUNDER bot, the dynamic `version_beta` agent achieved a **70% win rate** (7/10 wins). In shared-market crashes, both scores drop to ~50k, but the dynamic agent consistently out-adapts the static bot.

## 4. The Future Roadmap (Unimplemented Final Strategies)
The user has outlined the final strategic additions needed to make the agent 100% un-exploitable. **DO NOT modify the baseline logic until these are perfectly integrated:**

### Strategy 1: Dynamic CapEx Liquidity Buffering
Currently, the agent buys land the moment it has enough cash (e.g., $2k). This leaves it broke, unable to afford premium seeds or labor for the new land, leading to dead infrastructure.
**Implementation Goal:** The agent must calculate a `Required_Liquidity_Buffer` before buying land.
- `Buffer = (25 tiles × Cost of Current Best Seed) + (Projected Labor Cost for those tiles over the next 5 days)`
- Rule: Only buy land if `Current_Cash > Land_Cost + Required_Liquidity_Buffer`.

### Strategy 2: Adversarial State Evaluation (Algorithmic Edge-Case Handling)
While pure RL is a trap for this environment (due to the 720-step credit assignment problem and market crash ceilings), we need algorithmic edge-case handling akin to chess engines.
**Implementation Goals:**
- **Market Anticipation Tracker:** A state-machine module that scans the opponent's board. If the opponent builds 4 Pastures, it predicts a Wool market crash in 10 days and triggers an early sell-off or pivot to Geese.
- **Minimax / MCTS Integration:** Future iterations could simulate the next 5 days of opponent actions (assuming they take the worst possible actions for our economy) to find the optimal Nash Equilibrium response.

## 5. Agent Instructions for Resumption
When picking up this project:
1. Review `version_beta/main.py`. This is the cutting-edge dynamic agent.
2. The immediate next task is implementing the **Dynamic CapEx Liquidity Buffer** logic into the land expansion code block.
3. Test all changes heavily using `python test.py -n 10 -o ../main.py` in the `version_beta` directory to ensure the 70%+ win rate against the THUNDER strat is maintained or improved.
