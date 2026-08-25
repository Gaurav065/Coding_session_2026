import json
import os

replay_path = r"C:\Users\GauravPatel\Downloads\top_player\94401941.json"

with open(replay_path, "r", encoding="utf-8") as f:
    data = json.load(f)

team_names = data.get("info", {}).get("TeamNames", ["", ""])
seat = 0 if team_names[0] == "Ryo Hasegawa" else 1

steps = data.get("steps", [])
print(f"Replay: 94401941 | Ryo Seat: {seat} | Total Steps: {len(steps)}")
print(f"Final Reward: Ryo = ${steps[-1][seat]['reward']:,.0f} vs Opp = ${steps[-1][1-seat]['reward']:,.0f}")

# Inspect all market actions across all 720 steps for Ryo
market_events = []
for step_idx, step_data in enumerate(steps):
    action = step_data[seat].get("action") or {}
    market = action.get("market", [])
    if market:
        obs = step_data[seat].get("observation", {})
        money = obs.get("farms", [{}, {}])[seat].get("money", 0)
        shed = obs.get("private", {}).get("shed", {})
        market_events.append((step_idx, money, shed, market))

print(f"\nTotal turns with market orders: {len(market_events)}")
print("\nFirst 15 Market Orders:")
for s, m, sh, orders in market_events[:15]:
    print(f"  Step {s:03d} (Day {s//24:02d} Hr {s%24:02d}): Money=${m:6,.1f} | Shed={sh} | Orders={orders}")

print("\nSample Mid-Game Market Orders (Steps 200-400):")
for s, m, sh, orders in [e for e in market_events if 200 <= e[0] <= 400][:15]:
    print(f"  Step {s:03d} (Day {s//24:02d} Hr {s%24:02d}): Money=${m:6,.1f} | Shed={sh} | Orders={orders}")

print("\nFinal 10 Market Orders (Terminal Phase):")
for s, m, sh, orders in market_events[-10:]:
    print(f"  Step {s:03d} (Day {s//24:02d} Hr {s%24:02d}): Money=${m:6,.1f} | Shed={sh} | Orders={orders}")
