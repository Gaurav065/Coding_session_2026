# Copilot converted scripts

This folder contains the Databricks notebook-source conversions of all ten
Teradata scripts in the hands-on exercise:

| Source | Conversion | Type |
|---|---|---|
| `JOB_01.btq` | [`JOB_01.py`](./JOB_01.py) | BTEQ |
| `JOB_02.btq` | [`JOB_02.py`](./JOB_02.py) | BTEQ |
| `JOB_03.btq` | [`JOB_03.py`](./JOB_03.py) | BTEQ |
| `JOB_04.fex` | [`JOB_04.py`](./JOB_04.py) | FastExport |
| `JOB_05.mld` | [`JOB_05.py`](./JOB_05.py) | MultiLoad |
| `JOB_06.mld` | [`JOB_06.py`](./JOB_06.py) | MultiLoad |
| `JOB_07.btq` | [`JOB_07.py`](./JOB_07.py) | BTEQ |
| `JOB_08.mld` | [`JOB_08.py`](./JOB_08.py) | MultiLoad |
| `JOB_09.btq` | [`JOB_09.py`](./JOB_09.py) | BTEQ |
| `JOB_10.btq` | [`JOB_10.py`](./JOB_10.py) | BTEQ |

[`RUN_ALL.py`](./RUN_ALL.py) is a single orchestrator notebook. It runs
`SETUP.py`, all ten jobs in dependency order, and final row-count checks. Set
`NOTEBOOK_ROOT` to the workspace folder containing `SETUP.py` and these
notebooks, set `CATALOG` to a writable Unity Catalog catalog, and run only
`RUN_ALL.py`.

The complete copy/paste execution prompt is in
[`prompt.md`](./prompt.md).

After a successful run, the orchestrator saves the verification results in two
places:

1. Delta table
   `<catalog>.usr_tmpbat.CONVERSION_VERIFICATION_RESULTS`
2. JSON file
   `/Volumes/<catalog>/usr_land/landing/conversion_verification_results.json`

The notebook output also prints each `PASS` check and both result locations.
The report is overwritten on each run so it always represents the latest
orchestrator execution.

Each `.py` file is Databricks notebook source. Import it into Databricks as a
notebook, provide the documented widgets, and run the setup script before
executing the job.

## Verification results

The expected values below come from the exercise verification guide. They are
the acceptance criteria for the converted notebooks.

| Job | Output | Expected result | Important verification |
|---|---|---:|---|
| JOB_01 | `WT_LOGICALDEL` | 11 rows | Exact campaign/store pairs; duplicate source rows must not survive. |
| JOB_02 | `MT_CALENDAR` | 31 rows | `2026-03-16` has `REL_YMD = 0`; offsets shift by one. A clean failure for the documented date-cast trap is acceptable when explained. |
| JOB_03 | `WD_CMPGN_MON_SUM` | 18 rows | Only months `202501`–`202503`; no `PLAN00000006` or `PLAN00000007`; the two `ST0003` rows per month remain. |
| JOB_04 | `WT_DELKEY_EXP` | 8 rows | Straight copy of the eight store/order pairs. |
| JOB_05 | `WT_PROFITCTR` | 12 rows + 2 rejects | Preserve spaces in the profit-centre codes and place damaged records in the reject table. |
| JOB_06 | `CONSGN_RAW` | 9 rows + 1 reject | Load valid fixed-width records and preserve the rejected record separately. |
| JOB_07 | `LANE_KEY` | 8 rows | Correct surrogate keys, December dates, and the NULL country for lane `1002`. |
| JOB_08 | `VEHICLE_REG_RAW` | 10 rows | Preserve accented operator names and fixed-width parsing. |
| JOB_09 | `FT_TXN_DETAIL` | 15 rows from 18 | Delete only the three exact customer/sequence keys; all three `CUST00000003` rows survive. A second run is safe. |
| JOB_10 | `WD_RENEWAL_PROSPECT` | 3 rows | Only customers `CUST00000001`, `CUST00000002`, and `CUST00000003`; rerunning appends as the source does. |

## Conversion checks performed

- All ten source scripts have a corresponding notebook source file.
- BTEQ, FastExport, and MultiLoad control commands are represented in each
  file's migration-notes section.
- Catalog and environment schemas are supplied through widgets rather than
  hardcoded names.
- Teradata duplicate handling, fixed-width parsing, date arithmetic, joins,
  reject rows, deletes, and surrogate-key assignment are explicitly handled.
- Required widget validation and block-level row-count or cardinality checks
  are included where the source conversion can validate them.
- `python3` syntax compilation passed for all ten notebook-source files after
  removing Databricks magic lines from the temporary validation copy. Databricks
  runtime execution was not available in this repository environment, so the
  result below is intentionally marked as pending runtime execution.

## Runtime verification status

| Verification stage | Status |
|---|---|
| Source-to-notebook coverage | PASS |
| Migration-notes coverage | PASS |
| Static Python syntax review | PASS |
| Databricks setup and notebook execution | Run [`RUN_ALL.py`](./RUN_ALL.py) in Databricks |
| Exact output-table comparison | Final row-count checks run by `RUN_ALL.py`; detailed content checks remain in this README |
| Reset and rerun behavior | PENDING — run after Databricks execution |

Do not mark the batch fully runtime-verified until the three pending stages have
been run against the setup data and compared with the expected results above.
