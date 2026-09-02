"""Identity-free weed transaction repair for fixed-route research policies."""

from __future__ import annotations

import copy

from v19_terminal import align_hands


def _tile(farm, position):
    try:
        x, y = int(position[0]), int(position[1])
        return (farm.get("tiles", []) or [])[y][x]
    except (IndexError, TypeError, ValueError):
        return "LOCKED"


def _trace_action(base_actions, step, actor):
    trace = base_actions[min(max(int(step), 0), len(base_actions) - 1)] or {}
    if actor == "farmer":
        return copy.deepcopy(trace.get("farmer", ["PASS"]) or ["PASS"])
    hands = trace.get("hands", []) or []
    return copy.deepcopy(hands[actor] if actor < len(hands) else ["PASS"])


def wrap_weed_repair(policy, base_actions, *, replay_steps=8, stop_on_match=False):
    """Turn a failed build/plant-on-weed into a bounded route transaction.

    At collision time the actor DIGs.  On the next turn it retries the intended
    action, then replays that actor's previous fixed-route actions for a bounded
    number of turns.  Market actions and every unaffected actor are untouched.
    """
    replay_steps = max(0, int(replay_steps))
    states = {0: {}, 1: {}}
    telemetry = {
        "games": 0,
        "collisions": 0,
        "dig_actions": 0,
        "retry_actions": 0,
        "replay_actions": 0,
        "early_matches": 0,
        "expired_transactions": 0,
        "by_operation": {},
    }

    def wrapped(obs):
        step = max(0, int(obs.get("step", 0) or 0))
        seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
        game = states[seat]
        if step == 0 or step < game.get("last_step", -1):
            game = {"last_step": step, "active": {}}
            states[seat] = game
            telemetry["games"] += 1
        game["last_step"] = step

        action = align_hands(copy.deepcopy(policy(obs) or {}), obs)
        farms = list(obs.get("farms", []) or [])
        farm = farms[seat] if seat < len(farms) else {}
        positions = [farm.get("farmer"), *(farm.get("hands", []) or [])]
        unit_actions = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or [])]
        active = game["active"]

        for actor, transaction in list(active.items()):
            index = 0 if actor == "farmer" else int(actor) + 1
            if index >= len(unit_actions):
                active.pop(actor, None)
                telemetry["expired_transactions"] += 1
                continue
            age = step - transaction["start"]
            if age == 1:
                unit_actions[index] = copy.deepcopy(transaction["intended"])
                telemetry["retry_actions"] += 1
                continue
            if 2 <= age <= 1 + replay_steps:
                previous = _trace_action(base_actions, step - 1, actor)
                if stop_on_match and unit_actions[index] == previous:
                    active.pop(actor, None)
                    telemetry["early_matches"] += 1
                    continue
                unit_actions[index] = previous
                telemetry["replay_actions"] += 1
                continue
            active.pop(actor, None)
            telemetry["expired_transactions"] += 1

        for index, (position, intended) in enumerate(zip(positions, unit_actions)):
            actor = "farmer" if index == 0 else index - 1
            if actor in active or not isinstance(intended, list) or not intended:
                continue
            operation = intended[0]
            if operation not in ("BUILD_PASTURE", "PLANT"):
                continue
            tile = _tile(farm, position)
            if not isinstance(tile, dict) or tile.get("kind") != "WEED":
                continue
            active[actor] = {
                "start": step,
                "intended": copy.deepcopy(intended),
            }
            unit_actions[index] = ["DIG"]
            telemetry["collisions"] += 1
            telemetry["dig_actions"] += 1
            counts = telemetry["by_operation"]
            counts[operation] = counts.get(operation, 0) + 1

        action["farmer"] = unit_actions[0] if unit_actions else ["PASS"]
        action["hands"] = unit_actions[1:]
        return align_hands(action, obs)

    wrapped.telemetry = telemetry
    wrapped.replay_steps = replay_steps
    wrapped.stop_on_match = bool(stop_on_match)
    return wrapped
