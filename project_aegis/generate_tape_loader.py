import base64
import zlib

with open(r'C:\Users\GauravPatel\Downloads\multi_route_agent_files\decoded_agent.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
blob_lines = [l for l in lines if l.startswith('_ACTIONS_')]

header = '''"""Project Aegis - Module 4: Base Tape Multi-Route Loader & Oracle Selector

Embeds verified, high-scoring mathematical base tapes compressed via base85 + zlib.
Provides dynamic town-shop matching and lookahead sell-schedule inspection for The Predator.
"""

import base64
import json
import zlib
from typing import Dict, List, Any, Optional, Tuple, Set

'''

loader_code = '''
_MILK_SUPPORT_SHOPS: Set[str] = {
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "ICE_CREAM_SHOP",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
}

_CACHED_TAPES: Dict[str, List[Dict[str, Any]]] = {}

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
    """Selects optimal route based on Town Shop rolls at Day 3 / Day 6."""
    shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
    if shops[:1] == ["YARN_STORE"]:
        return get_base_tape("6c12s_4q_first_yarn")
    if "YARN_STORE" in shops[:2]:
        return get_base_tape("6c12s_4q_second_yarn")
    if "YARN_STORE" in shops[:3]:
        return get_base_tape("6c8s_3q")
    if _MILK_SUPPORT_SHOPS.intersection(shops[:3]):
        return get_base_tape("10c4s_3q")
    return get_base_tape("8c6s_3q")

def get_lookahead_scheduled_sells(
    tape: List[Dict[str, Any]],
    current_step: int,
    lookahead_steps: int = 96
) -> Dict[str, Tuple[int, int]]:
    """Scans upcoming tape steps to identify scheduled SELL orders.
    Returns mapping: item -> (scheduled_step, scheduled_quantity).
    """
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

full_content = header + "\n".join(blob_lines) + "\n\n" + loader_code

with open(r'C:\Coding\project_aegis\tape_loader.py', 'w', encoding='utf-8') as f:
    f.write(full_content)

print("Updated project_aegis/tape_loader.py successfully.")
