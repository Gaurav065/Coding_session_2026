# Complete Databricks execution and verification prompt

You are responsible for running and verifying the complete Teradata-to-Databricks
conversion exercise in Databricks.

## Objective

Run the single orchestrator notebook `RUN_ALL.py`. It must:

1. Run `SETUP.py`.
2. Create the required schemas, tables, volume, and input files.
3. Run `JOB_01.py` through `JOB_10.py` in dependency order.
4. Pass the required catalog, schema, file, and runtime parameters.
5. Validate final output row counts and key content checks.
6. Persist a verification report as a Delta table and JSON file.
7. Fail loudly if any notebook or verification check fails.

Do not request, print, log, store, or expose Databricks credentials. Use the
already-configured Databricks workspace authentication.

## Workspace files

Upload these files into one Databricks workspace folder:

```text
/Users/<your-user>/teradata-conversion/
├── SETUP.py
├── JOB_01.py
├── JOB_02.py
├── JOB_03.py
├── JOB_04.py
├── JOB_05.py
├── JOB_06.py
├── JOB_07.py
├── JOB_08.py
├── JOB_09.py
├── JOB_10.py
└── RUN_ALL.py
```

`SETUP.py` comes from the hands-on exercise archive. The remaining files come
from the `copilot converted scripts` folder. `README.md` and this prompt are
documentation and do not need to be run as notebooks.

## Run the orchestrator

Open and run only `RUN_ALL.py`. Set:

```text
NOTEBOOK_ROOT = /Users/<your-user>/teradata-conversion
CATALOG = <writable Unity Catalog catalog>
```

Use these exercise defaults:

```text
MIN_YM = 202501
MAX_YM = 202503
DATADATE =
YYYYMM = 202601
SEG_CD = RN
RANK_CD = A
LVL = 1
LOOKBACK_M = -12
MIN_SRVC_CNT = 3
```

`CATALOG` must allow creation of schemas, tables, and volumes. Do not
hardcode environment-specific catalog or schema names.

The orchestrator calls notebooks in this exact order:

```text
SETUP.py
JOB_01.py
JOB_02.py
JOB_03.py
JOB_04.py
JOB_05.py
JOB_06.py
JOB_07.py
JOB_08.py
JOB_09.py
JOB_10.py
```

## Setup outputs

`SETUP.py` creates these schemas under the selected catalog:

```text
usr_mst
usr_cust
usr_tmpbat
usr_ctl
usr_land
usr_core
usr_ref
usr_sched
usr_ctrl
```

It creates the landing volume:

```text
<catalog>.usr_land.landing
```

and these input files:

```text
/Volumes/<catalog>/usr_land/landing/profit_centre.dat
/Volumes/<catalog>/usr_land/landing/consgn_feed.txt
/Volumes/<catalog>/usr_land/landing/vehicle_reg.txt
```

## Expected results

Verify the following final output results:

| Job | Output table | Expected result |
|---|---|---:|
| JOB_01 | `<catalog>.usr_tmpbat.WT_LOGICALDEL` | 11 rows |
| JOB_02 | `<catalog>.usr_ctl.MT_CALENDAR` | 31 rows |
| JOB_03 | `<catalog>.usr_tmpbat.WD_CMPGN_MON_SUM` | 18 rows |
| JOB_04 | `<catalog>.usr_tmpbat.WT_DELKEY_EXP` | 8 rows |
| JOB_05 | `<catalog>.usr_tmpbat.WT_PROFITCTR` | 12 rows plus 2 rejects |
| JOB_06 | `<catalog>.usr_land.CONSGN_RAW` | 9 rows plus 1 reject |
| JOB_07 | `<catalog>.usr_core.LANE_KEY` | 8 rows |
| JOB_08 | `<catalog>.usr_land.VEHICLE_REG_RAW` | 10 rows |
| JOB_09 | `<catalog>.usr_cust.FT_TXN_DETAIL` | 15 rows from 18 |
| JOB_10 | `<catalog>.usr_tmpbat.WD_RENEWAL_PROSPECT` | 3 rows |

Also run:

```sql
SELECT DATA_YMD, REL_YMD
FROM <catalog>.usr_ctl.MT_CALENDAR
WHERE DATA_YMD = DATE '2026-03-16';
```

Expected result:

```text
DATA_YMD    REL_YMD
2026-03-16  0
```

## Content-level checks

Perform these checks in addition to row counts:

- **JOB_01:** `WT_LOGICALDEL` contains exactly the 11 expected campaign/store
  pairs. Duplicate source rows must not create duplicate target rows.
- **JOB_02:** `REL_YMD` is `1`, `0`, `-1`, and `-2` for March 15 through March
  18, respectively. Reset before rerunning because this job is not idempotent.
- **JOB_03:** only months `202501` through `202503` appear; no
  `PLAN00000006` or `PLAN00000007` appears; valid duplicate `ST0003` channel
  rows remain.
- **JOB_04:** `WT_DELKEY_EXP` contains exactly the eight store/order pairs.
- **JOB_05:** twelve accepted and two rejected records exist. Preserve spaces
  inside fixed-width codes such as `PC002    B`, `PC003    C`, `PC004    D`,
  and `PC006    E`.
- **JOB_06:** nine accepted and one rejected consignment record exist.
- **JOB_07:** `LANE_KEY` has eight rows, correct December dates, and the
  expected NULL country for lane `1002`.
- **JOB_08:** `VEHICLE_REG_RAW` has ten rows and accented operator names remain
  intact.
- **JOB_09:** only these exact customer/sequence keys are deleted:
  `CUST00000002/1`, `CUST00000002/2`, and `CUST00000005/3`. All three rows for
  `CUST00000003` survive. A second run is safe.
- **JOB_10:** only customers `CUST00000001`, `CUST00000002`, and
  `CUST00000003` appear. Customers `CUST00000004` through `CUST00000007` do
  not appear. Rerunning appends as the source does.

## Persisted verification report

After successful execution, verify this Delta table exists:

```text
<catalog>.usr_tmpbat.CONVERSION_VERIFICATION_RESULTS
```

Query it with:

```sql
SELECT *
FROM <catalog>.usr_tmpbat.CONVERSION_VERIFICATION_RESULTS
ORDER BY check;
```

It must contain the run timestamp, catalog, check name, status, expected value,
and actual value.

Also verify this JSON report exists:

```text
/Volumes/<catalog>/usr_land/landing/conversion_verification_results.json
```

Inspect it with:

```python
display(dbutils.fs.head(
    "/Volumes/<catalog>/usr_land/landing/conversion_verification_results.json"
))
```

The report is overwritten on every run and represents the latest orchestration
execution. The notebook output must print both report locations and each
individual `PASS` check.

## Acceptance criteria

Mark the conversion successful only when:

1. `SETUP.py` completes.
2. All ten job notebooks complete.
3. All expected output tables exist.
4. All expected row counts match.
5. The calendar business-date check passes.
6. Reject counts match.
7. Content-level checks pass.
8. The verification Delta table exists.
9. The verification JSON file exists.
10. Errors are not silently suppressed.
11. Migration notes are present in every converted notebook.
12. Rerun behavior matches the source behavior.

If anything fails, report the exact notebook, failed block or table, and
expected versus actual values. Do not mark the conversion successful.

Return a final report containing:

```text
- Workspace folder used
- Catalog used
- Notebook execution order
- SETUP.py status
- JOB_01 through JOB_10 status
- Final row-count results
- Content-level verification results
- Reject counts
- Verification Delta table location
- Verification JSON file location
- Rerun behavior results
- Unresolved semantic gaps
```
