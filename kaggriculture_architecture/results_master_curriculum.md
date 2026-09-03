# Master Curriculum PPO Results (Day 6 -> Day 30)

The master curriculum automation has successfully completed, transitioning through chunks of 3 days and scaling the PPO model all the way up to Day 30.

## Progression Summary

Here is the reward progression as the agent learned to survive and optimize further into the game:

- **Day 6 -> 9**: Mean Reward ~3.4k
- **Day 9 -> 12**: Mean Reward ~14.8k
- **Day 12 -> 15**: Mean Reward ~18.4k
- **Day 15 -> 18**: Mean Reward ~18.2k
- **Day 18 -> 21**: Mean Reward ~18.8k
- **Day 21 -> 24**: Mean Reward ~27.8k
- **Day 24 -> 27**: Mean Reward ~25.4k
- **Day 27 -> 30**: Mean Reward ~27.4k

## Key Observations
- The jump from **Day 9 to Day 12** represented a massive inflection point where the compound scaling (likely unlocked by additional market/town shops or late-game animals/plants) took effect, boosting mean rewards from 3.4k into the 14k+ range.
- The next major scaling jump occurred at **Day 21 to Day 24**, pushing the agent into the high 20k margins and peaking near **28.7k** mid-training.
- The model successfully learned to navigate the full season without degrading or catastrophic forgetting.

Weights have been saved for each checkpoint (`ppo_resnet_day9.pth` through `ppo_resnet_day30.pth`).
