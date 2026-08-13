# =============================================================================
# PHASE 3: LIGHTWEIGHT MCTS FOR STRATEGIC DECISIONS
# Drop this into main.py after the REPLAY_DUMP_STATS definition
# =============================================================================

import time
import random
import math

# -----------------------------------------------------------------------------
# Strategic Action Space
# Each action represents a high-level strategic pivot for the next ~5 days
# -----------------------------------------------------------------------------
STRATEGIC_ACTIONS = [
    ("MAINTAIN",),
    ("PIVOT_FROM", "FERTILIZER"),
    ("PIVOT_FROM", "EGG"),
    ("PIVOT_FROM", "WHEAT"),
    ("PIVOT_FROM", "MILK"),
    ("PIVOT_FROM", "WOOL"),
    ("PIVOT_TO", "STRAWBERRY"),
    ("PIVOT_TO", "MELON"),
    ("PIVOT_TO", "MILK"),
    ("PIVOT_TO", "WOOL"),
    ("HOARD", "FERTILIZER"),
    ("HOARD", "STRAWBERRY"),
    ("HOARD", "MELON"),
    ("SHORT", "WHEAT"),
    ("SHORT", "FERTILIZER"),
    ("BUY_LAND",),
    ("HIRE_HANDS",),
]

# -----------------------------------------------------------------------------
# MCTS Node
# -----------------------------------------------------------------------------
class MCTSNode:
    __slots__ = ("state_hash", "parent", "children", "visits", "value", 
                 "action", "depth", "untried_actions")
    
    def __init__(self, state_hash, parent=None, action=None):
        self.state_hash = state_hash          # Compressed state representation
        self.parent = parent                  # Parent MCTSNode
        self.children = {}                    # action -> MCTSNode
        self.visits = 0                       # Visit count
        self.value = 0.0                      # Cumulative value
        self.action = action                  # Action that led to this node
        self.depth = 0 if parent is None else parent.depth + 1
        self.untried_actions = None           # Lazy initialization


# -----------------------------------------------------------------------------
# State Compression (for fast hashing/dict keys)
# -----------------------------------------------------------------------------
def compress_state(st, plan):
    """Compress observable state into a 64-bit integer for transposition table."""
    # Buckets: day(5b), money_bin(6b), animals(4b each), crop_counts(3b each), market_inv_bins(4b each)
    h = st.day
    h = (h << 6) | min(63, int(st.money // 5000))
    h = (h << 4) | min(15, plan["have"]["COW"])
    h = (h << 4) | min(15, plan["have"]["SHEEP"])
    h = (h << 4) | min(15, plan["have"]["GOOSE"])
    for crop in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"):
        cnt = sum(1 for row in st.tiles for t in row if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == crop)
        h = (h << 3) | min(7, cnt)
    for prod in ("FERTILIZER", "EGG", "MILK", "WOOL", "WHEAT"):
        inv_bin = min(15, int(st.minv.get(prod, 0) // 500))
        h = (h << 4) | inv_bin
    return h


# -----------------------------------------------------------------------------
# Opponent Dump Prediction (replay-informed)
# -----------------------------------------------------------------------------
def predict_opp_dumps(market_inv, day, current_dumps):
    """Returns dict {product: dump_qty} for the next horizon days."""
    dumps = {}
    for item, stats in REPLAY_DUMP_STATS.items():
        if current_dumps.get(item, False):
            # Already dumping - continue at observed rate
            dumps[item] = stats["avg_dump_qty"] / max(1, stats.get("duration", 10))
        elif day >= stats["trigger_day"] and market_inv.get(item, 0) >= stats["trigger_inv"]:
            # Probability-based trigger
            if random.random() < stats["prob"]:
                dumps[item] = stats["avg_dump_qty"] / max(1, stats.get("duration", 10))
    return dumps


# -----------------------------------------------------------------------------
# Fast Forward Simulation (5-day horizon)
# -----------------------------------------------------------------------------
SIM_HORIZON = 5

def simulate(st, plan, strategic_action, seed=None):
    """
    Deterministic rollout: simulates market + our production + opponent response
    for SIM_HORIZON days. Returns estimated terminal wealth (money + inventory value).
    """
    if seed is not None:
        random.seed(seed)
    
    # ---- Clone mutable state ----
    money = st.money
    animals = dict(plan["have"])
    market_inv = dict(st.minv)
    pipeline = dict(plan["pipeline"])
    crop_targets = dict(plan.get("crop_targets", {}))
    opp_dumps_active = dict(plan.get("opp_dump", {}))
    
    # ---- Apply strategic action effects ----
    action_type = strategic_action[0]
    
    if action_type == "PIVOT_FROM":
        item = strategic_action[1]
        # Liquidate reserves, stop production
        market_inv[item] = market_inv.get(item, 0) + pipeline.get(item, 0)
        pipeline[item] = 0
        if item in crop_targets:
            # Recover seed money
            money += crop_targets[item] * CROPS[item]["seed"]
            crop_targets[item] = 0
    
    elif action_type == "PIVOT_TO":
        item = strategic_action[1]
        # Boost production targets
        if item in CROPS:
            crop_targets[item] = crop_targets.get(item, 0) + 3
        # Reserve budget implicitly handled by MAV selection
    
    elif action_type == "HOARD":
        item = strategic_action[1]
        # Don't sell - reserve = inf
        pass  # Handled by reserve adjustment in plan
    
    elif action_type == "SHORT":
        item = strategic_action[1]
        # Buy from market instead of producing
        if item in crop_targets:
            crop_targets[item] = 0
    
    elif action_type == "BUY_LAND":
        if len(st.unlocked) < 4:
            cost = (1000, 2000, 4000)[len(st.unlocked) - 1]
            if money >= cost:
                money -= cost
    
    elif action_type == "HIRE_HANDS":
        # Extra hands implicitly increase action capacity
        pass
    
    # ---- Daily simulation loop ----
    daily_drain = dict(plan["rate"])  # town drain per day
    wheat_price = market_price("WHEAT", market_inv.get("WHEAT", 0))
    
    for day_offset in range(SIM_HORIZON):
        current_day = st.day + day_offset
        days_left = max(1, st.days_left - day_offset)
        
        # 1. Opponent dumps
        new_dumps = predict_opp_dumps(market_inv, current_day, opp_dumps_active)
        for item, qty in new_dumps.items():
            market_inv[item] = market_inv.get(item, 0) + qty
            opp_dumps_active[item] = True
        
        # 2. Our production enters market
        for item, qty in pipeline.items():
            if days_left > 0:
                market_inv[item] = market_inv.get(item, 0) + qty / days_left
        
        # 3. Town drain
        for item, rate in daily_drain.items():
            market_inv[item] = max(0, market_inv.get(item, 0) - rate)
        
        # 4. Our sales revenue (sell down to reserve)
        for item in PRODUCTS:
            reserve = plan["reserve"].get(item, 1)
            inv = market_inv.get(item, 0)
            sellable = units_sellable(item, inv, reserve, 9999)
            if sellable > 0:
                price = market_price(item, inv - sellable + 1)  # approx avg price
                money += sellable * price
                market_inv[item] -= sellable
        
        # 5. Operating costs
        total_animals = sum(animals.values())
        feed_cost = total_animals * wheat_price
        money -= feed_cost
        
        # Hand costs (Fibonacci)
        hands_est = max(1, int(total_animals * 2.8 / 13 + len(crop_targets) * 1.5 / 13))
        hand_cost = get_fib_cost(hands_est)
        money -= hand_cost
        
        # 6. Pipeline decay (products produced this simulation)
        for item in pipeline:
            if pipeline[item] > 0:
                pipeline[item] *= 0.8  # Remaining production decreases
    
    # ---- Terminal value: cash + inventory value at final prices ----
    terminal_value = money
    for item, inv in market_inv.items():
        if inv > 0:
            terminal_value += inv * market_price(item, inv)
    for item, count in animals.items():
        if count > 0:
            # Rough animal asset value
            terminal_value += count * ANIMALS[item]["cost"] * 0.5
    
    return terminal_value


# -----------------------------------------------------------------------------
# MCTS Search Loop (100ms budget)
# -----------------------------------------------------------------------------
MCTS_TIME_BUDGET_MS = 100
MCTS_EXPLORATION = 1.414  # sqrt(2)

def mcts_search(root_state_hash, st, plan, time_budget_ms=MCTS_TIME_BUDGET_MS):
    """
    Runs UCT search from root state. Returns best strategic action.
    """
    root = MCTSNode(root_state_hash)
    root.untried_actions = list(STRATEGIC_ACTIONS)
    
    start_time = time.time()
    deadline = start_time + time_budget_ms / 1000.0
    
    # Deterministic seed per search for reproducibility
    search_seed = hash((root_state_hash, st.day)) & 0x7FFFFFFF
    
    while time.time() < deadline:
        # 1. SELECTION
        node = root
        while node.untried_actions is None or len(node.untried_actions) == 0:
            if not node.children:
                break
            # UCT selection
            best_score = -float('inf')
            best_child = None
            for child in node.children.values():
                if child.visits == 0:
                    score = float('inf')
                else:
                    exploit = child.value / child.visits
                    explore = MCTS_EXPLORATION * math.sqrt(math.log(node.visits) / child.visits)
                    score = exploit + explore
                if score > best_score:
                    best_score = score
                    best_child = child
            if best_child is None:
                break
            node = best_child
        
        # 2. EXPANSION
        if node.untried_actions is not None and node.untried_actions:
            action = node.untried_actions.pop()
            child_hash = (node.state_hash ^ hash(action)) & 0xFFFFFFFFFFFFFFFF
            child = MCTSNode(child_hash, parent=node, action=action)
            node.children[action] = child
            node = child
            node.untried_actions = list(STRATEGIC_ACTIONS)  # Full branching
        
        # 3. SIMULATION
        sim_seed = (search_seed ^ node.state_hash) & 0x7FFFFFFF
        value = simulate(st, plan, node.action, seed=sim_seed)
        
        # 4. BACKPROPAGATION
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
    
    # Return most-visited action (robust to noise)
    if not root.children:
        return ("MAINTAIN",)
    
    best_action = max(root.children.items(), key=lambda kv: kv[1].visits)[0]
    return best_action


# -----------------------------------------------------------------------------
# Strategic Action Application
# -----------------------------------------------------------------------------
def apply_strategic_action(plan, action, st):
    """Mutates plan based on chosen strategic action."""
    action_type = action[0]
    
    if action_type == "PIVOT_FROM":
        item = action[1]
        plan["reserve"][item] = 1
        plan["head"][item] = 0
        plan["pipeline"][item] = 0
        # Boost premium alternatives
        for alt in ("STRAWBERRY", "MELON", "MILK", "WOOL"):
            if alt != item and not plan.get("opp_dump", {}).get(alt, False):
                plan["head"][alt] = int(plan["head"].get(alt, 0) * 1.5)
                plan["reserve"][alt] = int(plan["reserve"].get(alt, 1) * 1.2)
    
    elif action_type == "PIVOT_TO":
        item = action[1]
        plan["head"][item] = int(plan["head"].get(item, 0) * 2.0)
        plan["reserve"][item] = int(plan["reserve"].get(item, 1) * 1.3)
    
    elif action_type == "HOARD":
        item = action[1]
        plan["reserve"][item] = 9999  # Never sell
    
    elif action_type == "SHORT":
        item = action[1]
        if item in plan.get("crop_targets", {}):
            plan["crop_targets"][item] = 0
        plan["reserve"][item] = 1  # Liquidate any stock
    
    elif action_type == "BUY_LAND":
        plan["buy_land"] = True
    
    elif action_type == "HIRE_HANDS":
        plan["hands"] = min(plan.get("hands", 0) + 1, P["max_hands"])
    
    # MAINTAIN: no changes


# -----------------------------------------------------------------------------
# Integration Hook (call from build_plan every N days or on dump detection)
# -----------------------------------------------------------------------------
def run_strategic_mcts(st, plan):
    """Entry point: runs MCTS and applies best action to plan."""
    state_hash = compress_state(st, plan)
    needs_search = (
        st.day % 3 == 0 or  # Periodic re-evaluation
        any(plan.get("opp_dump", {}).values()) or  # Reactive to dumps
        st.day <= 5  # Early game
    )
    if not needs_search:
        return
    
    best_action = mcts_search(state_hash, st, plan)
    apply_strategic_action(plan, best_action, st)
    
    # Debug
    if st.hour == 0:
        with open("debug_mcts.log", "a") as f:
            f.write(f"Day {st.day} MCTS: {best_action}\n")