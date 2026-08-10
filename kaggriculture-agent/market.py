# market.py
import math
from typing import Dict, List, Tuple
from constants import MARKET_PARAMS, SHOP_DEMANDS

class MarketPredictor:
    def __init__(self):
        self.price_history: Dict[str, List[int]] = {k: [] for k in MARKET_PARAMS}
        self.inventory_history: Dict[str, List[int]] = {k: [] for k in MARKET_PARAMS}
    
    def update(self, market: Dict):
        for product, inv in market["inventory"].items():
            if product in MARKET_PARAMS:
                self.inventory_history[product].append(inv)
                self.price_history[product].append(market["prices"][product])
    
    def predict_price(self, product: str, future_inventory: int) -> int:
        params = MARKET_PARAMS[product]
        base = params["base"]
        I0 = params["I0"]
        T = params["T"]
        
        diff = future_inventory - I0
        abs_diff = abs(diff)
        
        if diff < 0:
            func = params["below_func"]
            target = params["below_target"]
            sign = 1
        else:
            func = params["above_func"]
            target = params["above_target"]
            sign = -1
        
        f_val = self._shape_function(func, abs_diff)
        f_T = self._shape_function(func, T)
        
        if f_T == 0:
            return base
        
        amp = target * base / f_T
        price = base + sign * amp * f_val
        return max(1, round(price))
    
    def _shape_function(self, func: str, x: float) -> float:
        if func == "linear": return x
        elif func == "sqrt": return math.sqrt(x)
        elif func == "sq": return x * x
        elif func == "log": return math.log1p(x)
        elif func == "log10": return math.log10(1 + x)
        return x
    
    def simulate_sell_impact(self, product: str, quantity: int, current_inv: int) -> List[int]:
        prices = []
        inv = current_inv
        for _ in range(quantity):
            price = self.predict_price(product, inv)
            prices.append(price)
            inv += 1
        return prices
    
    def optimal_sell_batch(self, product: str, available: int, current_inv: int) -> Tuple[int, int]:
        best_revenue = 0
        best_qty = 0
        for qty in range(1, available + 1):
            prices = self.simulate_sell_impact(product, qty, current_inv)
            revenue = sum(prices)
            if revenue > best_revenue:
                best_revenue = revenue
                best_qty = qty
            if prices and prices[-1] <= 1:
                break
        return best_qty, best_revenue
    
    def get_town_consumption_per_day(self, town: Dict) -> Dict[str, int]:
        """Daily consumption by town shops + center."""
        rates = {}
        shops = town.get("unlocked_shops", [])
        
        for shop in shops:
            for product in SHOP_DEMANDS.get(shop, []):
                rates[product] = rates.get(product, 0) + 1
        
        for product in MARKET_PARAMS:
            if product != "FERTILIZER":
                rates[product] = rates.get(product, 0) + 1
        
        return rates
    
    def next_town_consumption_turn(self, day: int, hour: int) -> int:
        """Turns until next town consumption tick (shops every 4 turns, center every 24)."""
        step = day * 24 + hour
        # Shops consume every 4 turns
        next_shop = ((step // 4) + 1) * 4
        # Center consumes every 24 turns
        next_center = ((step // 24) + 1) * 24
        return min(next_shop, next_center) - step

    def should_sell_now(self, product: str, current_price: int, town_rates: Dict[str, int], turns_until_consumption: int) -> bool:
        """Decide whether to sell now or wait for town consumption to drive price up."""
        # If town consumes this product soon and price is low, wait
        if town_rates.get(product, 0) > 0 and turns_until_consumption <= 2 and current_price < MARKET_PARAMS[product]["base"]:
            return False
        # Premium products: sell in batches, don't trickle
        if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
            return current_price > 1
        return True