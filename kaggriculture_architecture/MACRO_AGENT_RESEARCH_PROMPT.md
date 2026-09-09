# Deep Research Prompt: SOTA Hierarchical Macro-Agent for Real-Time Strategy Economy

**Persona:** You are an elite Deep Learning / Reinforcement Learning Architect specializing in Operations Research, hierarchical RL (HRL), and Real-Time Strategy (RTS) AI (e.g., AlphaStar, OpenAI Five).

## The Environment Context
I am building a Hierarchical Reinforcement Learning agent for a grid-based farming/economy game. The agent is split into two parts:
1. **The Micro-Agent:** Handles 10x10 spatial pathfinding and immediate tasks (moving, planting, harvesting).
2. **The Macro-Agent (The Focus of this Research):** Acts as the "Economy Manager". It does not see the grid. It only sees the financial state of the game, and its job is to manage the inventory, buy seeds, sell crops, and optimize massive delayed rewards over a 720-step episode.

## The Macro-Agent I/O Space
*   **Input Space:** A 100-dimensional continuous/discrete scalar vector containing:
    *   Normalized current game step (0 to 720).
    *   Current Money.
    *   Inventory arrays (amount of seeds, amount of harvested crops).
    *   Market arrays (current price of each crop, current market inventory).
    *   One-hot encodings of randomly spawned town shops.
*   **Output Space:** A 20-dimensional continuous action vector containing:
    *   Indices 0-4: Amounts of 5 different seeds to buy (Bounded continuous, e.g., 0 to N).
    *   Indices 5-7: Amounts of 3 different animals to buy.
    *   Indices 8-16: Sell Ratios for 9 different items (Bounded 0.0 to 1.0).
    *   Indices 17-19: Worker hires and land purchases.

## Your Task
Please research the current State-of-the-Art (SOTA) in Deep RL for RTS macro-management and provide a detailed architectural blueprint answering the following 4 questions. Cite specific papers, architectures, and loss functions.

### 1. Memory and Temporal Architecture
Because the reward for buying a seed is delayed by ~150 steps (until the crop is grown and sold), a reactive MLP might fail. Should the Macro-Agent be a standard Multi-Layer Perceptron (MLP), a Recurrent Neural Network (GRU/LSTM), or a Causal Transformer (Decision Transformer)? How did AlphaStar or OpenAI Five handle macro-economic memory over long horizons?

### 2. Action Space Parameterization
The 20-dimensional output space is highly heterogeneous. Some outputs are ratios `[0, 1]`, while others are integers/counts `[0, N]`. If we train this via PPO or Soft Actor-Critic (SAC), how should the Actor network parameterize this output distribution? Should we use independent Gaussian heads, Beta distributions (for the ratios), or an Auto-Regressive action head?

### 3. Credit Assignment for Delayed Economic Rewards
What is the SOTA method for temporal credit assignment in economics? Should we use standard Generalized Advantage Estimation (GAE) with a massive discount factor ($\gamma = 0.999$), Return-to-Go (RTG) conditioning, or Reward Shaping (e.g., assigning a heuristic intrinsic reward the moment a seed is planted)?

### 4. Proposed PyTorch Architecture
Based on your research, write a highly optimized, SOTA PyTorch class `MacroEconomyAgent(nn.Module)`. Include the specific layers (e.g., LayerNorm, Gated Residual Networks) that perform best on dense tabular feature inputs.
