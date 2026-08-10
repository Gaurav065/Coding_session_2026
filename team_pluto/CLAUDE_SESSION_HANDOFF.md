# Team Pluto — Claude Session Handoff
> **Purpose**: Complete context for a new Claude instance to pick up this pipeline without re-explaining history.
> **Last updated**: 2026-05-11
> **Project**: PWG 3.0 Charles Schwab Retail Brokerage — TPC-DI on Azure Databricks / Delta Lake

---

## 1. Project Overview

| Property | Value |
|---|---|
| Pipeline name | TPC-DI PWG 3.0 — Charles Schwab Brokerage |
| Platform | Azure Databricks, Delta Lake, Unity Catalog |
| Repo root | `C:\Coding\team_pluto` |
| Notebooks root | `C:\Coding\team_pluto\notebooks\` |
| Modules root | `C:\Coding\team_pluto\modules\` |
| Orchestrator | `notebooks\99_orchestration\run_batch.py` |
| Batches | B1 (historical load), B2, B3 (incremental CDC) |

**Architecture layers (in execution order):**
```
Landing → Bronze → Silver → [Validate Silver] → Staging → Gold → [Validate Gold]
  02        03       04            07b              05       06         07c
```

---

## 2. Full Notebook Inventory

### 00_setup
| File | Purpose |
|---|---|
| `00_catalog_setup.py` | Create Unity Catalog schemas / databases |
| `00b_generate_manifests.py` | Generate file manifests for raw source data |
| `01_verify_raw_access.py` | Verify landing zone access |

### 01_integrity
| File | Purpose |
|---|---|
| `01_integrity_check.py` | Pre-pipeline integrity checks |

### 02_landing (reads raw files → landing tables)
| File | Domain |
|---|---|
| `02a_landing_control.py` | Control / reference data |
| `02b_landing_cross_reference.py` | Cross-reference tables |
| `02c_landing_market.py` | FINWIRE + DailyMarket |
| `02d_landing_hr.py` | HR employee data |
| `02e_landing_customer.py` | CustomerMgmt XML |
| `02f_landing_account.py` | Account data |
| `02g_landing_trade.py` | Trade + TradeHistory |

### 03_bronze (landing → bronze, type-cast + audit cols)
| File | Domain |
|---|---|
| `03a_bronze_control.py` | Control |
| `03b_bronze_cross_reference.py` | Cross-reference |
| `03c_bronze_market.py` | FINWIRE (fixed-width lines), DailyMarket |
| `03d_bronze_hr.py` | HR |
| `03e_bronze_customer.py` | CustomerMgmt |
| `03f_bronze_account.py` | Account |
| `03g_bronze_trade.py` | Trade, TradeHistory, CashTransaction |

### 04_silver (bronze → silver, SCD-1, typed)
| File | Domain | Batch scope |
|---|---|---|
| `04a_silver_reference.py` | Reference (industry, statustype, tradetype, taxrate) | All |
| `04b_silver_date_time.py` | Date + Time dimension seeds | B1 only |
| `04c_silver_market.py` | company (CMP), security (SEC), dailymarket | CMP/SEC: B1 only; dailymarket: all |
| `04d_silver_hr.py` | HR employees | B1 only |
| `04e_silver_customer.py` | Customer (SCD-1 current state) | All |
| `04f_silver_account.py` | Account | All |
| `04g_silver_trade.py` | Trade | All |

### 05_staging (bronze → staging, pre-gold intermediate tables)
| File | Source | Writes |
|---|---|---|
| `05a_staging_finwire.py` | `bronze.finwire` | `staging.finwire_parsed` (CMP+SEC union, B1 only) |
| `05b_staging_market.py` | `bronze.dailymarket` | `staging.dailymarket_current` (SCD-1 + row_hash) |
| `05c_staging_prospect.py` | `bronze.prospect` | `staging.prospect_current` |
| `05d_staging_customer.py` | `bronze.customermgmt` + `bronze.customer` + `bronze.batchdate` | `staging.customer_scd2_versions` |

> **Important**: All 4 staging notebooks read from **bronze only** (not silver). They run after silver in the orchestrator as a safety measure, but have no hard dependency on silver output.

### 06_gold (silver + staging → gold)
| File | Tables produced | Batch scope |
|---|---|---|
| `05a_gold_reference.py` | `gold.industry`, `gold.statustype`, `gold.taxrate`, `gold.tradetype` | All |
| `05b_gold_dim_date_time.py` | `gold.dim_date`, `gold.dim_time` | All |
| `05c_gold_dim_company_security.py` | `gold.dim_company`, `gold.dim_security` | B1 only |
| `05d_gold_dim_broker_customer_account.py` | `gold.dim_broker`, `gold.dim_customer` (SCD-2), `gold.dim_account` | dim_broker: B1; rest: all |
| `05e_gold_dim_trade.py` | `gold.dim_trade` | All |
| `05f_gold_facts.py` | `gold.fact_market_history`, `gold.fact_watches`, `gold.fact_holdings`, `gold.fact_cash_balances` | All |

### 07_validation
| File | Purpose |
|---|---|
| `07a_validate_bronze.py` | Bronze row count + schema checks |
| `07b_validate_silver.py` | Silver row count checks (dynamic, matches bronze for date/time) |
| `07c_validate_gold.py` | Gold row counts, SK=-1 sentinels, SCD-2 validity, RI checks |

---

## 3. Key Data Sources

| Source | Format | Bronze table | Notes |
|---|---|---|---|
| FINWIRE | Fixed-width text (1-based positions) | `bronze.finwire` | B1 only; CMP=companies, SEC=securities, FIN=financials |
| DailyMarket | CSV | `bronze.dailymarket` | Accumulated append across all batches |
| HR | CSV | `bronze.hr` | B1 only; JOB_CODE='314' = brokers |
| CustomerMgmt | XML (ActionType events) | `bronze.customermgmt` | B1 only |
| Customer CDC | Pipe-delimited | `bronze.customer` | B2/B3 CDC |
| Account CDC | Pipe-delimited | `bronze.account` | B2/B3 |
| Trade | CSV | `bronze.trade` | All batches |
| TradeHistory | CSV | `bronze.tradehistory` | All batches |
| CashTransaction | CSV | `bronze.cashtransaction` | All batches |
| Prospect | CSV | `bronze.prospect` | All batches |
| BatchDate | Single-row date file | `bronze.batchdate` | Per-batch effective date |

---

## 4. Known TPC-DI Data Quirks (IMPORTANT)

### 4a. FINWIRE `shares_outstanding` field (SEC records, pos 122-134, 13 chars)
**Problem**: Generator stores `"56757      20"` (leading significand + spaces + trailing scale group) instead of a plain integer.
**Fix** (applied to `04c_silver_market.py` + `05a_staging_finwire.py`):
```python
F.when(
    F.trim(F.substring(F.col("line"), 122, 13)) != "",
    F.regexp_extract(F.substring(F.col("line"), 122, 13), r"^\s*(\d+)", 1)
     .cast("bigint"),
).alias("shares_outstanding"),
```

### 4b. FINWIRE `dividend` field (SEC records, pos 151-162, 12 chars)
**Problem**: Generator stores `"2.66XE"` (valid decimal + junk trailing chars).
**Fix** (applied to `04c_silver_market.py` + `05a_staging_finwire.py`):
```python
F.when(
    F.trim(F.substring(F.col("line"), 151, 12)) != "",
    F.regexp_extract(F.substring(F.col("line"), 151, 12), r"^\s*(-?\d+\.?\d*)", 1)
     .cast("decimal(15,4)"),
).alias("dividend"),
```

### 4c. FINWIRE `ex_date` field (SEC records, pos 114-121, 8 chars)
**Problem**: Some records contain `"NASDAQ65"` (exchange name) instead of a date. `try_to_date` returns NULL, which is correct.

### 4d. CustomerMgmt `ActionTS` field
**Problem**: ISO-8601 format `"2015-01-07T10:25:51"` — `unix_timestamp()` expects a space, not `T`.
**Fix** (applied to `04e_silver_customer.py`):
```python
F.regexp_replace(F.substring(F.col("ActionTS"), 1, 19), "T", " ")
# then parse with format "yyyy-MM-dd HH:mm:ss"
```

### 4e. HR `BRANCH_ID` field
**Problem**: TPC-DI `BRANCH_ID` is a VARCHAR branch name (e.g. `"MiTPrEAoUSnOJGbb gTxWENHNqMjBA"`), **not** a numeric ID. TPC-DI spec defines `DimBroker.Branch` as VARCHAR.
**Fix** (applied to `05d_gold_dim_broker_customer_account.py`):
```python
# WRONG (old):  F.col("BRANCH_ID").cast("int").alias("Branch")
# CORRECT:      F.col("BRANCH_ID").alias("Branch")
```

### 4f. FINWIRE SCD-1 dedup — update versions
**Situation**: FINWIRE contains multiple CMP records per CIK and multiple SEC records per symbol (different `pts` timestamps = update versions). SCD-1 correctly deduplicates.
**Actual counts** (verified via diagnostic):
- `5,000` raw CMP lines → `4,596` distinct CIKs → `silver.company = 4,596 rows` ✓
- `8,000` raw SEC lines → `7,598` distinct symbols → `silver.security = 7,598 rows` ✓

---

## 5. DBR 15+ ANSI Mode Rules (CRITICAL)

Databricks Runtime 15+ runs with ANSI mode ON by default. These functions **throw** on invalid input:

| Old (throws) | Safe replacement |
|---|---|
| `to_date(col, fmt)` | `try_to_date(col, fmt)` |
| `to_timestamp(col, fmt)` | `try_to_timestamp(col, fmt)` |
| `col.cast("date")` on STRING | `try_to_date(col, fmt)` |
| `col.cast("int")` on non-numeric STRING | `try_cast` or `regexp_extract` first |
| `unix_timestamp(col, fmt)` | wrap with `coalesce(..., F.lit(0))` |

**Always use `try_to_date` / `try_to_timestamp` for any user-supplied or fixed-width parsed date/timestamp field.**

---

## 6. SCD Patterns Used

### SCD-1 (keep latest version)
```python
w = Window.partitionBy("key_col").orderBy(F.col("pts").desc())
df = (
    df.withColumn("_rn", F.row_number().over(w))
      .filter(F.col("_rn") == 1)
      .drop("_rn")
)
```
Used for: `silver.company`, `silver.security`, `silver.dailymarket`, `silver.customer`, `silver.account`

### SCD-2 (full version history)
Built in `05d_staging_customer.py` → `staging.customer_scd2_versions`
- One row per `(C_ID, effective_date)` version
- `end_date = DATE_SUB(LEAD(effective_date), 1)`
- `is_current = (end_date IS NULL)`
- `gold.dim_customer` reads from this staging table

### Global Surrogate Key Generation
```python
import warnings
warnings.filterwarnings("ignore", category=UserWarning,
                        message=".*No Partition Defined for Window.*")

w = Window.orderBy(F.col("natural_key").cast("bigint"))
df = df.withColumn("SK_ID", F.row_number().over(w).cast("bigint"))
```
Used in all gold dimension tables. The Spark warning about "No Partition Defined" is intentional and suppressed.

---

## 7. Gold Table Row Count Targets

| Table | Expected rows | Notes |
|---|---|---|
| `gold.dim_date` | 25,933 | From silver.date |
| `gold.dim_time` | 86,400 | From silver.time (all seconds of a day) |
| `gold.dim_company` | **4,596** | NOT 5,000 — SCD-1 dedup of FINWIRE CMP records |
| `gold.dim_security` | **7,598** | NOT 8,658 — SCD-1 dedup of FINWIRE SEC records |
| `gold.dim_broker` | 14,239 | HR rows with JOB_CODE='314' |
| `gold.dim_customer` | 21,890 | SCD-2 all versions across B1/B2/B3 |
| `gold.dim_account` | 56,392 | SCD-1 current state |
| `gold.dim_trade` | 1,302,248 | |
| `gold.fact_market_history` | 5,285,024 | |
| `gold.fact_watches` | 2,412,745 | |
| `gold.fact_cash_balances` | 1,088,273 | |
| `gold.fact_holdings` | 1,206,578 | |

### Tables NOT YET implemented
| Table | Source | Target rows |
|---|---|---|
| `gold.dim_prospect` | `staging.prospect_current` | 49,940 |
| `gold.financial` | FINWIRE FIN records | 457,025 |
| `gold.fact_cash_transactions` | `bronze.cashtransaction` | 1,204,943 |
| `gold.fact_trade_history` | `bronze.tradehistory` | 3,267,433 |

> `05a_staging_finwire.py` does **not** yet parse FIN records — needed for `gold.financial`.

---

## 8. All Fixes Applied (Chronological)

| # | File | Change | Reason |
|---|---|---|---|
| 1 | `07b_validate_silver.py` | Replaced hardcoded date/time counts (25,933 / 86,400) with dynamic `silver_count == bronze_count` check | "keep all rows" policy change |
| 2 | `06_gold/05b_gold_dim_date_time.py` | Full rewrite — was reading `silver.dim_date` (doesn't exist); fixed to read `silver.date`/`silver.time`, compute all calendar attributes from `DateValue` | Critical bug — gold would always fail |
| 3 | `04e_silver_customer.py` | `ActionTS` ISO-8601 T-separator: `regexp_replace(..., "T", " ")` + explicit format `"yyyy-MM-dd HH:mm:ss"` | `CANNOT_PARSE_TIMESTAMP` on `"2015-01-07T10:25:51"` |
| 4 | `05d_gold_dim_broker_customer_account.py` | `BRANCH_ID.cast("int")` → `.alias("Branch")` (keep as STRING) | `CAST_INVALID_INPUT` — branch is a name, not int |
| 5 | `05d_gold_dim_broker_customer_account.py` | `F.to_date()` → `F.try_to_date()` for `C_DOB` | ANSI mode safety |
| 6 | `05c_gold_dim_company_security.py` | Added `import warnings` + suppress `No Partition Defined for Window` | Remove noisy log spam from intentional global ROW_NUMBER() |
| 7 | `05d_gold_dim_broker_customer_account.py` | Same warning suppression | Same reason |
| 8 | `04c_silver_market.py` | `shares_outstanding`: `regexp_extract(r"^\s*(\d+)", 1).cast("bigint")` | TPC-DI quirk: `"56757      20"` |
| 9 | `04c_silver_market.py` | `dividend`: `regexp_extract(r"^\s*(-?\d+\.?\d*)", 1).cast("decimal(15,4)")` | TPC-DI quirk: `"2.66XE"` |
| 10 | `05a_staging_finwire.py` | Same `shares_outstanding` fix as #8 | Same quirk, same fix |
| 11 | `05a_staging_finwire.py` | Same `dividend` fix as #9 | Same quirk, same fix |
| 12 | `05c_gold_dim_company_security.py` | `ex_date`, `first_trade`, `first_trade_on_exchange`: replace `.cast("date")` with `coalesce(try_to_date(...,"yyyy-MM-dd"), try_to_date(...,"yyyyMMdd"))` | `"NASDAQ65"` in STRING column from old silver schema |
| 13 | `05b_staging_market.py` | `F.to_date()` → `F.try_to_date()` for `DM_DATE` | ANSI mode safety |
| 14 | `07c_validate_gold.py` | **New file** — comprehensive gold validation: row counts, SK=-1 checks, price positivity, SCD-2 validity, RI checks; writes to `operations.pipeline_recon_results` | End-to-end pipeline quality gate |
| 15 | `99_orchestration/run_batch.py` | Fixed staging stage names `04b_staging_*` → `04c_staging_*`; added Stage 9 (Validate Gold) | Bug fix + new validation stage |

---

## 9. Module Reference

| Module | Key functions |
|---|---|
| `modules/config_loader.py` | `load_config()`, `tbl(cfg, layer, table)`, `apply_spark_conf(spark, cfg)` |
| `modules/audit_utils.py` | `bronze_to_silver(df)`, `add_staging_audit(df, batch, run_id)`, `add_gold_audit(df, batch, run_id)` |
| `modules/delta_utils.py` | `create_or_replace_table(df, table)`, `overwrite_table(df, table)`, `table_exists(spark, table)` |
| `modules/operations.py` | `log_row_count(spark, audit_tbl, layer, source_table, target_table, operation, rows_affected, batch_id, run_id)` |

---

## 10. Diagnostic SQL Snippets

```python
# Check silver column types (spot DATE vs STRING regressions)
for t in ["company", "security", "dailymarket", "customer", "account", "trade"]:
    spark.sql(f"DESCRIBE {tbl(cfg, 'silver', t)}").show()

# Quick counts across all silver tables
for t in ["company","security","dailymarket","customer","account","trade",
          "hr","date","time","taxrate","industry","statustype","tradetype"]:
    try:
        n = spark.sql(f"SELECT COUNT(*) FROM {tbl(cfg,'silver',t)}").collect()[0][0]
        print(f"  silver.{t:<20}: {n:>10,}")
    except Exception as e:
        print(f"  silver.{t:<20}: ERROR — {e}")

# Sample malformed security fields
spark.sql(f"""
    SELECT symbol, ex_date, first_trade, shares_outstanding, dividend
    FROM   {tbl(cfg,'silver','security')}
    LIMIT  10
""").show()

# Gold SK=-1 check (unmatched foreign keys)
spark.sql(f"""
    SELECT 'fact_market_history' AS fact, COUNT(*) AS sk_minus1_rows
    FROM   {tbl(cfg,'gold','fact_market_history')}
    WHERE  SK_SecurityID = -1
""").show()
```

---

## 11. Pending Work

1. **`gold.dim_prospect`** — implement from `staging.prospect_current`, target 49,940 rows
2. **`gold.financial`** — implement from FINWIRE FIN records; requires FIN record parsing in `05a_staging_finwire.py` first
3. **`gold.fact_cash_transactions`** — implement from `bronze.cashtransaction`, target 1,204,943 rows
4. **`gold.fact_trade_history`** — implement from `bronze.tradehistory`, target 3,267,433 rows
5. **Re-run `04c_silver_market.py`** — to rebuild `silver.security` with proper DATE column types (current table has `ex_date` as STRING from a pre-fix run). Gold notebook is now defensively coded to handle both old and new schemas.

---

## 12. Orchestrator Stage Map

```
Stage 1  : Integrity check
Stage 2  : Landing (parallel — 7 domain notebooks)
Stage 3  : Bronze  (parallel — 7 domain notebooks)
Stage 4  : Silver  (parallel — 7 domain notebooks)
Stage 4b : Validate Silver
Stage 4c : Staging (parallel — 4 notebooks: finwire, market, prospect, customer)
Stage 5  : Gold Group A: reference + dim_date/time  (parallel)
Stage 6  : Gold Group B: company/security + broker/customer/account  (parallel)
Stage 7  : Gold DimTrade
Stage 8  : Gold Facts (fact_market_history, fact_watches, fact_holdings, fact_cash_balances)
Stage 9  : Validate Gold
```

---

*Generated from Claude session — Team Pluto TPC-DI PWG 3.0 pipeline, 2026-05-11*
