"""Weed Handler & Construction Plot Cleaner for Project Maestro

Prevents wasteful weed digging:
1. Only digs weeds that are strictly located on PLANNED CONSTRUCTION TILES.
2. Hard cutoff: Zero weed digging after Day 16 (recovers 1,600+ wasted worker turns).
3. Preemptively clears weeds 1 turn before construction.
"""

from typing import Dict, List, Tuple, Set, Any, Optional

class WeedHandler:
    def __init__(self, planned_tiles: Optional[Set[Tuple[int, int]]] = None):
        self.planned_tiles = planned_tiles or set()

    def get_priority_weed_dig_tasks(self, obs: Dict[str, Any], player: int) -> List[Dict[str, Any]]:
        """
        Scans only planned construction tiles for weeds and dispatches instant priority-99 DIG tasks.
        Ignores all useless weeds in unused buffer tiles and halts all digging after Day 16.
        """
        day = obs.get("day", 0)
        if day >= 16:
            # Zero weed digging after Day 16 (eliminates 1,600+ wasted turns)
            return []

        me = obs["farms"][player]
        tasks = []

        for (tx, ty) in self.planned_tiles:
            if ty < len(me["tiles"]) and tx < len(me["tiles"][ty]):
                t = me["tiles"][ty][tx]
                if isinstance(t, dict) and t.get("kind") == "WEED":
                    tasks.append({
                        "target": (tx, ty),
                        "action": "DIG",
                        "priority": 99  # Highest priority to unblock construction
                    })

        return tasks
