import base64
import json
import zlib

with open(r'C:\Coding\project_aegis\tape_loader.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('_MILK_SUPPORT_SHOPS')
blobs = text[:idx]

updated_logic = '''_MILK_SUPPORT_SHOPS: Set[str] = {
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "ICE_CREAM_SHOP",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
}

_CACHED_TAPES: Dict[str, List[Dict[str, Any]]] = {}
_COMMITTED_ROUTE: Dict[int, Optional[str]] = {0: None, 1: None}

def get_base_tape(route_name: str = "8c6s_3q") -> List[Dict[str, Any]]:
    """Lazily loads and returns the requested base tape."""
    if route_name not in _CACHED_TAPES:
        if route_name == "6c12s_4q_first_yarn":
            _CACHED_TAPES[route_name] = _ACTIONS_6C12S_4Q_FIRST_YARN
        elif route_name == "6c12s_4q_second_yarn":
            _CACHED_TAPES[route_name] = _ACTIONS_6C12S_4Q_SECOND_YARN
        elif route_name == "6c8s_3q":
            _CACHED_TAPES[route_name] = _ACTIONS_6C8S_3Q
        elif route_name == "10c4s_3q":
            _CACHED_TAPES[route_name] = _ACTIONS_10C4S_3Q
        else:
            _CACHED_TAPES[route_name] = _ACTIONS_8C6S_3Q
    return _CACHED_TAPES[route_name]

def select_active_tape(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Selects and locks the optimal route based on Town Shop rolls at Day 3 / Day 6.
    Permanently locks the route by Day 6 (Step 144) to prevent late animal layout oscillation.
    """
    step = int(obs.get("step", 0) or 0)
    player = int(obs.get("player", 0) or 0)

    if step == 0:
        _COMMITTED_ROUTE[player] = None

    if _COMMITTED_ROUTE[player] is not None and step >= 144:
        return get_base_tape(_COMMITTED_ROUTE[player])

    shops = (obs.get("town") or {}).get("unlocked_shops", []) or []

    # 1. First shop on Day 3
    if len(shops) >= 1:
        if shops[:1] == ["YARN_STORE"]:
            _COMMITTED_ROUTE[player] = "6c12s_4q_first_yarn"
            return get_base_tape("6c12s_4q_first_yarn")
        if _MILK_SUPPORT_SHOPS.intersection(shops[:1]):
            _COMMITTED_ROUTE[player] = "10c4s_3q"
            return get_base_tape("10c4s_3q")

    # 2. Second shop on Day 6
    if len(shops) >= 2:
        if "YARN_STORE" in shops[:2]:
            _COMMITTED_ROUTE[player] = "6c12s_4q_second_yarn"
            return get_base_tape("6c12s_4q_second_yarn")
        if _MILK_SUPPORT_SHOPS.intersection(shops[:2]):
            _COMMITTED_ROUTE[player] = "10c4s_3q"
            return get_base_tape("10c4s_3q")

    # 3. Third shop fallback before Step 144
    if len(shops) >= 3 and "YARN_STORE" in shops[:3] and step < 144:
        _COMMITTED_ROUTE[player] = "6c8s_3q"
        return get_base_tape("6c8s_3q")

    default_route = "10c4s_3q" if _MILK_SUPPORT_SHOPS.intersection(shops[:3]) else "8c6s_3q"
    if step >= 144:
        _COMMITTED_ROUTE[player] = default_route
    return get_base_tape(default_route)

def get_lookahead_scheduled_sells(
    tape: List[Dict[str, Any]],
    current_step: int,
    lookahead_steps: int = 96
) -> Dict[str, Tuple[int, int]]:
    scheduled: Dict[str, Tuple[int, int]] = {}
    for i in range(1, lookahead_steps + 1):
        idx = current_step + i
        if idx >= len(tape):
            break
        for order in tape[idx].get("market", []) or []:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = max(0, int(order[2] or 0))
                if item not in scheduled and qty > 0:
                    scheduled[item] = (idx, qty)
    return scheduled
'''

full_code = blobs + updated_logic

with open(r'C:\Coding\project_aegis\tape_loader.py', 'w', encoding='utf-8') as f:
    f.write(full_code)

print("Updated project_aegis/tape_loader.py with Sticky Route Commitment.")
