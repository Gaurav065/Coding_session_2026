# 🚀 Phase 2 Completion: Final Evaluation & Submission

**To the GPU Worker Node:**
Congratulations on successfully running the Master Curriculum! You have generated `ppo_resnet_day30.pth` which boasts a highly stable 27k+ Net Worth baseline. 

Before we move to Phase 3 (LSTM), we must visually audit this agent and lock in our Kaggle Leaderboard baseline.

## Step 1: The Local Visual Audit
We need to visually confirm that the PyTorch Macro Agent is successfully commanding the BFS Micro Agent without getting stuck, and crucially, that it liquidates its farm on Day 30.

Run the local evaluator:
```bash
python evaluate_local.py
```

**What to check:**
1. Open `local_evaluation.html` in your web browser. Watch the agent's behavior. Does it successfully plant dense crops? Does it buy animals?
2. Open `match_economy_log.csv`. Scroll to the very last row (Step 718 / 719). 
   * Is `Items_in_Shed` equal to `0`? If yes, the agent perfectly liquidated. If not, it left money on the table.

## Step 2: Package the Kaggle Baseline
Once you have visually confirmed the agent is behaving rationally, we need to secure our leaderboard rank.

Run the packager script:
```bash
python package_submission.py
```

This will bundle:
- `submission_agent.py` (Renamed to `main.py` inside the tar)
- `hrl_heuristic_agent.py`
- `ppo_resnet_day30.pth`

**Action Required:**
Take the resulting `kaggle_submission.tar.gz` and upload it to the Kaggle competition page! 

## Step 3: Phase 3 (The LSTM Upgrade)
Once you have submitted to Kaggle, report back to the Command Center. 
We will then run `python prepare_lstm_data.py` and `python train_custom_bc.py` to give the agent a 10-day Memory Bank to shatter the 74k Tape Score ceiling!
