# Kaggriculture Engine Mechanics & Diagnostic Rules

### 1. Plant Watering & Wither Rules
- **Missed Watering**: A crop that misses 2 consecutive end-of-day refreshes turns into a **WEED** (`kind: 'WEED'`). Once turned into a weed, it produces 0 yield and can only be cleared with `DIG`.
- **Planting Day Trap**: The day a plant is placed (`PLANT`) counts as its **first unwatered day** unless a `WATER` action is performed on that tile on that same day before midnight (Hour 23)!
  - *Example defect*: Planting on Hour 19 without watering before Hour 23 means `consecutive_unwatered = 1`. If the worker skips watering the next day, the plant is dead at Hour 0 of Day 2!
- **Ongoing Crops (Tomato, Strawberry)**: Produce continuously every few days, but **require water every single day** for their entire lifespan.
- **One-time Crops (Wheat, Carrot, Melon)**: Can survive dry spells after maturation, but yield bonuses require watering during bonus windows (`ceil(max_yield_day / 2)` to `max_yield_day`).

### 2. Land Acquisition & Tile Rules
- **Starting Board**: Only Northwest (`NW`, tiles `0..4, 0..4`) is unlocked at Step 0.
- **Unlock Order & Cost**:
  - 1st expansion: `NE` ($1,000)
  - 2nd expansion: `SW` ($2,000)
  - 3rd expansion: `SE` ($4,000)
- **Ghost Land**: If an agent issues `BUY_LAND` but its movement tape does not route workers across `x >= 5` or `y >= 5`, the money is deducted but 0 agricultural value is extracted.

### 3. Market Order Execution
- Max 10 market orders per turn.
- If a player orders `["SELL", "TOMATO", 5]` but has 0 tomatoes in their private shed, the game engine silently drops the order as a no-op without raising an error.
- If an agent repeatedly outputs phantom sell orders, it pollutes the turn's order cap and conceals the lack of harvest production.
