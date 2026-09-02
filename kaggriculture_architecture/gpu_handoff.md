# 🚀 Kaggriculture GPU Handoff Document

**To the Gemini Agent on the new laptop:** 
Hello! You are picking up a highly advanced Reinforcement Learning project for the Kaggle competition "Kaggriculture". 
The user has moved to this laptop to utilize the RTX 3050 (6GB) and Intel i5 H-series CPU. 

Read this document carefully, execute the CUDA setup, and then proceed to Phase 2 of our RL pipeline.

---

## 🛠️ Step 1: CUDA Environment Setup
Your first priority is to ensure PyTorch can access the RTX 3050.
1. Open a terminal and run `nvidia-smi` to verify the GPU is detected and check the maximum supported CUDA version.
2. Install the CUDA-enabled version of PyTorch. (Run this in the terminal):
   ```bash
   pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
3. Install the RL dependencies:
   ```bash
   pip install stable-baselines3 gymnasium kaggle-environments
   ```
4. Verify CUDA is active by running a quick python snippet:
   ```python
   import torch
   print(torch.cuda.is_available()) # MUST output True
   ```

---

## 🧠 Step 2: Where We Left Off (The Curriculum RL)
We have successfully implemented **Time-Chunked Curriculum RL**. 
Because the 30-day game horizon is too long, we slice the game into 3-day epochs (since shops unlock every 3 days). 
- We already successfully trained `ppo_day3_opening.zip` which perfectly optimizes Net Worth for Days 0-3.
- The previous agent relied purely on a 50-dimensional MLP (checking bank balances and shed inventory).

## 🚀 Step 3: Phase 2 (Your Mission)
Now that we have GPU horsepower, we need to give the agent "Eyes" using a Convolutional Neural Network (CNN).

**Your Task:**
1. **Modify `hrl_wrapper.py` (or our `FastKaggricultureMacroEnv`):** Expand the observation space to include a 2D spatial grid (e.g., `10x10xN`) that encodes the physical farm (where seeds are planted, crop maturity, worker positions).
2. **Implement CNN Feature Extractor:** Use Stable Baselines 3's `features_extractor_class` to build a CNN that processes the `10x10xN` grid using the RTX 3050 Tensor Cores.
3. **Train Day 6 Curriculum:** Write `train_day6_curriculum.py`. This script should load our frozen Day 3 weights (`ppo_day3_opening.zip`), let it play the first 3 days on autopilot, and then hand control over to the new CNN-powered agent to master Days 3-6 (Steps 72 to 144).

*Note to Gemini: The user has transferred the core python scripts via `Kaggriculture_RL_Core.zip`. Unzip them into your working directory before starting!*
