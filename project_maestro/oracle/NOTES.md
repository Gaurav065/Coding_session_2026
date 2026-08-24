# oracle -- NOTES

## Phase 1: Analytical Price & Valuation Engine

### Analytical AMM Model (`oracle/price_model.py`)
Implements exact mathematical pricing equations from `kaggriculture.py:195-207`:
$$P(inv) = \max\left(1, \text{round}\left(\text{base} + \text{sign} \cdot \frac{\text{target} \cdot \text{base}}{f(T)} \cdot f(|inv - I_0|)\right)\right)$$
where `_shape` is implemented at `kaggriculture.py:61-74`.

---

### 1. Exact Lifetime Animal Yield Schedule (`kaggriculture.py:804-839`)
Formula: $\text{days\_since\_first} = \text{next\_day} - \text{placed\_day} - \text{first\_yield\_day}$.
Yield occurs when $\text{days\_since\_first} \ge 0 \text{ and } \text{days\_since\_first} \pmod{\text{interval}} == 0$ over $\text{next\_day} \in [1, 30]$:
- **GOOSE** (`first_yield_day = 4`, `interval = 1`):
  - Placed Day 0: **27 yields** (Days 4..30).
  - Placed Day 1: **26 yields** (Days 5..30).
- **COW** (`first_yield_day = 8`, `interval = 2`):
  - Placed Day 0: **12 yields** (Days 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30).
  - Placed Day 1: **11 yields** (Days 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29).
- **SHEEP** (`first_yield_day = 6`, `interval = 3`):
  - Placed Day 0: **9 yields** (Days 6, 9, 12, 15, 18, 21, 24, 27, 30).
  - Placed Day 1: **8 yields** (Days 7, 10, 13, 16, 19, 22, 25, 28).

---

### 2. Endogenous Feed Valuation (Grown vs Bought) with Tile & Labor Opportunity Costs
Feeding consumes 1 wheat daily (`_inv_take(inv, "WHEAT", 1)`, `kaggriculture.py:505`).
- **Grown Feed**: Seed cost \$10 for 4 units unfertilized ($\approx \$2.50/\text{unit}$) $+$ labor ($\approx \$1.0/\text{action}$ over 30 actions $\approx \$30\text{–}\$35$). Total cost: **\$105** (Goose, 27 days), **\$90** (Cow, 22 days), **\$90** (Sheep, 24 days).
- **Bought Feed**: Market price quotes at $\approx \$39.4/\text{unit}$ (mean realized price in 697 real games due to 31 units/day shop drain). Total cost: **\$1,063.8** (Goose), **\$866.8** (Cow), **\$945.6** (Sheep).

| Animal | Capital Cost | Production Days | Lifetime Yield | Grown Feed Net (Base) | Bought Feed Net (Base) | Grown Feed Net (Glut) | Bought Feed Net (Glut) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GOOSE** | \$300 | 27 (Days 4..30) | 27 eggs | **+\$834.0** | -\$124.8 | **+\$702.0** | -\$256.8 |
| **COW** | \$400 | 22 (Days 8..30) | 12 milk | **+\$1,292.0** | +\$515.2 | **-\$478.0** | -\$1,254.8 |
| **SHEEP** | \$500 | 24 (Days 6..30) | 9 wool | **+\$1,198.0** | +\$342.4 | **-\$581.0** | -\$1,436.6 |

**Key Valuation Insights**:
1. **Endogenous Feed Sourcing**: Sourcing feed internally via on-farm wheat is a mandatory condition for livestock profitability ($16\times$ cost spread).
2. **Goose / EGG Immunity**: Stays strictly positive ($+\$702$ to $+\$834$) under all market conditions due to log glut decay ($T=332$, $\text{above\_target}=0.20$), cheap \$300 entry, and 27 lifetime units.
3. **Decoupled Cow vs Sheep Risk**:
   - `MILK`: $97.7\%$ chance of shop drain ($P(\text{zero demand}) = 2.33\%$). Cows are a core profit engine.
   - `WOOL`: $34.36\%$ chance of zero shop drain. Sheep must be conditional on Yarn Store appearing.

---

### 3. Market Interleaving Mechanics (`kaggriculture.py:596-597`)
- Orders from both players execute unit-by-unit, re-quoting after each unit.
- Modeled in `calculate_interleaved_revenue` in `oracle/price_model.py`.
