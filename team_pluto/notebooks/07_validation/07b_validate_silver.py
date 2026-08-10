# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 07b — Silver Validation
# Runs 5 categories of data-quality checks across all silver tables:
#
#   1. Row counts         — exact expected counts for static reference tables;
#                           silver.date/time compared dynamically against bronze
#                           (all rows kept — no filtering, nulls allowed);
#                           floor (≥ N) checks for SCD-1 / CDC derived tables
#   2. Uniqueness         — COUNT(*) == COUNT(DISTINCT pk) for all SCD-1 tables
#   3. NOT NULL           — zero nulls on critical business key columns
#   4. Value domain       — business rules: prices > 0, valid status codes, etc.
#   5. Referential integ. — FK columns all resolve to parent table rows
#
# Results are printed in a structured table and persisted to
# operations.pipeline_recon_results for trend monitoring.
#
# Called after Stage 4 (Silver) and before Stage 4b (Staging).
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
    """Record one check and print a single result line."""
    global _pass, _fail
    status = "PASS" if passed else "FAIL"
    icon   = "✅" if passed else "❌"
    all_results.append((RUN_ID, AFTER_BATCH, "silver", table, check_type,
                         check_name, str(expected), str(actual), status,
                         datetime.now(timezone.utc)))
    print(f"  {icon} [{check_type:12}] {table:<22} {check_name:<38} {actual!s:>12}  (expected {expected})")
    if passed:
        _pass += 1
    else:
        _fail += 1
    return passed

def chk_err(check_type: str, table: str, check_name: str, exc: Exception):
    """Record an ERROR result when the table or column doesn't exist yet."""
    global _err
    msg = str(exc)[:60]
    all_results.append((RUN_ID, AFTER_BATCH, "silver", table, check_type,
                         check_name, "?", f"ERROR: {msg}", "ERROR",
                         datetime.now(timezone.utc)))
    print(f"  ⚠  [{check_type:12}] {table:<22} {check_name:<38} ERROR: {msg}")
    _err += 1

def s(table_name: str) -> str:
    """Return fully-qualified silver table name."""
    return tbl(cfg, "silver", table_name)

def count(table_name: str) -> int:
    return spark.sql(f"SELECT COUNT(*) FROM {s(table_name)}").collect()[0][0]

print(f"Silver Validation — After Batch {AFTER_BATCH}  (run_id={RUN_ID or 'n/a'})")
print("=" * 80)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — Row Counts
# Reference tables: exact match against TPC-DI problem-statement counts.
# Derived SCD-1 / CDC tables: floor check (≥ minimum expected rows).
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*80}")
print("CHECK 1 · Row Counts")
print(f"  {'icon':<2} {'check_type':14} {'table':22} {'check_name':38} {'actual':>12}  (expected)")

# ── Static reference tables (B1-only, unchanged across all batches) ───────────
EXACT = {
    "statustype": {1: 6,      2: 6,      3: 6},
    "taxrate":    {1: 320,    2: 320,    3: 320},
    "tradetype":  {1: 5,      2: 5,      3: 5},
    "industry":   {1: 102,    2: 102,    3: 102},
    # HR is static across all batches
    "hr":         {1: 50_000, 2: 50_000, 3: 50_000},
}

for tbl_name, by_batch in sorted(EXACT.items()):
    expected = by_batch.get(after_b, 0)
    try:
        actual = count(tbl_name)
        chk("ROW_COUNT", tbl_name, f"count == {expected:,}", expected, actual, actual == expected)
    except Exception as e:
        chk_err("ROW_COUNT", tbl_name, f"count == {expected:,}", e)

# ── Date / Time: ALL rows kept — silver count must equal bronze count ─────────
# 04b_silver_date_time keeps every row; rows that cannot be parsed receive
# DateValue / TimeValue = NULL but are never dropped.
for ref_tbl in ("date", "time"):
    try:
        bronze_cnt = spark.sql(
            f"SELECT COUNT(*) FROM {tbl(cfg, 'bronze', ref_tbl)}"
        ).collect()[0][0]
        silver_cnt = count(ref_tbl)
        chk("ROW_COUNT", ref_tbl,
            f"count == bronze.{ref_tbl} (all rows kept)",
            bronze_cnt, silver_cnt, silver_cnt == bronze_cnt)
    except Exception as e:
        chk_err("ROW_COUNT", ref_tbl, f"count == bronze.{ref_tbl}", e)

# ── Derived tables — floor checks (minimum sensible row count) ────────────────
# company / security: B1-only FINWIRE parse — may be absent on B2/B3 reruns
# but the tables themselves should persist from B1.
FLOORS = {
    "company":     (1,           "≥1  B1 FINWIRE CMP"),
    "security":    (1,           "≥1  B1 FINWIRE SEC"),
    "customer":    (40_000,      "≥40 K  SCD-1 per C_ID"),
    "dailymarket": (5_000_000,   "≥5 M  SCD-1 per symbol+date"),
    "prospect":    (40_000,      "≥40 K  latest per agencyid"),
    "account":     (40_000,      "≥40 K  SCD-1 per CA_ID"),
    "trade":       (1_000_000,   "≥1 M  SCD-1 per T_ID"),
    "watchhistory":(500_000,     "≥500 K  active watches"),
}

for tbl_name, (floor, desc) in sorted(FLOORS.items()):
    try:
        actual = count(tbl_name)
        chk("ROW_COUNT", tbl_name, f"count ≥ {floor:,}  ({desc})", f"≥{floor:,}", actual, actual >= floor)
    except Exception as e:
        chk_err("ROW_COUNT", tbl_name, f"count ≥ {floor:,}", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — Uniqueness
# Every SCD-1 silver table must have no duplicate natural keys.
# Detects bugs in dedup window logic (off-by-one, wrong orderBy, etc.).
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*80}")
print("CHECK 2 · Uniqueness  (COUNT(*) must equal COUNT(DISTINCT pk))")

# (table_name, pk_expression, description)
UNIQUE_CHECKS = [
    ("statustype",  "ST_ID",             "unique status codes"),
    ("taxrate",     "TX_ID",             "unique tax IDs"),
    ("tradetype",   "TT_ID",             "unique trade type IDs"),
    ("industry",    "IN_ID",             "unique industry IDs"),
    ("company",     "cik",               "SCD-1 per CIK"),
    ("security",    "symbol",            "SCD-1 per symbol"),
    ("customer",    "C_ID",              "SCD-1 per C_ID"),
    ("dailymarket", "DM_S_SYMB, DM_DATE","SCD-1 per symbol+date"),
    ("prospect",    "agencyid",          "latest per agencyid"),
    ("account",     "CA_ID",             "SCD-1 per CA_ID"),
    ("trade",       "T_ID",              "SCD-1 per T_ID"),
    ("watchhistory","W_C_ID, W_S_SYMB",  "active per customer+symbol"),
]

for tbl_name, pk_expr, desc in UNIQUE_CHECKS:
    try:
        total    = spark.sql(f"SELECT COUNT(*)           FROM {s(tbl_name)}").collect()[0][0]
        distinct = spark.sql(f"SELECT COUNT(DISTINCT {pk_expr}) FROM {s(tbl_name)}").collect()[0][0]
        dups     = total - distinct
        chk("UNIQUE", tbl_name, f"no dup ({pk_expr})  [{desc}]",
            f"dups=0", f"dups={dups:,}", dups == 0)
    except Exception as e:
        chk_err("UNIQUE", tbl_name, f"no dup ({pk_expr})", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — NOT NULL on Critical Columns
# Business keys and dimensional identifiers that downstream gold tables depend on.
# NULL here means a join to gold will silently produce SK=-1 (unknown member).
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*80}")
print("CHECK 3 · NOT NULL on critical columns  (null_count must be 0)")

NULL_CHECKS = [
    # table_name, column, description
    ("customer",    "C_ID",       "customer natural key"),
    ("customer",    "C_STATUS",   "customer status"),
    ("customer",    "C_L_NAME",   "customer last name"),
    ("customer",    "C_F_NAME",   "customer first name"),
    ("company",     "cik",        "company CIK"),
    ("company",     "company_name","company name"),
    ("security",    "symbol",     "security symbol"),
    ("dailymarket", "DM_S_SYMB",  "market symbol"),
    ("dailymarket", "DM_DATE",    "market date"),
    ("dailymarket", "DM_CLOSE",   "closing price"),
    ("trade",       "T_ID",       "trade ID"),
    ("trade",       "T_ST_ID",    "trade status"),
    ("trade",       "T_TT_ID",    "trade type"),
    ("trade",       "T_S_SYMB",   "trade symbol"),
    ("trade",       "T_QTY",      "trade quantity"),
    ("trade",       "T_CA_ID",    "trade account ID"),
    ("trade",       "opened_dts", "trade open timestamp"),
    ("account",     "CA_ID",      "account ID"),
    ("account",     "CA_C_ID",    "account customer ID"),
    ("watchhistory","W_C_ID",     "watch customer ID"),
    ("watchhistory","W_S_SYMB",   "watch symbol"),
    ("watchhistory","W_DTS",      "watch timestamp"),
    ("taxrate",     "TX_RATE",    "tax rate value"),
]

for tbl_name, col, desc in NULL_CHECKS:
    try:
        null_cnt = spark.sql(
            f"SELECT COUNT(*) FROM {s(tbl_name)} WHERE {col} IS NULL"
        ).collect()[0][0]
        chk("NOT_NULL", tbl_name, f"{col} IS NOT NULL  ({desc})", 0, null_cnt, null_cnt == 0)
    except Exception as e:
        chk_err("NOT_NULL", tbl_name, f"{col} IS NOT NULL", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — Value Domain
# Business rules: prices must be positive, status codes must be in a known set,
# market OHLC ordering must hold (High ≥ Close ≥ Low), etc.
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*80}")
print("CHECK 4 · Value Domain  (violation_count must be 0)")

# (table, condition_that_must_be_TRUE, friendly_name)
DOMAIN_CHECKS = [
    # DailyMarket OHLC sanity
    ("dailymarket", "DM_CLOSE > 0",           "close_price_positive"),
    ("dailymarket", "DM_HIGH  > 0",           "high_price_positive"),
    ("dailymarket", "DM_LOW   > 0",           "low_price_positive"),
    ("dailymarket", "DM_VOL   >= 0",          "volume_non_negative"),
    ("dailymarket", "DM_HIGH >= DM_CLOSE",    "high >= close"),
    ("dailymarket", "DM_CLOSE >= DM_LOW",     "close >= low"),
    # Customer status domain
    ("customer",    "C_STATUS IN ('Active','Inactive')",   "valid_customer_status"),
    # Account status domain
    ("account",     "CA_ST_ID IN ('ACTV','INAC')",         "valid_account_status"),
    # Trade business rules
    ("trade",       "T_QTY > 0",              "trade_qty_positive"),
    ("trade",       "T_ST_ID IN ('ACTV','CMPT','CNCL','SBMT','PNDG')",
                                               "valid_trade_status"),
    # Taxrate
    ("taxrate",     "TX_RATE > 0",            "tax_rate_positive"),
    # Security shares outstanding
    ("security",    "shares_outstanding IS NULL OR shares_outstanding > 0",
                                               "shares_outstanding_positive_or_null"),
]

for tbl_name, condition, check_name in DOMAIN_CHECKS:
    try:
        bad_cnt = spark.sql(
            f"SELECT COUNT(*) FROM {s(tbl_name)} WHERE NOT ({condition})"
        ).collect()[0][0]
        chk("DOMAIN", tbl_name, f"{check_name}  [WHERE NOT {condition}]",
            "violations=0", f"violations={bad_cnt:,}", bad_cnt == 0)
    except Exception as e:
        chk_err("DOMAIN", tbl_name, check_name, e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5 — Referential Integrity
# FK columns in child tables must have matching rows in their parent table.
# Orphan count > 0 means gold dimension joins will silently produce SK = -1.
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'─'*80}")
print("CHECK 5 · Referential Integrity  (orphan_count must be 0)")

# (child_table, child_col, parent_table, parent_col, description)
REF_CHECKS = [
    ("trade",        "T_S_SYMB",  "security", "symbol",  "trade symbol → security"),
    ("trade",        "T_CA_ID",   "account",  "CA_ID",   "trade account → account"),
    ("account",      "CA_C_ID",   "customer", "C_ID",    "account owner → customer"),
    ("watchhistory", "W_C_ID",    "customer", "C_ID",    "watch customer → customer"),
    ("watchhistory", "W_S_SYMB",  "security", "symbol",  "watch symbol → security"),
    # dailymarket symbols should all be in security (B1+ only)
    ("dailymarket",  "DM_S_SYMB", "security", "symbol",  "market symbol → security"),
]

for child, child_col, parent, parent_col, desc in REF_CHECKS:
    try:
        orphans = spark.sql(f"""
            SELECT COUNT(*) FROM {s(child)} c
            LEFT JOIN {s(parent)} p ON c.{child_col} = p.{parent_col}
            WHERE p.{parent_col} IS NULL
              AND c.{child_col}  IS NOT NULL
        """).collect()[0][0]
        chk("REFERENTIAL", child,
            f"{child_col} → {parent}.{parent_col}  ({desc})",
            "orphans=0", f"orphans={orphans:,}", orphans == 0)
    except Exception as e:
        chk_err("REFERENTIAL", child, f"{child_col} → {parent}.{parent_col}", e)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Summary + persist results to operations.pipeline_recon_results
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*80}")
print(f"Silver Validation Summary — Batch {AFTER_BATCH}")
print(f"  PASS  : {_pass:>4}")
print(f"  FAIL  : {_fail:>4}")
print(f"  ERROR : {_err:>4}")
print(f"  TOTAL : {_pass + _fail + _err:>4}")

if _fail > 0:
    print(f"\n⚠  {_fail} check(s) FAILED — review before running Gold.")

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
print(f"{'='*80}")
