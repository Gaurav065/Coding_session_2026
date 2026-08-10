# Kaggriculture Competition - Agent Development Handoff Document

## Competition Overview
- **Competition**: Kaggriculture on Kaggle
- **Game**: Turn-based farming simulation (30 days, 720 turns)
- **Goal**: Maximize coins in bank at end of season
- **Current Best Score**: ~160 vs Starter bot (3476) - **LOSING BADLY**

## Repository Structure
```
C:\coding\kaggriculture-agent\
├── main.py                 # Entry point (exports agent function)
├── constants.py            # Game parameters, crop/animal stats, market params
├── state.py                # GameState parser with helper methods
├── market.py               # MarketPredictor for price forecasting
├── pathfinding.py          # A* pathfinding on 10x10 grid
├── strategy.py             # Main agent logic (Strategy + SimpleController)
└── pathfinding.py          # A* pathfinding
```

## Game Mechanics Summary

### Core Resources
| Resource | Type | Key Stats |
|----------|------|-----------|
| **Wheat** | One-time crop | 2 days to harvest, 6 max yield, seed=$10, sells ~$25 |
| **Tomato** | Ongoing crop | 8 days first yield, then daily x4, seed=$50 |
| **Melon** | One-time | 10 days, 6 max, seed=$80, sells ~$250 (crashes market) |
| **Goose** | Animal | $300, produces 1 egg/day, needs COOP ($100), fed 1 wheat/day |
| **Cow** | Animal | $400, produces 1 milk/2 days, needs PASTURE ($100) |

### Winning Economics (Theoretical)
1. **Geese are OP**: 1 egg/day = $50, feed cost = 1 wheat ($25) → **$25/day/tile net**
2. **Wheat loop**: Fast capital generation for geese
3. **Market dynamics**: Premium crops (melon, strawberry, milk, wool) crash to $1 floor on glut
4. **Town demand**: Shops unlock every 3 days, consume products, drive prices up

## Current Agent Architecture

### Strategy Class (Planning)
- Creates daily plan based on game day
- Phased approach: Wheat → Geese → Scale
- Budget-aware purchasing
- Market sell planning with price prediction

### SimpleController (Execution)
- **Farmer**: Wheat planting, watering, harvesting, building coops
- **Hand 0**: Goose management (feed, care, harvest eggs, place geese)
- **Hand 1+**: Wheat support (water, harvest, plant)

### Key Methods
```python
agent(obs) -> Dict  # Main entry point
Strategy.create_plan(state) -> DailyPlan
SimpleController.get_actions(state, plan) -> Dict
```

## Critical Bugs Blocking Progress

### 1. **PLACE_GOOSE Action Fails** 
- Hand tries to place goose but action fails silently
- Goose stays in shed, hand loops PLACE_GOOSE forever
- **Root cause**: Hand not on coop tile when action executes, or PLACE requires specific positioning

### 2. **No Feeding/Caring Happening**
- Hand 0 prioritizes PLACE over FEED/CARE
- Geese placed but never fed → escape after 2 days
- **Current priority order broken**

### 3. **Market Submissions Every Turn**
- Sell orders submitted every turn instead of once/day
- Wastes market order slots (max 10/turn)

### 4. **Wheat → Shed Timing**
- Wheat harvested day 2, reaches shed day 4 (end of day drop)
- No money for geese on day 3 when plan expects it

### 5. **Movement Logic Fragile**
- `_move_or_act` returns movement if not on target
- But action execution and movement happen in same turn
- Hand often arrives next turn but action already "executed"

## Files to Focus On

### `strategy.py` - MAIN FILE TO FIX
Key areas:
- `SimpleController._hand_action()` - Fix priority order (FEED → CARE → HARVEST → PLACE)
- `SimpleController._move_or_act()` - Fix movement/action coordination
- `Strategy.create_plan()` - Adjust budget projections for wheat→shed delay

### `state.py` - Helper methods working correctly
- `occupied_animal_structures()`, `animals_needing_feed()`, etc. ✓

### `market.py` - Price prediction working
- `optimal_sell_batch()`, `predict_price()` ✓

## What a Working Agent Needs

### Minimum Viable Strategy (Copy from Starter + Improvements)
```python
def agent(obs):
    # 1. Buy wheat seeds day 0
    # 2. Plant 6 wheat near shed
    # 3. Water daily, harvest at age 2+
    # 4. Sell wheat, keep 3 buffer
    # 4. Day 3: Buy 2 geese + 2 coops
    # 5. Hand 0: Feed→Care→Harvest eggs→Place geese (ONLY when on coop tile)
    # 6. Sell eggs, keep 1 buffer
    # 7. Scale to 4-6 geese by day 10
```

### Critical Fixes Needed
1. **Place geese ONLY when hand on coop tile** - check position before PLACE
2. **FEED must be absolute priority** - every goose every day
3. **Market once per day** - hour 0 only
4. **Budget projection** - account for 2-day wheat→shed delay

## Test Commands
```bash
cd C:\coding\kaggriculture-agent
python -c "
from kaggle_environments import make
from main import agent
env = make('kaggriculture', configuration={'episodeSteps': 150}, debug=True)
env.run([agent, 'starter'])
"
```

## Competition Timeline
- **Entry Deadline**: Sept 23, 2026
- **Final Submission**: Sept 30, 2026
- **Leaderboard Convergence**: ~Oct 15, 2026
- **Prizes**: $5,000 each for 1st-10th place

## Next Steps for New Model
1. **Start simple**: Copy starter agent, add geese logic incrementally
2. **Fix PLACE_GOOSE**: Only execute when `pos == coop_position`
3. **Add FEED as absolute first action** for hand 0
4. **Test 150-turn games** first, then full 720
5. **Target score**: Beat starter (3476) consistently

## Key Insight
The starter agent scores ~3500 with just wheat loop. Adding 2 geese properly should add ~$50/day = $1500 over 30 days → **target ~5000**. Winning agents likely hit 8000-10000.

---
*Last updated: Development session attempting wheat→geese pipeline. Core issue: action execution coordination between movement and tile actions.*