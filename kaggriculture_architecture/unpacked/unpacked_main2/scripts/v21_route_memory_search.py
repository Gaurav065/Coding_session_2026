from __future__ import annotations
import copy
PASS = {"farmer": ["PASS"], "hands": [], "market": []}
def replay_policy(actions):
    def policy(obs):
        step = min(max(0, int(obs.get("step", 0) or 0)), len(actions) - 1)
        return copy.deepcopy(actions[step] or PASS)
    return policy
