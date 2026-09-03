# 🚀 Kaggriculture Master Handoff Document (Phase 2 GPU)

**ATTENTION GEMINI AGENT**: 
You are picking up a highly complex, multi-day Reinforcement Learning project for the Kaggle competition **Kaggriculture**. The user has specifically transitioned to this laptop to leverage its **RTX 3050 (6GB) GPU** and Intel i5 H-Series CPU for advanced CNN training. 

Read this document meticulously. Do not deviate from this established architecture.

---

## 🌾 1. The Competition & Mechanics
* **Grid**: A 10x10 farm grid where 2 agents (players) compete.
* **Horizon**: 30 in-game days (2000 steps total).
* **Goal**: Maximize Cash by the end of the 30 days.
* **Mechanics**: You plant crops (wheat, carrot, tomato, etc.) and raise animals (cows, sheep, geese). Crops take time to grow. Prices dynamically fluctuate based on market supply/demand.
* **Shops**: Every 3 days (approx. 72 steps), a new shop unlocks offering better seeds.

## 🪤 2. The Core Challenge: "The Greedy Trap"
Standard RL completely fails at this game because of the 2000-step horizon. An RL agent trained on the full 30 days will quickly learn to buy fast-growing crops (wheat) and immediately dump them for small profits, refusing to invest in high-yield, slow-growing assets like Geese or Cows.
* **Our Solution**: **Time-Chunked Curriculum RL**. We train the agent on only 3 days at a time (corresponding to the shop unlock cadence). 
* **The Net Worth Fix**: To prevent the agent from panic-selling at the end of the 3-day window, our custom environment calculates "Unrealized Net Worth" (valuing planted crops and shed inventory) as the reward function instead of raw cash.

## ⚙️ 3. The Architecture (HRL + FastGame)
We do **not** train the RL agent to output raw physical moves (like `NORTH`, `SOUTH`). Pathfinding is too inefficient for RL right now.
Instead, we use a **Hierarchical RL (HRL)** approach:
1. **The Heuristic Agent (`hrl_heuristic_agent.py`)**: We acquired the exact logic from the 169th-place competitor. It flawlessly handles BFS pathfinding, moving the worker to plant and harvest.
2. **The RL Macro-Agent**: Our PPO agent acts as the "Brain". It observes the state and outputs a 17-dimensional vector:
   * 8 `BUY_TARGETS` (How many of each seed to hoard).
   * 8 `SELL_RATIOS` (What percentage of inventory to dump to the market).
   * 1 `HIRE_TARGET` (How many workers to hire).
3. **Fast Engine (`project_maestro/engine/fast_engine.py`)**: We use a highly optimized pure Python port of the Kaggle environment capable of running at 100+ FPS to accelerate RL training.

## 🏆 4. Current Progress
We have successfully completed **Phase 1**.
* We wrote `train_day3_curriculum.py`.
* We trained a purely scalar MLP model on Days 0-3 that perfectly optimizes the opening sequence.
* The finalized weights are stored in **`ppo_day3_opening.zip`**.

## 🚀 5. Your Mission: Phase 2 (CNN "Eyes" + Day 6 Curriculum)
Currently, our RL agent only sees a 50D numerical vector (bank balance, prices, shed inventory). It is completely blind to the physical 2D farm.

**Your Tasks:**
1. **CUDA Setup**: Ensure PyTorch is using the RTX 3050:
   `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121`
2. **Observation Space Upgrade**: Modify our observation space to be a `spaces.Dict`. It must include both the existing 50D scalar vector AND a `10x10xN` spatial grid representing the physical tiles (crop type, maturity, worker positions).
3. **Build the CNN Feature Extractor**: Write a custom SB3 `BaseFeaturesExtractor`. Use a 2-layer Convolutional Neural Network (CNN) to process the `10x10xN` grid using the RTX 3050's Tensor Cores, and concatenate it with the processed scalar vector.
4. **Train Day 6**: Write `train_day6_curriculum.py`. This script must:
   * Load `ppo_day3_opening.zip`.
   * Force the environment to use the Day 3 weights for steps 0-71 (auto-pilot the opening).
   * Hand over control to your newly initialized CNN-PPO agent from step 72 to 144 (Days 3-6) so it can learn how to exploit Shop 1 unlocks.
