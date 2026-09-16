#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Analyze spatial efficiency and lifecycle of all 100 tiles in Route 0 and Route 13."""

import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments
from modular_apex import main

def analyze():
    print("Running Route 0 / Route 13 spatial analysis on Seed 42...")
    env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env.run([main.agent, "pass"])
    
    # Track each tile: (x, y) -> list of events (planted, watered, harvested, kind)
    tile_history = defaultdict(lambda: {
        "crops": [],
        "animals": [],
        "total_yield": 0,
        "first_used_step": None,
        "last_used_step": None,
        "quadrant": None
    })
    
    for step_idx, step in enumerate(env.steps):
        farm = step[0]["observation"]["farms"][0]
        tiles = farm["tiles"]
        for y in range(10):
            for x in range(10):
                t = tiles[y][x]
                if t == "LOCKED":
                    continue
                q = "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))
                tile_history[(x, y)]["quadrant"] = q
                if isinstance(t, dict):
                    if tile_history[(x, y)]["first_used_step"] is None:
                        tile_history[(x, y)]["first_used_step"] = step_idx
                    tile_history[(x, y)]["last_used_step"] = step_idx
                    kind = t.get("kind")
                    if kind == "PLANT":
                        c = t.get("crop")
                        if not tile_history[(x, y)]["crops"] or tile_history[(x, y)]["crops"][-1] != c:
                            tile_history[(x, y)]["crops"].append(c)
                    elif kind in ("COOP", "PASTURE"):
                        a = t.get("animal")
                        if a and (not tile_history[(x, y)]["animals"] or tile_history[(x, y)]["animals"][-1] != a):
                            tile_history[(x, y)]["animals"].append(a)

    print("\n--- Quadrant Utilization Summary ---")
    quad_counts = defaultdict(lambda: {"total": 25, "used": 0, "crops": defaultdict(int), "animals": defaultdict(int)})
    for (x, y), info in tile_history.items():
        q = info["quadrant"]
        if info["first_used_step"] is not None:
            quad_counts[q]["used"] += 1
            for c in info["crops"]:
                quad_counts[q]["crops"][c] += 1
            for a in info["animals"]:
                quad_counts[q]["animals"][a] += 1

    for q in ["NW", "NE", "SW", "SE"]:
        u = quad_counts[q]
        print(f"Quadrant {q}: {u['used']:2d}/25 tiles used | Crops: {dict(u['crops'])} | Animals: {dict(u['animals'])}")

    print("\n--- Full 10x10 Board Layout ---")
    grid = [["  .  " for _ in range(10)] for _ in range(10)]
    for (x, y), info in tile_history.items():
        label = "."
        if info["animals"]:
            label = f"{info['animals'][-1][:2]}(A)"
        elif info["crops"]:
            label = f"{info['crops'][-1][:2]}(C)"
        grid[y][x] = f"{label:^5}"

    for r in range(10):
        print(f"Row {r:2d}: " + "".join(grid[r]))

if __name__ == "__main__":
    analyze()
