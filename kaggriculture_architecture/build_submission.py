import base64
import os

def build(model_path="ppo_kaggriculture_hrl.zip", out_path="submission.py"):
    if os.path.exists(model_path):
        with open(model_path, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")
    else:
        b64_str = "PLACEHOLDER_FOR_ZIP"
        
    with open("phase_f_dynamic_agent/phase_f_dispatcher.py", "r") as f:
        dispatcher_code = f.read()
        
    with open("hrl_heuristic_agent.py", "r") as f:
        heuristic_code = f.read()
        heuristic_code = heuristic_code.replace("from phase_f_dispatcher import PhaseFDispatcher", "")
        # Rename the inner agent so the main RL agent can be called 'agent'
        heuristic_code = heuristic_code.replace("def agent(", "def heuristic_agent(")
        
    submission_template = f"""import os
import sys
import base64
import numpy as np
import collections

# --- PHASE F DISPATCHER ---
{dispatcher_code}

# --- HRL HEURISTIC AGENT ---
{heuristic_code}

# --- RL INFERENCE LOGIC ---
try:
    from stable_baselines3 import PPO
except ImportError:
    import os
    os.system("pip install stable-baselines3")
    from stable_baselines3 import PPO

MODEL_BASE64 = b"{b64_str}"
MODEL = None

def get_macro_obs(obs):
    vec = np.zeros(50, dtype=np.float32)
    if not obs or "farms" not in obs: return vec
    player_idx = obs.get("player", 0)
    farm = obs["farms"][player_idx]
    priv = obs.get("private", {{}})
    shed = priv.get("shed", {{}})
    seeds = priv.get("seeds", {{}})
    market = obs.get("market", {{}})
    vec[0] = obs.get("step", 0) / 2000.0
    vec[1] = farm.get("money", 0) / 10000.0
    items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
    for i, item in enumerate(items):
        vec[2 + i] = shed.get(item, 0) / 100.0
        vec[13 + i] = seeds.get(item, 0) / 100.0
        vec[24 + i] = market.get("prices", {{}}).get(item, 0) / 100.0
    vec[35] = len(farm.get("hands", [])) / 10.0
    return vec

def update_target_portfolio(action):
    buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
    sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
    
    targets = {{}}
    for i, item in enumerate(buy_items[:5]): targets[item] = int(action[i] * 50)
    for i, item in enumerate(buy_items[5:]): targets[item] = int(action[i+5] * 20)
    hire_target = max(2, int(action[8] * 10))
    
    ratios = {{}}
    for i, item in enumerate(sell_items): ratios[item] = float(action[9+i])
        
    TARGET_PORTFOLIO["BUY_TARGETS"] = targets
    TARGET_PORTFOLIO["SELL_RATIOS"] = ratios
    TARGET_PORTFOLIO["HIRE_TARGET"] = hire_target

def agent(obs, config=None):
    global MODEL
    if MODEL is None:
        with open("/tmp/model.zip", "wb") as f:
            f.write(base64.b64decode(MODEL_BASE64))
        MODEL = PPO.load("/tmp/model.zip")
        
    step = obs.get("step", 0)
    if step % 24 == 0:
        macro_obs = get_macro_obs(obs)
        action, _ = MODEL.predict(macro_obs, deterministic=True)
        update_target_portfolio(action)
        
    return heuristic_agent(obs, config)
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(submission_template)
    print(f"Built {out_path}!")

if __name__ == "__main__":
    build()
