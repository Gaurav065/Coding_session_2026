# Modular Apex: Grandmaster Kaggriculture Engine

An autonomous, multi-quadrant farming intelligence engine for Kaggle's Kaggriculture competition.

Modular Apex orchestrates livestock husbandry, high-margin continuous fruit cultivation, dynamic shop fulfillment, and predatory market crashing across a 10x10 farm grid over 720 turns.

---

## Architecture Overview

The agent is organized into a modular architecture:

```
kaggriculture_architecture/
├── modular_apex/
│   ├── config.py           # Engine tuning, shop signatures, and market thresholds
│   ├── payload.py          # 14 optimized strategic route tapes (0 geese, 0 eggs)
│   ├── router.py           # Town shop signature matching & dynamic scenario routing
│   ├── chassis.py          # Real-time state machine, pathfinding, and market dumping
│   ├── guards.py           # Production guard decorators
│   ├── _guards_source.py   # Invariant defenders (anti-stall, anti-drift, cash floor)
│   ├── packager.py         # Sandbox compilation & tarball validator
│   └── main.py             # Internal modular entrypoint
├── submission.tar.gz       # Canonical submission package ready for Kaggle
├── main.py                 # Clean root entrypoint exposing agent(obs)
├── deploy.py               # Direct deployment utility supporting multi-account ports
├── switch_account.sh       # Rapid credential switcher (gaurav065 / gaurav06520)
├── kaggle_deployment_ports.json  # Multi-account API ports configuration
├── verify_sandbox.py       # Full sterile sandbox evaluator
└── NEW_SYSTEM_CONTEXT.md   # Architectural invariants and route maps
```

---

## Key Strategic Pillars

### 1. Zero Geese / Zero Eggs Invariant
All 14 route tapes are purged of low-yield geese and fragile coops. Early capital is allocated into cows and sheep, unlocking high-margin milk and wool production.

### 2. High-Margin Crop Focus & SE Expansion
- **Melons & Strawberries**: 15 contiguous strawberry tiles in the SW quadrant and structured melon strips generate continuous harvests.
- **Dynamic Tomato & Pizza Expansion (Route 13)**: If the town spawns 2 or more Pizza Shops, the agent unlocks the Southeast (SE) quadrant at Step 312 for $4,000, cultivating 100 tiles with tomatoes and grains to capture shop bonuses.

### 3. Starvation Market Crash Defense
The engine monitors rival inventories in real-time. When a rival accumulates harvestable goods or attempts to sell into liquid markets, Apex executes an anticipatory mass inventory dump, crashing prices to the $1 floor and starving the opponent's bank balance down to <$5k.

### 4. Zero Trapped Livestock Guarantee
Animal pastures are routed along a central corridor (`(1,4)..(7,4)`). Farm hands and farmers never enclose an animal tile, ensuring 100% feed and care delivery across every turn.

---

## Local Verification & Testing

To run the sterile multi-agent sandbox verification:

```bash
python verify_sandbox.py
```

This simulates complete 720-step matches against Starter, Random, and Pass baselines, asserting zero exceptions and high score margins (typically >$100k-$160k+).

To re-package the submission tarball:

```bash
python modular_apex/packager.py
```

---

## Deployment to Kaggle

Deploy directly to the primary Grandmaster account (`gaurav065`):

```bash
python deploy.py --account gaurav065 --message "Apex Grandmaster v2.0"
```

Or switch native CLI credentials:

```bash
source switch_account.sh gaurav065
kaggle competitions submit kaggriculture -f submission.tar.gz -m "Apex Grandmaster v2.0"
```
