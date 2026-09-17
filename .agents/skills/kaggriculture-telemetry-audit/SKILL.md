---
name: kaggriculture-telemetry-audit
description: >-
  Audits Kaggriculture agents and simulation episodes for crop lifecycle failures,
  unwatered/withered plants, ghost land acquisitions, phantom/no-op market orders,
  and livestock welfare. Use this skill whenever testing, verifying, or evaluating
  a Kaggriculture agent locally before Kaggle submission to catch hidden execution bugs.
---

# Kaggriculture Telemetry & Lifecycle Auditor

Standard evaluation metrics (e.g. final bank balance or win rate) often mask critical execution defects because the Kaggriculture game engine silently drops invalid actions (such as selling produce not in the shed or buying seeds that wither).

This skill enforces a **zero-silent-failure standard** across all Kaggriculture subsystems:
1. **Crop Vitality**: Verifies that every planted seed survives to harvest. Red-flags any crop that withers into a weed due to missed daily watering.
2. **Land Utilization**: Verifies that every unlocked quadrant (NW, NE, SW, SE) is actually cultivated by workers and not bought as "ghost land".
3. **Market Integrity**: Catches phantom sell orders (orders submitted when shed inventory is 0) and unfulfilled buy orders.
4. **Livestock Welfare**: Ensures all cows, sheep, and geese are fed daily and never escape.
5. **Worker Efficiency**: Tracks idle hand percentages and unexecuted actions.

---

## Quick Start

Run the automated telemetry auditor against any agent script:

```bash
# Run against Starter benchmark with seed 42
python kaggriculture_architecture/audit.py kaggriculture_architecture/submission.py --opponent starter --seed 42

# Strict mode: exits with non-zero exit code if ANY critical flaw is found
python kaggriculture_architecture/audit.py kaggriculture_architecture/submission.py --opponent starter --strict
```

Or using the skill script directly:

```bash
python .agents/skills/kaggriculture-telemetry-audit/scripts/run_audit.py kaggriculture_architecture/submission.py
```

---

## Diagnostic Criteria & Red Flags

An agent run is flagged as **CRITICAL DEFECT** if any of the following occur:

| Red Flag | Severity | Root Cause | Action Required |
| :--- | :--- | :--- | :--- |
| **Crop Withered into Weed** | ❌ CRITICAL | Ongoing crops (Tomato, Strawberry) missed watering 2 consecutive days. | Add a daily dynamic watering sweep in `chassis.py` before end-of-day. |
| **Ghost Land (0 tiles cultivated)** | ❌ CRITICAL | `BUY_LAND` executed for NE/SW/SE, but no worker was routed there. | Route hired hands to cultivate newly unlocked quadrants. |
| **Phantom Sell Orders (>50 units)** | ❌ CRITICAL | Market tape fires `SELL` orders when shed inventory is 0. | Filter market orders against `obs["private"]["shed"]` before submission. |
| **Livestock Escaped** | ❌ CRITICAL | Animals missed feeding for 2 consecutive days. | Verify daily wheat feeding task in worker queue. |
| **Dormant Seeds (>5 bought, 0 planted)** | ⚠️ WARNING | Agent spends money buying seeds that are never planted. | Remove dormant seed orders or dispatch planters. |

---

## Procedure for Agent Iteration & Fixing Defects

When a critical defect is flagged:
1. **Identify the exact coordinates and turn**: The audit report logs the first occurrence (e.g. `Day 11, Tile (4,0)`).
2. **Patch the dynamic reactive layer (`chassis.py`)**:
   - For **Tomato / Strawberry withering**: Inject a mandatory daily watering guard that checks all ongoing plant tiles before hour 23 and overrides any idle/passing worker to water them.
   - For **Phantom sells**: Intercept market orders in `chassis.py` and clamp `SELL` amounts to `shed.get(item, 0)`.
   - For **Ghost land**: Allocate hands to new quadrants once `BUY_LAND` completes.
3. **Re-run the audit**: Verify that `DIAGNOSTIC VERDICT` displays `✅ STATUS: CLEAN & HEALTHY`.
4. **Compile and Submit**: Run `packager.py` to regenerate `submission.py`.
