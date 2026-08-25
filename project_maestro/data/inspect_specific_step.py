"""Inspect step 47, 48, 49 in 93924742.json"""

import json

def inspect_step(path, target_step):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    steps = data["steps"]
    for s_idx in [target_step - 1, target_step, target_step + 1]:
        print(f"\n=================== STEP {s_idx} ===================")
        for p in [0, 1]:
            s_data = steps[s_idx][p]
            obs = s_data.get("observation", {})
            act = s_data.get("action", {})
            reward = s_data.get("reward")
            status = s_data.get("status")
            print(f"Player {p}: Status={status}, Reward={reward}")
            farm = obs.get("farms", [{}, {}])[p]
            print(f"  Farm money: {farm.get('money')}")
            print(f"  Action: {act}")
            print(f"  Private Shed: {obs.get('private', {}).get('shed')}")
            print(f"  Private Invs: {obs.get('private', {}).get('inventories')}")

if __name__ == "__main__":
    inspect_step(r"C:\Coding\kaggriculture-agent\replays\93924742.json", 48)
