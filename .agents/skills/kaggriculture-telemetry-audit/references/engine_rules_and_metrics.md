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

### 4. Livestock Macroeconomics & Price Collapse Thresholds
- **Dynamic Pricing Shape Function**: Sale prices for milk and wool decay with market inventory:
  \[
  P(I) = \max\left(1, \text{round}\left(P_{\text{base}} \times f\left(\frac{I_0}{I}\right)\right)\right)
  \]
  Premium goods (Milk, Wool) have steep convex penalty curves (`sq` or `linear` on oversupply side). Once market inventory exceeds town consumption capacity, sale prices collapse to the **$1.00 floor**.
- **The Negative Net-Cashflow Threshold (Feeding Cost > Revenue)**:
  - Feeding 1 animal consumes 1 wheat every day.
  - When livestock count is high across both players, market wheat supply is exhausted, spiking the wheat buy price to **$45 - $50 / unit**.
  - A Cow yields 1 Milk every 2 days (0.5 Milk/day baseline). If Milk sells at $1.00, daily revenue is $0.50 while daily feed expense is $48.00.
  - **Net loss per cow**: \$-47.50 / day. Holding 20 cows in a glut loses **\$950 per day** in cash!

### 5. Multi-Agent Livestock Over-Expansion Trap (Seed 2 & 100 Case Study)
- **Sunk-Cost Land & Animal Trap**: Expanding into the 4th quadrant (`SE`) requires:
  - $4,000 for `BUY_LAND`
  - $4,800 to purchase 12 Cows ($400 each)
  - Hiring 3 additional daily farmhands (~$7/day * 18 days = ~$126)
  - Feeding 12 extra animals with wheat (~$48/wheat * 12 = $576/day * 17 days = ~$9,792)
  - **Total marginal investment**: **~$18,700+**.
- **The Defeat Mechanism**:
  - In 1v1 play against an opponent who also maintains 8-12 animals, the joint livestock pool reaches 30+ animals.
  - If the town has only 1 or 2 matching shops (e.g. 1 Ice Cream Shop consuming 6 milk/day, and 0 Yarn Stores consuming wool), total milk/wool production exceeds town consumption by 200%-300%.
  - Prices hit the $1.00 floor instantly. The 12 extra SE cows produce ~72 milk sold for $72 total, yielding a net loss of **-$18,600+**.
  - An opponent who abstains from SE expansion, keeps 12 animals, and pays half the feed costs preserves $12,000 - $14,000 more cash, causing a direct match loss.

### 6. Terminal Horizon Feeding Deadlines (Zero-Yield Feeding Waste)
- Cows have a production interval of 2 days; Sheep have an interval of 3 days.
- Feeding on Day 28 or Day 29 costs full wheat prices ($45-$50) but **produces 0 additional yield before Step 720**.
- Animals placed after Day 20 or fed during the final 48 hours without a remaining payout milestone are pure financial drains.

