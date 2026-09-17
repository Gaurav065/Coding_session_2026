# Apple Silicon Mac M3 Distributed Compute Runner

This package enables high-throughput, multi-core simulation, tournament evaluation, genetic tape optimization, and multi-account Kaggle deployment directly from your Apple Silicon Mac (M3 chip).

---

## 🚀 Quick Setup (Terminal on your Mac)

### 1. Pull Latest Code from GitHub
Open Terminal on your Mac and navigate to your cloned repository:
```bash
git pull origin main
cd m3_compute_runner
```

*(If you haven't cloned it yet on your Mac:)*
```bash
git clone https://github.com/Gaurav065/Coding_session_2026.git
cd Coding_session_2026/m3_compute_runner
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🔑 Multi-Account Kaggle Deployment Ports

Both Kaggle accounts are pre-configured as deployment ports:

| Account | Role / Purpose | Token | Active Sub ID | Current Elo |
| :--- | :--- | :--- | :--- | :--- |
| **`gaurav065`** | **Primary Grandmaster Ladder** | `KGAT_9b806157756d5ff934d83a0797ba658b` | `56274948` | **1,891.8** |
| **`gaurav06520`** | **Secondary Exploration Port** | `KGAT_ec5e135bd5730eb67df2a539d8fcac64` | `56254428` | **1,812.0** |

### How to Switch Accounts on Mac CLI:
```bash
# Switch active session to gaurav065:
source switch_account.sh gaurav065

# Switch active session to gaurav06520:
source switch_account.sh gaurav06520
```

### Direct Automated Deployment from Mac:
You can deploy any package directly to either account using the multi-account deployer:
```bash
# Deploy to primary account (gaurav065):
python3 deploy.py --account gaurav065 --file ../kaggriculture_architecture/submission.tar.gz --message "M3 Optimized Apex Grandmaster"

# Deploy to secondary account (gaurav06520):
python3 deploy.py --account gaurav06520 --file ../kaggriculture_architecture/submission.tar.gz --message "M3 Counter-Tape Exploration"
```

---

## ⚡ Workloads to Run

### Option A: Run Parallel High-Throughput Tournament
Simulate dozens of full 720-step matches in parallel across all M3 Performance and Efficiency cores:
```bash
# Run 50 matches across all M3 cores (vs pass baseline)
python3 run_m3_tournament.py --matches 50 --cores 8

# Run 30 matches of intensive self-play (modular_apex vs modular_apex)
python3 run_m3_tournament.py --matches 30 --mode self_play
```
- Results are printed live with execution time and steps/sec throughput.
- Full statistics and per-seed results are saved to `tournament_results.json`.

---

### Option B: Genetic Tape Optimizer (Discovering $200k+ God Paths)
Run evolutionary beam search to mutate farmer movements, crop timings, and livestock sales to discover higher scoring action sequences:
```bash
# Run 15 evolutionary generations with a population of 16 mutants per generation
python3 optimize_counter_tapes.py --generations 15 --population 16 --cores 8
```
- Every mutant is verified to guarantee **0 trapped animals in the shed**.
- Any tape that beats the current champion is immediately locked in.
- The winning tape is saved directly to `discovered_tapes.json`.

---

## 🔄 Syncing Results Back to Production

Once a run is complete or a new champion tape is found:
```bash
git add discovered_tapes.json tournament_results.json
git commit -m "M3: Discovered optimized 200k counter-tape"
git push origin main
```

On the Windows development workstation, we will run `git pull` and immediately ingest the new tape into `modular_apex/payload.py` for submission!
