#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test and calibrate Mass Dumping Market Crashing Strategy against an active opponent."""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments
from modular_apex import chassis, config, payload, router

def run_experiment():
    routes = payload.load_routes()
    base_tape = routes[0]
    
    # 1. Clean Route 0 (No Geese, Tomato + Crops)
    from develop_crop_pizza_dump_engine import build_sanitized_route0, build_route13_pizza_se_expansion
    
    r0 = build_sanitized_route0(base_tape)
    r13 = build_route13_pizza_se_expansion(r0)
    
    test_routes = copy.deepcopy(routes)
    test_routes[0] = r0
    test_routes[13] = r13
    
    def test_router(obs, step, st):
        if step >= config.FINAL_PLAN_STEP and not st.get("day27"):
            st["route"] = 2
            st["day27"] = True
            return 2
        shops = (obs.get("town", {}) or {}).get("unlocked_shops", []) or []
        if shops.count("PIZZA_SHOP") >= 2:
            st["route"] = 13
            return 13
        if step >= config.ROUTE_STEP and not st.get("day6"):
            pair = tuple(shops[:2])
            st["route"] = router.SHOP_PLANS.get(pair, 0)
            st["day6"] = True
        return st.get("route", 0)

    # Baseline Agent without active opponent crash layer
    agent_base = chassis.make_agent(test_routes, router=test_router, **config.CHASSIS_SETTINGS)
    
    # Let's run a match between our agent and an opponent that grows crops (e.g. starter_agent or another instance)
    env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env.run([agent_base, "starter"])
    p0_rew = env.steps[-1][0]["reward"] or 0
    p1_rew = env.steps[-1][1]["reward"] or 0
    print(f"Match vs Starter (Seed 42): P0 (Us) = ${p0_rew:,.0f} | P1 (Starter) = ${p1_rew:,.0f}")

    # Now let's see vs self (mirror match)
    agent_p1 = chassis.make_agent(test_routes, router=test_router, **config.CHASSIS_SETTINGS)
    env2 = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env2.run([agent_base, agent_p1])
    print(f"Mirror Match (Seed 42): P0 = ${env2.steps[-1][0]['reward']:,.0f} | P1 = ${env2.steps[-1][1]['reward']:,.0f}")

if __name__ == "__main__":
    run_experiment()
