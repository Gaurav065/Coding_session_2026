# Kaggriculture GPU Phase 2 Handoff

Hello! You are picking up an advanced Reinforcement Learning project for the Kaggle competition "Kaggriculture". We have just migrated to this laptop to utilize its RTX 3050 (6GB) GPU and Intel i5 H-Series CPU for training.

## 🎯 Our Goal
We are using **Time-Chunked Curriculum RL** using Stable Baselines 3 (PPO). The 30-day game is too complex to learn at once (the Greedy Trap), so we slice it into 3-day epochs.
* We have already perfectly optimized Days 0-3 (Net Worth maximization) using a pure MLP that only sees scalar values (bank balance, inventory). The weights are saved in `ppo_day3_opening.zip`.
* **Your immediate mission** is to build the **Phase 2 CNN Feature Extractor** so the agent can literally "see" the 2D spatial grid (crops, maturity, workers), and then train the **Day 3-6 Curriculum model**.

## 📂 Key Files in Current Directory
* `hrl_heuristic_agent.py`: A heuristic HRL layer (originally from a 169th-place competitor). It handles low-level pathfinding (BFS). Our RL agent interacts with it by outputting macro-commands: `BUY_TARGETS`, `SELL_RATIOS`, and `HIRE_TARGET`.
* `fast_engine.py` (inside the `project_maestro` folder): Our ultra-fast pure Python port of the Kaggle environment. Essential for hitting 100+ FPS during training.
* `train_day3_curriculum.py`: The script used to train the Day 0-3 MLP model. It contains our custom `Day3CurriculumEnv` and the crucial `_calculate_net_worth()` function that prevents the agent from panic-selling.
* `ppo_day3_opening.zip`: The finalized weights for Days 0-3.

## 🛠️ Step 1: CUDA Environment Validation
Before writing any code, ensure PyTorch can access the RTX 3050. Run these terminal commands:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install stable-baselines3 gymnasium kaggle-environments
```
Verify CUDA is active by running: `python -c "import torch; print(torch.cuda.is_available())"`. It MUST output `True`.

## 🚀 Step 2: Build the CNN "Eyes"
Modify our Observation Space to include the 2D grid.
1. Inspect how `FastGame.get_observation()` outputs the grid (e.g. `10x10` tiles containing `crop`, `planted_step`).
2. Update the environment's `observation_space` to be a `spaces.Dict` containing both the `scalar` vector (50D) and the `spatial` grid (e.g., `10x10x4` channels for crop type, maturity, worker pos, etc.).
3. Write a custom SB3 `BaseFeaturesExtractor` that uses a simple 2-layer CNN to process the `spatial` grid, and an MLP to process the `scalar` vector, concatenating them at the end.

## 🏆 Step 3: Train Day 3-6 Curriculum
Write a new script `train_day6_curriculum.py`:
1. It must load `ppo_day3_opening.zip` (the MLP model).
2. For steps 0 to 71 (Days 0-3), the environment must execute actions dictated by the Day 0-3 MLP model.
3. At step 72, control hands over to the *new* CNN-powered PPO model.
4. Train the new model to maximize Net Worth at the end of Day 6 (Step 144), taking advantage of the newly unlocked Shop 1!
