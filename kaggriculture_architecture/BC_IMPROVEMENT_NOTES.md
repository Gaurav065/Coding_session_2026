# Behavioral Cloning (BC) Improvement Notes
**Date**: September 2, 2026
**Status**: Archived for future fine-tuning.

## The Vision
While static "Tape Stitching" currently dominates the Kaggriculture leaderboard, Behavioral Cloning (Deep Learning) has a significantly higher skill ceiling. A static tape breaks the moment an opponent does something unexpected (e.g., stealing a prime grid spot or manipulating market prices). A well-trained BC agent is dynamic—it learns *why* the Grandmaster made a move, allowing it to adapt to novel market conditions and counter-attack static tapes.

## Root Causes of Current Underperformance ($6,800 vs $74,000)

1. **The Jitter Problem (Thrashing)**
   - *Issue*: Our `MacroAgentNet` processes each day independently. On Day 5, it might predict `23 Melons`. On Day 6, minor price fluctuations cause the network to predict `21 Melons`. On Day 7, it jumps to `25 Melons`.
   - *Impact*: Our heuristic micro-agent blindly follows these targets, causing it to buy seeds, sell them at a loss the next day, and buy them back again. This bleeds the farm's cash reserves through transaction fees.

2. **Temporal Blindness (State Representation)**
   - *Issue*: The current 50-dimensional observation vector tracks *current* cash and prices, but ignores the spatial and temporal state of the farm (e.g., "I have 20 Melons planted that will harvest in 2 days yielding $10,000").
   - *Impact*: The network cannot predict future cash flow, leading to overly conservative or mistimed targets.

3. **Target vs. Action Mismatch**
   - *Issue*: Predicting the "Target Portfolio" (what the human *holds*) is an indirect way of cloning. If the human slowly accumulates 30 seeds over 5 days to manage cash flow, the network just predicts "Target: 30", causing our micro-agent to buy all 30 immediately, threatening payroll reserves.

## Action Plan for Upgrading BC (To Overpower Tapes)

When we return to this branch, we must implement the following:

1. **Output Smoothing (Low-Pass Filter)**
   - Apply an Exponential Moving Average (EMA) to the network's output targets. 
   - *Fix*: `smoothed_target = 0.8 * old_target + 0.2 * new_target`. This completely eliminates jitter and stops the micro-agent from thrashing.

2. **Recurrent Neural Networks (LSTM / GRU)**
   - Replace the MLP with an LSTM. By passing a hidden state between days, the network gains "memory" of its overarching strategy (e.g., "I decided to go all-in on Melons yesterday, I shouldn't pivot to Wheat today just because prices shifted").

3. **Direct Action Cloning (Micro-Level)**
   - Instead of predicting abstract "Targets", train a Transformer model to predict the exact discrete commands (`BUY_SEED MELON 5`) based on a sequence of the last 10 observations. 

4. **Self-Play Reinforcement Learning (Fine-Tuning)**
   - Once the LSTM BC agent can smoothly achieve $60,000+, we inject it back into PPO. Because it already knows how to farm, the RL reward signal will no longer be sparse, allowing it to discover superhuman strategies that beat the Grandmaster tapes it was cloned from.
