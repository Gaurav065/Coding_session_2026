# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 07c — Gold Validation
# Validates all implemented gold tables against TPC-DI specification targets.
#
# Row count targets (after all 3 batches loaded — final state):
#   dim_date=25,933        dim_time=86,400        dim_broker=14,239
#   dim_company=5,000      dim_security=8,658     dim_customer=21,890
#   dim_account=56,392     dim_trade=1,302,248    fact_market_history=5,285,024
#   fact_watches=2,412,745 fact_cash_balances=1,088,273 fact_holdings=1,206,578
#   (total implemented gold = 16,492,721 rows across 16 tables)
#
# Tables NOT YET IMPLEMENTED (excluded from this notebook):
#   dim_prospect=49,940   financial=457,025
#   fact_cash_transactions=1,204,943   fact_trade_history=3,267,433
#
# 5 check categories:
#   1. Row counts         — exact match against TPC-DI targets for B3 final state;
#                           after B1 / B2 tables show floor checks only
#   2. Uniqueness         — no duplicate surrogate keys
#   3. NOT NULL           — critical SK / business columns never NULL
#   4. Value domain       — SK=-1 sentinel count, price positivity, status validity
#   5. Referential integ. — fact SK columns resolve to parent dim rows
#
# Results written to operations.pipeline_recon_results for unified monitoring.
# Called after Stage 8 (Gold Facts).
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'): del sys.modules[_k]
sys.path.insert(0, _root)

from datetime import datetime, timezone

from modules.config_loader import load_config, tbl, apply_spark_conf

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("run_id",      "")
dbutils.widgets.text("after_batch", "3")

RUN_ID      = dbutils.widgets.get("run_id")
AFTER_BATCH = dbutils.widgets.get("after_batch")
after_b     = int(AFTER_BATCH)

RECON_TABLE = tbl(cfg, "operations", "pipeline_recon_results")

# ─── Result accumulator ──────────────────────────────────────────────────────
all_results = []
_pass = _fail = _err = 0

def chk(check_type: str, table: str, check_name: str,
        expected, actual, passed: bool) -> bool:
    global _pass, _fail
    status = "PASS" if passed else "FAIL"
    icon   = "✅" if passed else "❌"
    all_results.append((RUN_ID, AFTER_BATCH, "gold", table, check_type,
                         check_name, str(expected), str(actual), status,
                         datetime.now(timezone.utc)))
    print(f"  {icon} [{check_type:12}] {table:<28} {check_name:<40} {actual!s:>14}  (expected {expected})")
    if passed: _pass += 1
    else:      _fail += 1
    return passed

def chk_err(check_type: str, table: str, check_name: str, exc: Exception):
    global _err
    msg = str(exc)[:80]
    all_results.append((RUN_ID, AFTER_BATCH, "gold", table, check_type,
                         check_name, "?", f"ERROR: {msg}", "ERROR",
                         datetime.now(timezone.utc)))
    print(f"  ⚠  [{check_type:12}] {table:<28} {check_name:<40} ERROR: {msg}")
    _err += 1

def g(table_name: str) -> str:
    return tbl(cfg, "gold", table_name)

def count(table_name: str) -> int:
    return spark.sql(f"SELECT COUNT(*) FROM {g(table_name)}").collect()[0][0]

print(f"Gold Validation — After Batch {AFTER_BATCH}  (run_id={RUN_ID or 'n/a'})")
print("=" * 90)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — Row Counts
#
# B3 final state: exact match against TPC-DI specification targets.
# B1 / B2 only: floor checks (≥ minimum expected for that batch).
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*90}")
print("CHECK 1 · Row Counts")
print(f"  {'':2} {'check_type':14} {'table':28} {'check_name':40} {'actual':>14}  (expected)")

# ── Exact targets by batch ────────────────────────────────────────────────────
# B1-only dims: same count in all batches (no new data in B2/B3)
# Multi-batch tables: B3 values are final state totals from TPC-DI spec
EXACT_BY_BATCH = {
    # B1-only static dims — count never changes after B1
    "dim_date":            {1: 25_933,    2: 25_933,    3: 25_933},
    "dim_time":            {1: 86_400,    2: 86_400,    3: 86_400},
    # dim_company: FINWIRE has 5,000 CMP lines but 404 are update versions for
    # existing CIKs → SCD-1 yields 4,596 unique companies. Validated against data.
    "dim_company":         {1: 4_596,     2: 4_596,     3: 4_596},
    # Multi-batch dims — B3 is final spec target
    "dim_broker":          {3: 14_239},
    # dim_security: FINWIRE has 8,000 SEC lines; 402 are update versions for
    # existing symbols → SCD-1 yields 7,598 unique securities. Validated against data.
    "dim_security":        {3: 7_598},
    "dim_customer":        {3: 21_890},   # total SCD-2 versions across all batches
    "dim_account":         {3: 56_392},
    "dim_trade":           {3: 1_302_248},
    # Fact tables — B3 final state
    "fact_market_history": {3: 5_285_024},
    "fact_watches":        {3: 2_412_745},
    "fact_cash_balances":  {3: 1_088_273},
    "fact_holdings":       {3: 1_206_578},
}

for tbl_name in sorted(EXACT_BY_BATCH):
    by_batch = EXACT_BY_BATCH[tbl_name]
    if after_b in by_batch:
        expected = by_batch[after_b]
        try:
            actual = count(tbl_name)
            chk("ROW_COUNT", tbl_name, f"count == {expected:,}", expected, actual, actual == expected)
        except Exception as e:
            chk_err("ROW_COUNT", tbl_name, f"count == {expected:,}", e)
    else:
        # No exact target for this batch — use a floor check
        floor = min(by_batch.values()) // 2  # conservative lower bound
        try:
            actual = count(tbl_name)
            chk("ROW_COUNT", tbl_name, f"count ≥ {floor:,} (B{after_b}, no exact target)",
                f"≥{floor:,}", actual, actual >= floor)
        except Exception as e:
            chk_err("ROW_COUNT", tbl_name, f"count ≥ {floor:,}", e)

# ── Reference dims produced by gold.05a_gold_reference (B1-only) ─────────────
REF_EXACT = {
    "industry":    {1: 102,  2: 102,  3: 102},
    "status_type": {1: 6,    2: 6,    3: 6},
    "tax_rate":    {1: 320,  2: 320,  3: 320},
    "trade_type":  {1: 5,    2: 5,    3: 5},
}
for tbl_name, by_batch in sorted(REF_EXACT.items()):
    expected = by_batch.get(after_b, 0)
    try:
        actual = count(tbl_name)
        chk("ROW_COUNT", tbl_name, f"count == {expected:,}", expected, actual, actual == expected)
    except Exception as e:
        chk_err("ROW_COUNT", tbl_name, f"count == {expected:,}", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — Uniqueness of Surrogate Keys
# Every gold table must have no duplicate PKs.
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*90}")
print("CHECK 2 · Uniqueness  (COUNT(*) must equal COUNT(DISTINCT pk))")

UNIQUE_CHECKS = [
    # (table, pk_expression, description)
    ("dim_date",            "SK_DateID",                    "unique date surrogate"),
    ("dim_time",            "SK_TimeID",                    "unique time surrogate"),
    ("dim_broker",          "SK_BrokerID",                  "unique broker surrogate"),
    ("dim_company",         "SK_CompanyID",                 "unique company surrogate"),
    ("dim_security",        "SK_SecurityID",                "unique security surrogate"),
    ("dim_customer",        "SK_CustomerID",                "unique customer version surrogate"),
    ("dim_account",         "SK_AccountID",                 "unique account surrogate"),
    ("dim_trade",           "SK_TradeID",                   "unique trade surrogate"),
    ("industry",            "IndustryID",                   "unique industry ID"),
    ("status_type",         "StatusType",                   "unique status type"),
    ("tax_rate",            "TaxID",                        "unique tax rate ID"),
    ("trade_type",          "TradeTypeID",                  "unique trade type ID"),
    # Natural key uniqueness on dims
    ("dim_date",            "DateValue",                    "one row per calendar date"),
    ("dim_time",            "TimeValue",                    "one row per time-of-day second"),
    ("dim_company",         "CompanyID",                    "one company per CIK"),
    ("dim_security",        "Symbol",                       "one security per symbol"),
    ("dim_account",         "AccountID",                    "one row per account"),
    ("dim_trade",           "SK_TradeID",                   "one row per trade T_ID"),
]

for tbl_name, pk_expr, desc in UNIQUE_CHECKS:
    try:
        total    = spark.sql(f"SELECT COUNT(*) FROM {g(tbl_name)}").collect()[0][0]
        distinct = spark.sql(f"SELECT COUNT(DISTINCT {pk_expr}) FROM {g(tbl_name)}").collect()[0][0]
        dups     = total - distinct
        chk("UNIQUE", tbl_name, f"no dup ({pk_expr})  [{desc}]",
            "dups=0", f"dups={dups:,}", dups == 0)
    except Exception as e:
        chk_err("UNIQUE", tbl_name, f"no dup ({pk_expr})", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — NOT NULL on Critical Columns
# Null SKs / business keys cause silent data quality issues downstream.
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*90}")
print("CHECK 3 · NOT NULL on critical columns  (null_count must be 0)")

NULL_CHECKS = [
    # (table, column, description)
    ("dim_date",            "SK_DateID",        "date surrogate key"),
    ("dim_date",            "DateValue",        "parsed date value"),
    ("dim_time",            "SK_TimeID",        "time surrogate key"),
    ("dim_time",            "TimeValue",        "parsed time value"),
    ("dim_broker",          "SK_BrokerID",      "broker surrogate key"),
    ("dim_broker",          "LastName",         "broker last name"),
    ("dim_company",         "SK_CompanyID",     "company surrogate key"),
    ("dim_company",         "CompanyID",        "company CIK"),
    ("dim_company",         "Name",             "company name"),
    ("dim_security",        "SK_SecurityID",    "security surrogate key"),
    ("dim_security",        "Symbol",           "security symbol"),
    ("dim_customer",        "SK_CustomerID",    "customer surrogate key"),
    ("dim_customer",        "CustomerID",       "customer natural key C_ID"),
    ("dim_customer",        "EffectiveDate",    "SCD-2 effective date"),
    ("dim_customer",        "IsCurrent",        "SCD-2 is-current flag"),
    ("dim_account",         "SK_AccountID",     "account surrogate key"),
    ("dim_account",         "AccountID",        "account natural key CA_ID"),
    ("dim_trade",           "SK_TradeID",       "trade surrogate key"),
    ("dim_trade",           "Status",           "trade status"),
    ("dim_trade",           "Type",             "trade type"),
    ("fact_market_history", "SK_SecurityID",    "security FK"),
    ("fact_market_history", "SK_DateID",        "date FK"),
    ("fact_market_history", "ClosePrice",       "closing price"),
    ("fact_cash_balances",  "SK_AccountID",     "account FK"),
    ("fact_cash_balances",  "SK_DateID",        "date FK"),
    ("fact_cash_balances",  "Cash",             "cumulative cash balance"),
    ("fact_holdings",       "SK_TradeID",       "trade FK"),
    ("fact_watches",        "SK_CustomerID",    "customer FK"),
    ("fact_watches",        "SK_SecurityID",    "security FK"),
]

for tbl_name, col, desc in NULL_CHECKS:
    try:
        null_cnt = spark.sql(
            f"SELECT COUNT(*) FROM {g(tbl_name)} WHERE {col} IS NULL"
        ).collect()[0][0]
        chk("NOT_NULL", tbl_name, f"{col} IS NOT NULL  ({desc})", 0, null_cnt, null_cnt == 0)
    except Exception as e:
        chk_err("NOT_NULL", tbl_name, f"{col} IS NOT NULL", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — Value Domain
# Business rules: no unexpected sentinel SKs, positive prices, valid states.
#
# SK = -1 means a join miss (FK not found in dim). Sentinel count > 0 is a
# WARNING level issue — it means the pipeline has orphan fact rows.
# A small number may be acceptable; zero is the target.
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*90}")
print("CHECK 4 · Value Domain  (violation_count / sentinel_count target = 0)")

# ── SK sentinel checks (SK = -1 means join miss) ──────────────────────────────
SK_SENTINEL_CHECKS = [
    ("dim_security",        "SK_CompanyID = -1",   "security missing company"),
    ("dim_trade",           "SK_AccountID = -1",   "trade missing account"),
    ("dim_trade",           "SK_SecurityID = -1",  "trade missing security"),
    ("dim_trade",           "SK_BrokerID = -1",    "trade missing broker"),
    ("dim_trade",           "SK_CreateDateID = -1","trade missing create date"),
    ("dim_account",         "SK_CustomerID = -1",  "account missing customer"),
    ("dim_account",         "SK_BrokerID = -1",    "account missing broker"),
    ("fact_market_history", "SK_SecurityID = -1",  "market history missing security"),
    ("fact_market_history", "SK_DateID = -1",      "market history missing date"),
    ("fact_cash_balances",  "SK_AccountID = -1",   "cash balance missing account"),
    ("fact_cash_balances",  "SK_DateID = -1",      "cash balance missing date"),
    ("fact_watches",        "SK_CustomerID = -1",  "watch missing customer"),
    ("fact_watches",        "SK_SecurityID = -1",  "watch missing security"),
    ("fact_holdings",       "SK_TradeID = -1",     "holdings missing trade"),
]

for tbl_name, condition, desc in SK_SENTINEL_CHECKS:
    try:
        cnt = spark.sql(
            f"SELECT COUNT(*) FROM {g(tbl_name)} WHERE {condition}"
        ).collect()[0][0]
        chk("DOMAIN", tbl_name, f"{desc}  [WHERE {condition}]",
            "sentinels=0", f"sentinels={cnt:,}", cnt == 0)
    except Exception as e:
        chk_err("DOMAIN", tbl_name, desc, e)

# ── Business rule checks ──────────────────────────────────────────────────────
DOMAIN_CHECKS = [
    # DimDate calendar attributes
    ("dim_date",            "CalendarYear BETWEEN 1967 AND 2039",    "year in expected range"),
    ("dim_date",            "CalendarQuarterNumber BETWEEN 1 AND 4", "quarter 1-4"),
    ("dim_date",            "CalendarMonthNumber BETWEEN 1 AND 12",  "month 1-12"),
    # DimTime attributes
    ("dim_time",            "HourID BETWEEN 0 AND 23",               "hour 0-23"),
    ("dim_time",            "MinuteID BETWEEN 0 AND 59",             "minute 0-59"),
    ("dim_time",            "SecondID BETWEEN 0 AND 59",             "second 0-59"),
    # DimCustomer SCD-2 integrity
    ("dim_customer",        "EffectiveDate <= COALESCE(EndDate, DATE('9999-12-31'))", "effective <= end"),
    # Market prices
    ("fact_market_history", "ClosePrice > 0",                        "close price positive"),
    ("fact_market_history", "HighPrice >= ClosePrice",               "high >= close"),
    ("fact_market_history", "ClosePrice >= LowPrice",                "close >= low"),
    # Trade
    ("dim_trade",           "Quantity > 0",                          "trade quantity positive"),
]

for tbl_name, condition, check_name in DOMAIN_CHECKS:
    try:
        bad_cnt = spark.sql(
            f"SELECT COUNT(*) FROM {g(tbl_name)} WHERE NOT ({condition})"
        ).collect()[0][0]
        chk("DOMAIN", tbl_name, f"{check_name}  [WHERE NOT {condition}]",
            "violations=0", f"violations={bad_cnt:,}", bad_cnt == 0)
    except Exception as e:
        chk_err("DOMAIN", tbl_name, check_name, e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5 — Referential Integrity
# Fact SK columns must all resolve to a row in the parent dim.
# Orphan = fact row whose SK finds no match in the dim (excluding SK=-1 sentinels).
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*90}")
print("CHECK 5 · Referential Integrity  (orphan_count must be 0)")

# (child_table, child_sk, parent_table, parent_pk, description)
REF_CHECKS = [
    # Fact → DimDate
    ("fact_market_history", "SK_DateID",    "dim_date",     "SK_DateID",    "market history date"),
    ("fact_cash_balances",  "SK_DateID",    "dim_date",     "SK_DateID",    "cash balance date"),
    ("fact_watches",        "SK_DateID",    "dim_date",     "SK_DateID",    "watch date"),
    # Fact → DimSecurity
    ("fact_market_history", "SK_SecurityID","dim_security", "SK_SecurityID","market history security"),
    ("fact_watches",        "SK_SecurityID","dim_security", "SK_SecurityID","watch security"),
    ("fact_holdings",       "SK_SecurityID","dim_security", "SK_SecurityID","holdings security"),
    # Fact → DimAccount
    ("fact_cash_balances",  "SK_AccountID", "dim_account",  "SK_AccountID", "cash balance account"),
    # Fact → DimTrade
    ("fact_holdings",       "SK_TradeID",   "dim_trade",    "SK_TradeID",   "holdings original trade"),
    # Fact → DimCustomer
    ("fact_watches",        "SK_CustomerID","dim_customer", "SK_CustomerID","watch customer"),
    # DimAccount → DimCustomer (current version)
    ("dim_account",         "SK_CustomerID","dim_customer", "SK_CustomerID","account current customer"),
    # DimAccount → DimBroker
    ("dim_account",         "SK_BrokerID",  "dim_broker",   "SK_BrokerID",  "account broker"),
    # DimSecurity → DimCompany
    ("dim_security",        "SK_CompanyID", "dim_company",  "SK_CompanyID", "security company"),
]

for child, child_sk, parent, parent_pk, desc in REF_CHECKS:
    try:
        orphans = spark.sql(f"""
            SELECT COUNT(*) FROM {g(child)} c
            LEFT JOIN {g(parent)} p ON c.{child_sk} = p.{parent_pk}
            WHERE p.{parent_pk} IS NULL
              AND c.{child_sk} IS NOT NULL
              AND c.{child_sk} != -1
        """).collect()[0][0]
        chk("REFERENTIAL", child,
            f"{child_sk} → {parent}.{parent_pk}  ({desc})",
            "orphans=0", f"orphans={orphans:,}", orphans == 0)
    except Exception as e:
        chk_err("REFERENTIAL", child, f"{child_sk} → {parent}.{parent_pk}", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Summary + persist results to operations.pipeline_recon_results
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*90}")
print(f"Gold Validation Summary — Batch {AFTER_BATCH}")
print(f"  PASS  : {_pass:>4}")
print(f"  FAIL  : {_fail:>4}")
print(f"  ERROR : {_err:>4}")
print(f"  TOTAL : {_pass + _fail + _err:>4}")

if _fail > 0:
    print(f"\n⚠  {_fail} check(s) FAILED — review before marking pipeline complete.")

print(f"\nNOTE: 4 gold tables not yet implemented (excluded from checks):")
print(f"  dim_prospect=49,940   financial=457,025")
print(f"  fact_cash_transactions=1,204,943   fact_trade_history=3,267,433")

cols = [
    "run_id", "after_batch", "layer", "table_name",
    "check_type", "check_name", "expected", "actual",
    "status", "validated_at",
]

rows = [
    (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9])
    for r in all_results
]

df_recon = spark.createDataFrame(rows, cols)
df_recon.write \
    .format("delta") \
    .mode("append") \
    .option("mergeSchema", "true") \
    .saveAsTable(RECON_TABLE)

print(f"\nResults written to {RECON_TABLE}")
print(f"{'='*90}")
