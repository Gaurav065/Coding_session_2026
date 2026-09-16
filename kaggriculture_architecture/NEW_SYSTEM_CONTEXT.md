# MASTER CONTEXT & REPO NAVIGATION GUIDE
**Project**: Kaggle Kaggriculture Simulation Competition (Target: 3000+ Elo & Top 10)  
**Last Updated**: September 16, 2026  
**Active Git Remote**: `https://github.com/Gaurav065/Coding_session_2026.git` (Branch: `main`)

---

## 1. Executive Summary & Live Production Status

Our goal is to break the 2000 Elo plateau and surge to 3000+ Elo on Kaggle's simulation ladder.

### Current Live Submissions:
1. **Account `gaurav065`**:
   - **Active Submission**: `56274948` (Apex Grandmaster 3000+ Rectified)
   - **Public Ladder Match 1 (Ep `109616048`)**: **BLOWOUT WIN** — Us: **$152,051** vs Opponent: **$17,192** (Margin: **+$134,859**).
   - **Quota Status**: **4/5 daily submissions safely intact**. Do not waste them!
2. **Account `gaurav06520`**:
   - **Active Submission**: `56254428`
   - **Matches**: 152+ played, current Elo **1,945.3**.

---

## 2. Repository Navigation (What to Pick Up First)

If you are a new agent or developer entering this repository, **start here**:

```
c:\Coding\
├── NEW_SYSTEM_CONTEXT.md               <-- THIS MASTER GUIDE
├── m3_compute_runner/                  <-- Mac M3 Distributed Compute Package
│   ├── README_MAC.md                   # Step-by-step terminal instructions for macOS
│   ├── run_m3_tournament.py            # Parallel tournament engine across all M3 cores
│   ├── optimize_counter_tapes.py       # Genetic evolutionary tape optimizer (200k+ God paths)
│   ├── tournament_results.json         # Latest match telemetry
│   └── requirements.txt                # Dependencies (kaggle-environments, numpy, tqdm)
│
└── kaggriculture_architecture/         <-- Core Production Codebase
    ├── modular_apex/                   <-- THE DEFINITIVE MODULAR ENGINE
    │   ├── config.py                   # Constants, seed prices, engine parameters
    │   ├── payload.py                  # Compressed 13 action tapes & lossless reconstructor (123 KB)
    │   ├── router.py                   # Production Scenario Router (Dairy vs Wool vs Terminal)
    │   ├── chassis.py                  # Deterministic replay chassis + reactive micro-adjustments
    │   ├── _guards_source.py           # Defensive wrapper source code
    │   ├── guards.py                   # Bytecode compiler & isolated-scope wrapper executor
    │   ├── main.py                     # Kaggle-compliant callable agent entry point
    │   └── packager.py                 # Automated packager & sandbox validator
    │
    ├── submission.tar.gz               # Verified 143 KB deployable Kaggle submission tarball
    ├── actions.json                    # Full uncompressed 13-route action tapes (1.75 MB reference)
    ├── optimal_64_shop_plans.json      # Complete 8x8 shop pair unlock mapping
    ├── test_grandmaster_engine.py      # Grandmaster engine test suite
    ├── eval_agent.py                   # Evaluation utility
    ├── evaluate_mode.py                # Match mode comparator
    ├── LICENSE.txt                     # Apache-2.0 License
    └── README.md                       # High-level repo summary
```

---

## 3. Core Strategy, Routes, and Empirical Breakthroughs

### A. The 13 Pre-Computed Route Tapes
The core policy replays highly optimized 719-step action tapes, dynamically selected by the router:

| Route ID | Strategic Role | Key Livestock & Crops | Benchmark Score (vs Pass) |
| :--- | :--- | :--- | :--- |
| **Route 0** | **The Dairy Champion** | 8 Cows, 6 Sheep, 3 Geese, 239 crop operations (12 Melons, 163 Wheat, 33 Strawberries, 31 Carrots) | **$169,034 – $191,954** |
| **Routes 3–11** | **Wool Specialists** | 6 Cows, 11 Sheep (+5 Sheep, -2 Cows, -3 Geese) | **$184,035 – $184,501** |
| **Route 12** | **Ultra-Wool Specialist** | 4 Cows, 14 Sheep (+8 Sheep, -4 Cows) | Double Yarn Store specialist |
| **Route 2** | **Terminal Liquidation** | Winds down production at Step 648 (Day 27) and liquidates all inventory | Final step liquidation |

### B. The Crucial Router Discovery
- **Empirical Rule**: When town shops unlock at Step 144 (Day 6), if `YARN_STORE` is in the first two shops (`shops[:2]`), the agent switches to the specialized Wool routes (Routes 3..12) and achieves **$184,501+**.
- **Crucial Negative Finding**: If `YARN_STORE` is **not** in the first two shops, forcing specialized wool routes loses **-$18,000 to -$45,000**, because early wool orders cannot be sold and congest the shed.
- **Route 0 Dominance**: In all non-yarn scenarios (Bakery, Ice Cream, Smoothie, Pizza), Route 0 is a dominant Dairy powerhouse, reliably reaching **$179k – $192k**!
- The [`router.py`](file:///c:/Coding/kaggriculture_architecture/modular_apex/router.py) reflects this empirical truth.

### C. The Verified Defensive Guard Stack
All wrappers are consolidated inside [`guards.py`](file:///c:/Coding/kaggriculture_architecture/modular_apex/guards.py):
1. **Clean Opening (`_R42_OPENING`)**: Step 0 buys strictly `[['BUY_PRODUCT', 'WHEAT', 13]]`. Eliminates bid-ask spread churn and cash leakage in Seat 1.
2. **Day-0 Cash Floor Guard (`$10.0 Floor`)**: Evaluates `money - cost < 10.0` during Day 0 (Steps 0–23). Clamps seed orders to guarantee the $4.00 morning worker wages while allowing full 12 melon seeds.
3. **Day-End Storage Guard (`SHED_CAPACITY = 100`)**: Keeps warehouse inventory <= 99 to prevent catastrophic shed capacity loss.
4. **Smart Labor Dispatcher (`_R53_LABOR`)**: Coordinates Days 26–28 worker movement for maximum crop harvesting.
5. **Zero Trapped Animals Guarantee**: Ensures `shed['COW'] == 0` and `shed['SHEEP'] == 0` at Step 719 across all routes.

---

## 4. How to Test, Run, and Package (Workstation / Windows)

### 1. Run Local Verification Simulation
```bash
python -c "
import kaggle_environments
from modular_apex.main import agent

env = kaggle_environments.make('kaggriculture', configuration={'episodeSteps': 720, 'seed': 2026})
env.run([agent, 'pass'])
print('Seed 2026 Reward:', env.steps[-1][0]['reward'])
print('Shed:', env.steps[-1][0]['observation']['private']['shed'])
"
```
*(Expected Output: Reward = $184,271.0 | Trapped cows = 0 | Trapped sheep = 0)*

### 2. Build and Validate Kaggle Submission Package
Run the automated packager:
```bash
python modular_apex/packager.py
```
This will:
- Bundle `config.py`, `payload.py`, `router.py`, `chassis.py`, `_guards_source.py`, `guards.py`, and `main.py` into `submission.tar.gz`.
- Compute the SHA256 checksum.
- Extract into a sandboxed temp directory and execute dummy step 0 to prove Kaggle loader compliance.

---

## 5. Apple Silicon Mac M3 Distributed Compute Workflow

We offload high-throughput simulation, tournament matches, and genetic tape optimization to the user's Apple Silicon Mac M3 via Git:

### Setup on Mac:
```bash
# 1. Pull latest code from GitHub
git pull origin main
cd m3_compute_runner

# 2. Setup Virtual Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### High-Throughput Workloads on Mac:
1. **Parallel Multi-Core Tournament** (utilizes all 8 M3 cores):
   ```bash
   python3 run_m3_tournament.py --matches 50 --cores 8
   ```
   Simulates 50 games in parallel and generates `tournament_results.json`.

2. **Genetic Evolutionary Tape Optimizer (Seeking 200k+ God Paths)**:
   ```bash
   python3 optimize_counter_tapes.py --generations 20 --population 16 --cores 8
   ```
   Mutates farmer actions, planting schedules, and market timing across generations. Winning tapes are saved to `discovered_tapes.json`.

### Syncing Back to Windows Production:
On the Mac:
```bash
git add discovered_tapes.json tournament_results.json
git commit -m "M3: Add discovered 200k counter-tape"
git push origin main
```
On Windows:
```bash
git pull origin main
# Ingest discovered tape into modular_apex/payload.py
```

---

## 6. Deployment Rules & Constraints

> [!CAUTION]
> **STRICT SUBMISSION RULES**:
> 1. **Do NOT waste submission slots on `gaurav065`**: We have 4 slots remaining today. Never submit without 100% passing local sandbox validation (`packager.py`).
> 2. **Kaggle Loader Integrity**: Always verify `main.py` defines `agent` as the last callable in globals.
> 3. **Zero Shed Animals**: Reject any tape or modification that leaves cows or sheep trapped in the shed at Step 719.
