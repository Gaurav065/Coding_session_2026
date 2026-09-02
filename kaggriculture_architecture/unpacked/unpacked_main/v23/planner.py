"""Promoted sparse closed-loop policy after v23 ablations."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from scripts.v21_route_memory_search import replay_policy
from scripts.v22_weed_repair import wrap_weed_repair
from v23.policy_library import reorder_sell_slots
from v23.state_encoder import get, regime_from_configuration


@dataclass(frozen=True)
class PlannerConfig:
    weed_replay_steps: int = 8
    rebalance_demand_alpha: float = 0.25


def build_sparse_planner(actions, config: PlannerConfig = PlannerConfig()):
    """Open-loop farm backbone plus the two promoted feedback events.

    * Legacy configuration: exact v22 price-impact SELL-slot ordering.
    * PR #1394 configuration: demand-recovery-adjusted SELL-slot ordering.

    Route switching and quantity MPC are deliberately absent because their
    seed-grouped holdouts did not improve wins.
    """
    base = wrap_weed_repair(
        replay_policy(copy.deepcopy(actions)),
        copy.deepcopy(actions),
        replay_steps=config.weed_replay_steps,
    )
    telemetry = {
        "games": 0,
        "legacy_turns": 0,
        "rebalance_turns": 0,
        "reordered_turns": 0,
    }
    last_step = {0: -1, 1: -1}

    def agent(obs, configuration=None):
        seat = int(get(obs, "player", 0) or 0)
        step = int(get(obs, "step", 0) or 0)
        if step == 0 or step < last_step[seat]:
            telemetry["games"] += 1
        last_step[seat] = step
        action = base(obs)
        regime = regime_from_configuration(configuration)
        if regime == "rebalance":
            telemetry["rebalance_turns"] += 1
            alpha = config.rebalance_demand_alpha
        else:
            telemetry["legacy_turns"] += 1
            alpha = 0.0
        result = reorder_sell_slots(
            obs, action, configuration, demand_alpha=alpha
        )
        telemetry["reordered_turns"] += result.get("market") != action.get("market")
        return result

    agent.telemetry = telemetry
    agent.planner_config = config
    return agent


def build_dual_regime_planner(
    legacy_actions,
    rebalance_actions,
    config: PlannerConfig = PlannerConfig(),
):
    """Select one validated backbone from the official engine configuration.

    The selection happens at the environment-regime boundary, not from noisy
    within-game prices.  Legacy uses the strongest strict-future current-meta
    route; the announced PR #1394 regime uses the route that was most robust on
    seed-grouped rebalance holdouts.  Both retain the same sparse market loop.
    """
    legacy = build_sparse_planner(copy.deepcopy(legacy_actions), config)
    rebalance = build_sparse_planner(copy.deepcopy(rebalance_actions), config)
    telemetry = {"legacy_calls": 0, "rebalance_calls": 0}

    def agent(obs, configuration=None):
        regime = regime_from_configuration(configuration)
        if regime == "rebalance":
            telemetry["rebalance_calls"] += 1
            return rebalance(obs, configuration)
        telemetry["legacy_calls"] += 1
        return legacy(obs, configuration)

    agent.telemetry = telemetry
    agent.legacy_planner = legacy
    agent.rebalance_planner = rebalance
    agent.planner_config = config
    return agent
