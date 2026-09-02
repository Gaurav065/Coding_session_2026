"""E777A: Apex All-Product Terminal Sweep & Robustness Guard on top of E776A."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

import e776a_engine_exact_latent_pasture as PARENT

ENGINE = PARENT.ENGINE
MAX_STEPS = ENGINE.MAX_STEPS
FINAL_EXECUTABLE_STEP = 718

ALL_SWEEP_PRODUCTS = (
    "MILK", "WOOL", "MELON", "STRAWBERRY", "CARROT", 
    "TOMATO", "WHEAT", "EGG", "TRUFFLE", "FERTILIZER"
)

def _revenue(item: str, inventory: int, quantity: int) -> int:
    return sum(ENGINE._price(item, inventory + offset) for offset in range(quantity))

def _sanitize_coops(action: dict[str, Any]) -> dict[str, Any]:
    """Unconditionally eliminate any legacy BUILD_COOP commands to ensure zero dead coops."""
    if not isinstance(action, dict):
        return action
    changed = copy.deepcopy(action)
    farmer = changed.get("farmer", [])
    if isinstance(farmer, list) and any("COOP" in str(x).upper() for x in farmer):
        changed["farmer"] = ["PASS"]
    hands = changed.get("hands", [])
    if isinstance(hands, list):
        for i, h in enumerate(hands):
            if isinstance(h, list) and any("COOP" in str(x).upper() for x in h):
                hands[i] = ["PASS"]
        changed["hands"] = hands
    return changed

def _capital_budgeting_filter(step: int, action: dict[str, Any]) -> dict[str, Any]:
    """
    Finite-horizon ROI calculator shield.
    Prevents investing in long-term assets when there aren't enough turns left to recoup the cost.
    """
    if not isinstance(action, dict):
        return action
    
    changed = copy.deepcopy(action)
    
    # Filter market actions
    market = []
    for order in changed.get("market", []):
        if not order:
            continue
        op = str(order[0]).upper()
        item = str(order[1]).upper() if len(order) > 1 else ""
        
        # Animals take ~100+ turns to pay back
        if op == "BUY_ANIMAL" and step > MAX_STEPS - 120:
            continue
        # Land requires time to clear weeds, plant, and harvest
        if op == "BUY_LAND" and step > MAX_STEPS - 200:
            continue
            
        # Seeds have varying growth cycles
        if op == "BUY_SEED":
            if item == "MELON" and step > MAX_STEPS - 30:
                continue
            if item in ("STRAWBERRY", "TOMATO") and step > MAX_STEPS - 20:
                continue
            if item in ("CARROT", "WHEAT") and step > MAX_STEPS - 10:
                continue
                
        market.append(order)
    changed["market"] = market
    
    # Filter physical actions (e.g. BUILD_PASTURE)
    # Pastures take time to build, and animals take time to yield
    farmer = changed.get("farmer", ["PASS"])
    if isinstance(farmer, list) and len(farmer) > 0 and str(farmer[0]).upper() == "BUILD_PASTURE":
        if step > MAX_STEPS - 140:
            changed["farmer"] = ["PASS"]
            
    hands = changed.get("hands", [])
    if isinstance(hands, list):
        for i, h in enumerate(hands):
            if isinstance(h, list) and len(h) > 0 and str(h[0]).upper() == "BUILD_PASTURE":
                if step > MAX_STEPS - 140:
                    hands[i] = ["PASS"]
        changed["hands"] = hands
        
    return changed

def _detect_opponent_hoarding(obs: Any, seat: int) -> dict[str, bool]:
    """
    Phase C: Shadow Ledger / Opponent Tracking.
    Calculates the opponent's industrial production capacity from the public board state.
    If the opponent has significant production power of a specific item, they are likely
    hoarding it or will flood the market soon.
    """
    opp_seat = 1 - seat
    farms = ENGINE._get(obs, "farms", [])
    if opp_seat >= len(farms):
        return {}
        
    opp_farm = farms[opp_seat]
    tiles = ENGINE._get(opp_farm, "tiles", [])
    
    production_power = {}
    if isinstance(tiles, list):
        for row in tiles:
            if isinstance(row, list):
                for tile in row:
                    if isinstance(tile, dict):
                        if tile.get("type") == "CROP":
                            crop = tile.get("crop")
                            if crop:
                                production_power[crop] = production_power.get(crop, 0) + 1
                        elif tile.get("type") == "ANIMAL":
                            animal = tile.get("animal")
                            if animal == "COW":
                                production_power["MILK"] = production_power.get("MILK", 0) + 1
                            elif animal == "SHEEP":
                                production_power["WOOL"] = production_power.get("WOOL", 0) + 1
                            elif animal == "GOOSE":
                                production_power["EGG"] = production_power.get("EGG", 0) + 1
                            elif animal == "PIG":
                                production_power["TRUFFLE"] = production_power.get("TRUFFLE", 0) + 1
                                
    hoarding = {}
    for item, count in production_power.items():
        # If opponent has >= 3 sources of an item, they have high production capacity
        if count >= 3:
            hoarding[str(item).upper()] = True
            
    return hoarding

def _exact_market_pricing_filter(obs: Any, seat: int, action: dict[str, Any]) -> dict[str, Any]:
    """
    Phase A & C: Exact Market Pricing Model with Opponent Preemption.
    Dynamically throttles SELL orders by modeling the exact price drop curve.
    Only sells units if the marginal price remains above a dynamically calculated threshold.
    """
    if not isinstance(action, dict):
        return action
        
    step = int(ENGINE._get(obs, "step", 0) or 0)
    # Phase D: Terminal Liquidation Guarantee. Bypass all pricing logic on the last two turns
    # to ensure NO inventory is left on the table.
    if step >= MAX_STEPS - 2:
        return action
        
    try:
        available, _ = PARENT.PARENT.PARENT.PARENT.BASE._project_shed(obs, seat, action)
    except Exception:
        farm = ENGINE._get(obs, "farms", [])[seat]
        available = dict(ENGINE._get(farm, "inventory", {}) or {})
        
    total_shed = sum(max(0, int(v)) for v in available.values())
    
    # Determine base price drop tolerance based on shed pressure
    if total_shed >= 90:
        base_tolerance = 1.00  # Panic dump, accept 100% price drop
    elif total_shed >= 75:
        base_tolerance = 0.40  # Accept 40% price drop
    elif total_shed >= 50:
        base_tolerance = 0.25  # Accept 25% price drop
    else:
        base_tolerance = 0.15  # Accept 15% price drop
        
    hoarding = _detect_opponent_hoarding(obs, seat)
    market_data = ENGINE._get(obs, "market", {}) or {}
    inventory = ENGINE._get(market_data, "inventory", {}) or {}
    
    changed = copy.deepcopy(action)
    new_market = []
    
    for order in changed.get("market", []):
        if len(order) >= 3 and str(order[0]).upper() == "SELL":
            item = str(order[1]).upper()
            requested = max(0, int(order[2] or 0))
            if requested == 0:
                continue
                
            current_inv = int(ENGINE._get(inventory, item, ENGINE.I0) or ENGINE.I0)
            base_price = ENGINE._price(item, current_inv)
            
            # Phase C: Preemption
            # If the opponent is hoarding this item, increase our tolerance by 15%
            # to front-run their dump and crash the market before they do!
            item_tolerance = base_tolerance
            if hoarding.get(item):
                item_tolerance = min(1.0, item_tolerance + 0.15)
                
            min_acceptable_price = base_price * (1.0 - item_tolerance)
            
            allowed_qty = 0
            for q in range(requested):
                marginal_price = ENGINE._price(item, current_inv + q)
                if marginal_price < min_acceptable_price:
                    break
                allowed_qty += 1
                
            if allowed_qty > 0:
                order[2] = allowed_qty
                new_market.append(order)
        else:
            new_market.append(order)
            
    changed["market"] = new_market
    return changed

def _sweep_terminal_shed(obs: Any, seat: int, action: dict[str, Any]) -> dict[str, Any]:
    step = int(ENGINE._get(obs, "step", 0) or 0)
    # Phase D: Terminal Liquidation Guarantee. Sweep on both 718 and 719.
    if step < MAX_STEPS - 2:
        return action
    
    # Calculate available inventory in shed after planned physical actions
    try:
        available, _ = PARENT.PARENT.PARENT.PARENT.BASE._project_shed(obs, seat, action)
    except Exception:
        farm = ENGINE._get(obs, "farms", [])[seat]
        available = dict(ENGINE._get(farm, "inventory", {}) or {})
        
    for order in action.get("market") or []:
        if len(order) >= 3 and order[0] == "SELL":
            item = str(order[1])
            available[item] = max(0, int(available.get(item, 0)) - max(0, int(order[2] or 0)))
            
    market = ENGINE._get(obs, "market", {}) or {}
    raw_inventory = ENGINE._get(market, "inventory", {}) or {}
    
    ranked = []
    for item in ALL_SWEEP_PRODUCTS:
        quantity = max(0, int(available.get(item, 0)))
        if not quantity:
            continue
        mkt_inv = int(ENGINE._get(raw_inventory, item, ENGINE.I0) or ENGINE.I0)
        rev = _revenue(item, mkt_inv, quantity)
        ranked.append((rev, item, quantity))
        
    ranked.sort(reverse=True)
    
    changed = ENGINE._copy_action(action)
    existing_orders = list(changed.get("market") or [])
    room = max(0, ENGINE.MAX_MARKET_ORDERS - len(existing_orders))
    
    for _, item, quantity in ranked[:room]:
        existing_orders.append(["SELL", item, quantity])
        
    changed["market"] = existing_orders[:ENGINE.MAX_MARKET_ORDERS]
    return changed

def _phantom_supply_injection(obs: Any, seat: int) -> dict[str, Any]:
    """
    Phase E: Phantom Supply Injection / Adversarial Planting.
    Scans the opponent's farm for planted crops. If they have significant crop counts,
    we artificially inject those counts into the market inventory of a fake observation.
    This 'scares' the base agent's ROI calculator into diversifying away from monocultures
    that the opponent is already monopolizing.
    """
    fake_obs = copy.deepcopy(obs)
    opp_seat = 1 - seat
    farms = ENGINE._get(fake_obs, "farms", [])
    if opp_seat >= len(farms):
        return fake_obs
        
    opp_farm = farms[opp_seat]
    tiles = ENGINE._get(opp_farm, "tiles", [])
    
    opp_crops = {}
    if isinstance(tiles, list):
        for row in tiles:
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, dict) and cell.get("kind") == "PLANT":
                        crop = str(cell.get("crop") or "").upper()
                        if crop:
                            opp_crops[crop] = opp_crops.get(crop, 0) + 1
                            
    market = ENGINE._get(fake_obs, "market", {})
    if not isinstance(market, dict):
        return fake_obs
    inventory = ENGINE._get(market, "inventory", {})
    if not isinstance(inventory, dict):
        return fake_obs
        
    for crop, count in opp_crops.items():
        current_inv = int(ENGINE._get(inventory, crop, 0) or 0)
        inventory[crop] = current_inv + count
        
    market["inventory"] = inventory
    fake_obs["market"] = market
    
    return fake_obs

def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    try:
        seat = ENGINE._seat(obs)
        step = int(ENGINE._get(obs, "step", 0) or 0)
        
        # Phase E: Inject opponent's future supply into a fake observation
        # so the base agent naturally diversifies to avoid price crashes.
        fake_obs = _phantom_supply_injection(obs, seat)
        base_action = PARENT.agent(fake_obs, configuration)
                
        budgeted_action = _capital_budgeting_filter(step, base_action)
        # We pass the REAL obs to our filters so they use exact truth for dumping
        priced_action = _exact_market_pricing_filter(obs, seat, budgeted_action)
        swept_action = _sweep_terminal_shed(obs, seat, priced_action)
        final_action = _sanitize_coops(swept_action)
        return final_action
    except Exception:
        try:
            farms = list(ENGINE._get(obs, "farms", []) or [])
            seat = ENGINE._seat(obs)
            num_hands = len(ENGINE._get(farms[seat] if seat < len(farms) else {}, "hands", []) or [])
            return {
                "farmer": ["PASS"],
                "hands": [["PASS"] for _ in range(num_hands)],
                "market": [],
            }
        except Exception:
            return {"farmer": ["PASS"], "hands": [], "market": []}

e777a_agent = agent
