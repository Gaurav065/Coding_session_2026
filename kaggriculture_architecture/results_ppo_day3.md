# PPO Day 3 Fine-Tuning Results

**Architecture**: `KaggricultureResNet`
**Base Model**: `custom_bc_master.pth` (Behavioral Cloning pre-training)
**Environment**: `FastGame` (Day 0-3 Curriculum)
**Algorithm**: Proximal Policy Optimization (PPO)

## Training Configuration
- **Total Timesteps**: 30,000
- **Batch Size**: 64
- **Epochs per Update**: 4
- **Optimizer**: Adam (lr=1e-4)
- **Gradient Clipping**: 0.5
- **Entropy Coefficient**: 0.01

## Results (Net Worth / 1000)
- **Initial Mean Reward (Update 1)**: 1.929
- **Midpoint Mean Reward (Update 50)**: 2.997
- **Final Mean Reward (Update 117)**: 3.405

## Conclusion
The PyTorch `retain_graph` leak was successfully patched, allowing the rollout gradients to decouple from the backward passes. 
The RL fine-tuning worked flawlessly! By initializing from the BC weights, the model quickly scaled from an average Day 3 net worth of ~1,900 coins to an optimized **3,400+ coins**.

The final Day 3 curriculum weights have been saved to `ppo_resnet_day3.pth` and are ready for the Day 6 curriculum.
