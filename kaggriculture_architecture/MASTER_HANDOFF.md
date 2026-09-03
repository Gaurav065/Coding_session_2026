# 🚜 Kaggriculture Master Handoff Document (Phase 3: BC LSTM + Distributed Training)

**ATTENTION GEMINI AGENT**: 
You are picking up a highly complex, multi-day Reinforcement Learning and Behavioral Cloning project for the Kaggle competition **Kaggriculture**. 
**CRITICAL CONTEXT**: This machine (with the RTX 3050 6GB GPU) will now act as a **dedicated GPU training node**. It will receive instructions/jobs from a master orchestration machine.

Read this document meticulously. Do not deviate from this established architecture.

---

## 🌾 1. The Competition & Mechanics
* **Grid**: A 10x10 farm grid where 2 agents (players) compete.
* **Horizon**: 30 in-game days (2000 steps total).
* **Goal**: Maximize Cash by the end of the 30 days.
* **Mechanics**: You plant crops (wheat, carrot, tomato, etc.) and raise animals (cows, sheep, geese). Crops take time to grow. Prices dynamically fluctuate based on market supply/demand.
* **Shops**: Every 3 days (approx. 72 steps), a new shop unlocks offering better seeds.

## 🛠 2. The Architecture (HRL + FastGame)
We use a **Hierarchical RL (HRL)** approach:
1. **The Heuristic Agent (`hrl_heuristic_agent.py`)**: Flawlessly handles BFS pathfinding, moving the worker to plant and harvest.
2. **The Macro-Agent (RL / BC)**: The "Brain". Observes the state and outputs a 17-dimensional vector:
   * 8 `BUY_TARGETS` (How many of each seed to hoard).
   * 8 `SELL_RATIOS` (What percentage of inventory to dump to the market).
   * 1 `HIRE_TARGET` (How many workers to hire).
3. **Fast Engine (`project_maestro/engine/fast_engine.py`)**: Pure Python port of the Kaggle environment for 100+ FPS fast-forwarding.

## ✅ 3. Completed Work (Phase 1 & Phase 2)
* **Phase 1 (Opening Theory)**: Trained a purely scalar MLP on Days 0-3 that perfectly optimizes the opening sequence (`ppo_day3_opening.zip`).
* **Phase 2 (Spatial Vision & Handover)**: 
  - Upgraded PyTorch to `cu124` for full RTX 3050 acceleration on Python 3.13.
  - Implemented `train_day6_curriculum.py` utilizing an **IMPALA-style Residual CNN** (Espeholt et al.) merged with a LayerNorm MLP to process the 10x10 grid spatially.
  - Successfully handed over control from Day 3 to Day 6 to avoid the "Greedy Trap", resulting in `ppo_day6_curriculum.zip`.
* **Data Engineering**: Created `download_from_urls.py` and successfully extracted 600 JSON replays from the exact Top 20 Grandmasters by parsing raw Kaggle Submission IDs. The dataset currently resides in `D:\replays`.

## 🚀 4. Your Mission: Phase 3 (Distributed Behavioral Cloning)
Pure RL is currently underperforming Grandmaster static tapes ($6,800 vs $74,000) due to "Jitter" and "Temporal Blindness" (see `BC_IMPROVEMENT_NOTES.md`). 
Our new strategy is to Behavioral Clone (BC) the 600 Top Replays using LSTMs, and then use that as a seed for Self-Play PPO.

**Since this machine is now a GPU Worker Node**, your tasks are:
1. **Wait for Instructions**: Acknowledge commands from the master orchestration machine.
2. **Dataset Parsing**: Convert the 600 JSON replays in `D:\replays` into a massive sequence-based PyTorch dataset (Sequence Length = 10, to feed the LSTM).
3. **LSTM Architecture**: Implement an LSTM network that replaces the old MLP. The hidden state will completely eliminate the "Jitter" problem by giving the agent memory.
4. **Training Loop**: Execute the BC training loop on the RTX 3050, streaming batches efficiently from `D:\replays` so we don't blow out the RAM.

