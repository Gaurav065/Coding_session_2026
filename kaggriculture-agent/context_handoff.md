# Context Handoff: Kaggriculture Agent

## Objective
We are designing a counter-strategy for a 30-day (720 episodes) farming simulation competition. Our agent needs to consistently beat top leaderboard players (who score ~130k vs our ~40k). 

## Current Status & Discoveries
1. **Opponent Strategy**: We discovered that the opponent (HFT-style bot) manipulates market prices. We analyzed their replay (`92023176.json`) and created `replay_opponent.py` to replay their exact actions in our test environment (`test.py`). Despite our agent participating in the environment, the opponent still consistently achieves ~125k rewards while our agent stagnates around 40k.
2. **Agent Bottlenecks Identified**:
    * **Hoarding Behavior**: Our agent has hardcoded `reserve` prices in `main.py` (e.g., Milk = 105). If the market price drops below this reserve, the agent refuses to sell and just hoards items until the last few days when `reserve_scale` forces a dump. 
    * **Scaling Limits**: `main.py` originally capped hiring at 16 hands and 24 animals. 
    * **Fibonacci Labor Cost Trap**: We attempted to increase the caps to 100 hands/animals, but the agent still didn't scale. Investigation revealed that the game uses a Fibonacci sequence for labor costs (e.g., 20th hand costs 6765/day). The agent's `labor_reserve` calculation uses this exponential cost to hoard cash, which starves the `budget` and permanently prevents it from buying land, hiring more hands, or purchasing animals.
    * **Land Buying Bug**: `plan["buy_land"]` logic was disjointed, which we patched in `main.py` (via `do_replace_land.py`), but the Fibonacci budget starvation renders the fix moot.

## Actionable Next Steps
1. **Revamp Market Orders (Selling)**: The agent must dynamically adjust its reserve prices based on market trends rather than fixed pessimistic limits. If the opponent crashes the market, we need to either dump early (front-run) or switch production entirely.
2. **Rethink Labor Allocation**: The exponential cost of hiring hands means we cannot rely on a labor-heavy strategy. We must prioritize high ROI actions that require minimal hands (e.g., market trading or low-labor/high-yield animals like Geese/Sheep) instead of blindly increasing `current_hands`.
3. **Analyze Opponent's Market Actions**: The opponent's replay has structured actions (`farmer`, `hands`, `market`). A script should be written to properly parse `step[winner]['action']['market']` to see exactly what they are buying and selling to achieve 130k with minimal farming. (My previous parsing script checked the dictionary keys instead of the values).

## Files Modified
* `version_beta/main.py`: Increased max caps, attempted to fix `buy_land` logic, and modified the `reserve_scale` window to start dumping on Day 22 instead of Day 27.
* `version_beta/test.py` (and multiple debug scripts like `do_analyze.py`, `replay_opponent.py`): Used to replay the top player's JSON and trace agent execution.

## To Continue
1. Fix the opponent action parser in `do_analyze.py` to correctly parse `step[winner]['action']['market']`.
2. Rewrite the budget allocation (`labor_reserve`) in `main.py` so it doesn't exponentially starve the budget for land/seeds.
3. Implement a dynamic `reserve` price system to stop the agent from hoarding.
