# PPO Day 6 Fine-Tuning Results

**Architecture**: `KaggricultureResNet`
**Base Model**: `ppo_resnet_day3.pth` (Day 3 PPO Curriculum)
**Environment**: `FastGame` (Day 3-6 Curriculum)
**Algorithm**: Proximal Policy Optimization (PPO)

## Training Configuration
- **Total Timesteps**: 30,000
- **Batch Size**: 64
- **Epochs per Update**: 4
- **Optimizer**: Adam (lr=1e-4)

## Results (Net Worth / 1000)
- **Initial Mean Reward (Update 1)**: 2.797
- **Midpoint Mean Reward (Update 50)**: 3.452
- **Final Mean Reward (Update 117)**: 3.335

## Conclusion
The model successfully fast-forwarded to Day 3 using the active weights, and smoothly continued training through Day 6. The mean reward scaled up quickly and stabilized solidly around **3,300 - 3,400+ coins**. 

The agent demonstrates high stability and asset retention as it crosses into the mid-game, maintaining the high-yield behaviors learned during the behavioral cloning phase. 

The final Day 6 curriculum weights have been saved to `ppo_resnet_day6.pth` and are ready to be used as the base model for the Day 9 curriculum.
