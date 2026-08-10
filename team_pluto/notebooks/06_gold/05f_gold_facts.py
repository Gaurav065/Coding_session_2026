# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05f — Gold: Fact Tables
# Tables: gold.fact_cash_balances, gold.fact_holdings,
#         gold.fact_market_history, gold.fact_watches
# Pattern: Bronze/Silver → SK lookups → window functions → CORT
# Batch scope: all batches
#
# Temporal SCD-2 note for fact_watches:
#   dim_customer is SCD-2 (one row per version). fact_watches uses W_DTS to
#   look up the customer version that was ACTIVE when the watch was placed:
#     DATE(W_DTS) >= EffectiveDate AND DATE(W_DTS) <= COALESCE(EndDate, 9999-12-31)
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'): del sys.modules[_k]
sys.path.insert(0, _root)

from pyspark.sql import functions as F
from pyspark.sql import Window

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import add_gold_audit
from modules.delta_utils import create_or_replace_table
from modules.operations import log_row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID  = dbutils.widgets.get("batch_id")
RUN_ID    = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = tbl(cfg, "operations", "audit_log")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ─── Shared dimension references ──────────────────────────────────────────────
tgt_date  = tbl(cfg, "gold", "dim_date")
tgt_acct  = tbl(cfg, "gold", "dim_account")
tgt_cust  = tbl(cfg, "gold", "dim_customer")
tgt_sec   = tbl(cfg, "gold", "dim_security")
tgt_trade = tbl(cfg, "gold", "dim_trade")

# ─── Cache shared dimensions ──────────────────────────────────────────────────
# These dimensions are reused across multiple fact tables. Caching prevents
# redundant Delta scans — each fact table sees cached executor memory instead of
# re-reading from storage.
#
# dim_date    (~25 933 rows)  — used by cash_balances, market_history, watches
# dim_security (~6 500 rows)  — used by market_history, watches
# dim_account  (~1.2 M rows)  — used by cash_balances; cached to warm executor
# dim_trade    (~1.3 M rows)  — used TWICE by holdings (holding + current trade)
# dim_customer (SCD-2, 1.5 M+) — used by watches (range/temporal join)

_dim_date_c = (
    spark.table(tgt_date)
    .select(F.col("DateValue").alias("_date_val"), F.col("SK_DateID").alias("_sk_date_id"))
    .cache()
)
_dim_sec_c = (
    spark.table(tgt_sec)
    .select(
        F.col("Symbol").alias("_sec_symbol"),
        F.col("SK_SecurityID").alias("_sk_sec_id"),
        F.col("SK_CompanyID").alias("_sk_co_id"),
    )
    .cache()
)
_dim_acct_c = (
    spark.table(tgt_acct)
    .select(
        F.col("AccountID").alias("_acct_id"),
        F.col("SK_AccountID").alias("_sk_acct_id"),
        F.col("SK_CustomerID").alias("_sk_cust_id"),
    )
    .cache()
)
_dim_trade_c = (
    spark.table(tgt_trade)
    .select(
        F.col("SK_TradeID"),
        F.col("SK_AccountID"),
        F.col("SK_SecurityID"),
        F.col("SK_CompanyID"),
        F.col("SK_CreateDateID"),
    )
    .cache()
)
_dim_cust_c = (
    spark.table(tgt_cust)
    .select(
        F.col("CustomerID").alias("_cust_id"),
        F.col("SK_CustomerID").alias("_sk_cust_id"),
        F.col("EffectiveDate").alias("_eff_date"),
        F.col("EndDate").alias("_end_date"),
    )
    .cache()
)

# Materialise all caches now so subsequent fact tables read from memory
_dim_date_c.count()
_dim_sec_c.count()
_dim_acct_c.count()
_dim_trade_c.count()
_dim_cust_c.count()
print("Shared dimensions cached.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.fact_cash_balances
# Source : bronze.cashtransaction  (read directly — raw types, cast inline)
# Logic  : Daily sum per account → cumulative running sum per account ordered by date
# Grain  : one row per (CT_CA_ID, CT_DTS date)
# ═══════════════════════════════════════════════════════════════════════════════
src_ct  = tbl(cfg, "bronze", "cashtransaction")
tgt_fcb = tbl(cfg, "gold",   "fact_cash_balances")

df_ct_raw = spark.table(src_ct)

# Cast bronze string columns to proper types inline
df_ct = (
    df_ct_raw
    .select(
        F.col("CT_CA_ID").cast("bigint").alias("CT_CA_ID"),
        F.col("CT_DTS").cast("timestamp").alias("CT_DTS"),
        F.col("CT_AMT").cast("decimal(15,4)").alias("CT_AMT"),
        F.col("CT_NAME").cast("string").alias("CT_NAME"),
    )
    .withColumn("CT_DTS_DATE", F.to_date(F.col("CT_DTS")))
)

# Daily cash flow per account per date
df_daily = (
    df_ct
    .groupBy("CT_CA_ID", "CT_DTS_DATE")
    .agg(F.sum("CT_AMT").alias("DailyCashFlow"))
)

# Running cumulative sum (unbounded preceding → current row)
w_running = (
    Window
    .partitionBy("CT_CA_ID")
    .orderBy("CT_DTS_DATE")
    .rowsBetween(Window.unboundedPreceding, 0)
)
df_daily = df_daily.withColumn("Cash", F.sum("DailyCashFlow").over(w_running))

# Dimension lookups — use cached dims; broadcast dim_date (~26 K rows)
df_gacct = _dim_acct_c
df_gdate = F.broadcast(_dim_date_c)

df_fact_cash = (
    df_daily
    .join(df_gacct, df_daily["CT_CA_ID"] == df_gacct["_acct_id"], "left")
    .join(df_gdate, df_daily["CT_DTS_DATE"] == df_gdate["_date_val"], "left")
    .select(
        F.coalesce(F.col("_sk_acct_id"),  F.lit(-1).cast("bigint")).alias("SK_AccountID"),
        F.coalesce(F.col("_sk_cust_id"),  F.lit(-1).cast("bigint")).alias("SK_CustomerID"),
        F.coalesce(F.col("_sk_date_id"),  F.lit(-1).cast("bigint")).alias("SK_DateID"),
        F.col("Cash").cast("decimal(15,4)").alias("Cash"),
    )
)
df_fact_cash = add_gold_audit(df_fact_cash, BATCH_ID, RUN_ID)

count_fcb = create_or_replace_table(df_fact_cash, tgt_fcb)
print(f"gold.fact_cash_balances: {count_fcb:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_ct,
              target_table=tgt_fcb, operation="OVERWRITE",
              rows_affected=count_fcb, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.fact_holdings
# Source : bronze.holdinghistory  (read directly — raw types, cast inline)
# Logic  : Current holding = latest AFTER_QTY per original holding trade (HH_H_T_ID)
#          using ROW_NUMBER OVER (PARTITION BY HH_H_T_ID ORDER BY HH_T_ID DESC) = 1
# Grain  : one row per original holding trade ID
# ═══════════════════════════════════════════════════════════════════════════════
src_hh  = tbl(cfg, "bronze", "holdinghistory")
tgt_fh  = tbl(cfg, "gold",   "fact_holdings")

df_hh_raw = spark.table(src_hh)

df_hh = (
    df_hh_raw
    .select(
        F.col("HH_H_T_ID").cast("bigint").alias("HH_H_T_ID"),
        F.col("HH_T_ID").cast("bigint").alias("HH_T_ID"),
        F.col("HH_BEFORE_QTY").cast("int").alias("HH_BEFORE_QTY"),
        F.col("HH_AFTER_QTY").cast("int").alias("HH_AFTER_QTY"),
    )
)

# Latest holding state per original trade
w_hh = Window.partitionBy("HH_H_T_ID").orderBy(F.col("HH_T_ID").desc())
df_hh_latest = (
    df_hh
    .withColumn("_rn", F.row_number().over(w_hh))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
)

# dim_trade lookups — derive both aliases from the single cached scan
# (avoids two separate Delta reads of the ~1.3 M-row dim_trade table)
df_gtrade_holding = _dim_trade_c.select(
    F.col("SK_TradeID").alias("_hold_sk_trade"),
    F.col("SK_AccountID").alias("_hold_sk_acct"),
    F.col("SK_SecurityID").alias("_hold_sk_sec"),
    F.col("SK_CompanyID").alias("_hold_sk_co"),
    F.col("SK_CreateDateID").alias("_hold_sk_date"),
)
df_gtrade_current = _dim_trade_c.select(
    F.col("SK_TradeID").alias("_curr_sk_trade"),
)

df_fact_holdings = (
    df_hh_latest
    .join(df_gtrade_holding, df_hh_latest["HH_H_T_ID"] == df_gtrade_holding["_hold_sk_trade"], "left")
    .join(df_gtrade_current, df_hh_latest["HH_T_ID"]   == df_gtrade_current["_curr_sk_trade"], "left")
    .select(
        F.col("HH_H_T_ID").alias("SK_TradeID"),
        F.coalesce(F.col("_curr_sk_trade"),  F.lit(-1).cast("bigint")).alias("SK_CurrentTradeID"),
        F.coalesce(F.col("_hold_sk_acct"),   F.lit(-1).cast("bigint")).alias("SK_AccountID"),
        F.coalesce(F.col("_hold_sk_sec"),    F.lit(-1).cast("bigint")).alias("SK_SecurityID"),
        F.coalesce(F.col("_hold_sk_co"),     F.lit(-1).cast("bigint")).alias("SK_CompanyID"),
        F.coalesce(F.col("_hold_sk_date"),   F.lit(-1).cast("bigint")).alias("SK_DateID"),
        F.col("HH_AFTER_QTY").cast("int").alias("CurrentHolding"),
    )
)
df_fact_holdings = add_gold_audit(df_fact_holdings, BATCH_ID, RUN_ID)

count_fh = create_or_replace_table(df_fact_holdings, tgt_fh)
print(f"gold.fact_holdings: {count_fh:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_hh,
              target_table=tgt_fh, operation="OVERWRITE",
              rows_affected=count_fh, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.fact_market_history
# Source : silver.dailymarket
# Logic  : One row per (symbol, date) with 52-week trailing high price + date
# Grain  : one row per (Symbol, Date)
# Note   : Large table (~5M+ rows) — repartition(64) before write
# ═══════════════════════════════════════════════════════════════════════════════
src_dm  = tbl(cfg, "silver", "dailymarket")
tgt_fmh = tbl(cfg, "gold",   "fact_market_history")

df_dm = spark.table(src_dm)

# 52-week trailing window (364 days back in seconds for rangeBetween on unix_timestamp)
w_52wk = (
    Window
    .partitionBy("DM_S_SYMB")
    .orderBy(F.unix_timestamp(F.col("DM_DATE")).cast("long"))
    .rangeBetween(-364 * 86400, 0)
)

df_dm = (
    df_dm
    .withColumn("FiftyTwoWeekHigh",     F.max("DM_CLOSE").over(w_52wk))
    # FiftyTwoWeekHighDate: date of the 52-week high via struct trick (max_by semantics)
    .withColumn(
        "_52wk_struct",
        F.max(F.struct(F.col("DM_CLOSE").alias("c"), F.col("DM_DATE").alias("d"))).over(w_52wk),
    )
    .withColumn("FiftyTwoWeekHighDate", F.col("_52wk_struct.d"))
    .drop("_52wk_struct")
)

# Dimension lookups — cached dims; broadcast both (~6.5 K and ~26 K rows)
df_gsec  = F.broadcast(_dim_sec_c)
df_gdate = F.broadcast(_dim_date_c)

df_fact_mkt = (
    df_dm
    .join(df_gsec,  df_dm["DM_S_SYMB"] == df_gsec["_sec_symbol"],   "left")
    .join(df_gdate, df_dm["DM_DATE"]   == df_gdate["_date_val"],     "left")
    .select(
        F.coalesce(F.col("_sk_sec_id"),  F.lit(-1).cast("bigint")).alias("SK_SecurityID"),
        F.coalesce(F.col("_sk_co_id"),   F.lit(-1).cast("bigint")).alias("SK_CompanyID"),
        F.coalesce(F.col("_sk_date_id"), F.lit(-1).cast("bigint")).alias("SK_DateID"),
        F.col("FiftyTwoWeekHigh").cast("decimal(15,4)").alias("FiftyTwoWeekHigh"),
        F.col("FiftyTwoWeekHighDate").cast("date").alias("FiftyTwoWeekHighDate"),
        F.col("DM_CLOSE").cast("decimal(15,4)").alias("ClosePrice"),
        F.col("DM_HIGH").cast("decimal(15,4)").alias("HighPrice"),
        F.col("DM_LOW").cast("decimal(15,4)").alias("LowPrice"),
        F.col("DM_VOL").cast("bigint").alias("Volume"),
    )
)
df_fact_mkt = add_gold_audit(df_fact_mkt, BATCH_ID, RUN_ID)

# Repartition before writing — this table is 5M+ rows
df_fact_mkt = df_fact_mkt.repartition(64)

count_fmh = create_or_replace_table(df_fact_mkt, tgt_fmh)
print(f"gold.fact_market_history: {count_fmh:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_dm,
              target_table=tgt_fmh, operation="OVERWRITE",
              rows_affected=count_fmh, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.fact_watches
# Source : silver.watchhistory (already filtered to active watches: W_ACTION = 'ACTV')
# Logic  : Point-in-time (temporal) join to dim_customer (SCD-2) using W_DTS
#
# dim_customer has EffectiveDate / EndDate per version. The correct SK is the
# version that was active when the watch was placed (DATE(W_DTS)):
#   EffectiveDate <= DATE(W_DTS) <= COALESCE(EndDate, 9999-12-31)
#
# Grain: one row per active (customer, security) watch
# ═══════════════════════════════════════════════════════════════════════════════
src_wh  = tbl(cfg, "silver", "watchhistory")
tgt_fw  = tbl(cfg, "gold",   "fact_watches")

df_wh = spark.table(src_wh)

# Dimension lookups — reuse all cached dims.
# NOTE: dim_customer uses a range/non-equi join (EffectiveDate ≤ date ≤ EndDate).
# Spark cannot do a broadcast hash join on range predicates — broadcasting here
# would trigger a BroadcastNestedLoopJoin (O(n*m)), which is far slower than
# a sort-merge join for large tables.  Leave df_gcust unbroadcast; AQE handles it.
df_gcust   = _dim_cust_c
df_gsec_w  = F.broadcast(_dim_sec_c)
df_gdate_w = F.broadcast(_dim_date_c)

# Temporal join: find the customer version active at watch placement date
# COALESCE(EndDate, 9999-12-31) handles current (open-ended) versions
_watch_date = F.to_date(df_wh["W_DTS"])
_eff        = df_gcust["_eff_date"]
_end        = F.coalesce(df_gcust["_end_date"], F.lit("9999-12-31").cast("date"))

df_fact_watches = (
    df_wh
    .join(
        df_gcust,
        (df_wh["W_C_ID"].cast("bigint") == df_gcust["_cust_id"]) &
        (_watch_date >= _eff) &
        (_watch_date <= _end),
        "left",
    )
    .join(df_gsec_w,  df_wh["W_S_SYMB"]         == df_gsec_w["_sec_symbol"],   "left")
    .join(df_gdate_w, F.to_date(df_wh["W_DTS"]) == df_gdate_w["_date_val"],    "left")
    .select(
        F.coalesce(F.col("_sk_cust_id"), F.lit(-1).cast("bigint")).alias("SK_CustomerID"),
        F.coalesce(F.col("_sk_sec_id"),  F.lit(-1).cast("bigint")).alias("SK_SecurityID"),
        F.coalesce(F.col("_sk_co_id"),   F.lit(-1).cast("bigint")).alias("SK_CompanyID"),
        F.coalesce(F.col("_sk_date_id"), F.lit(-1).cast("bigint")).alias("SK_DateID"),
        # SK_AccountID is NULL — watches are not account-specific in TPC-DI
        F.lit(None).cast("bigint").alias("SK_AccountID"),
        F.col("W_DTS").cast("timestamp").alias("ActiveSince"),
    )
)
df_fact_watches = add_gold_audit(df_fact_watches, BATCH_ID, RUN_ID)

count_fw = create_or_replace_table(df_fact_watches, tgt_fw)
print(f"gold.fact_watches: {count_fw:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_wh,
              target_table=tgt_fw, operation="OVERWRITE",
              rows_affected=count_fw, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── Release cached dimensions ────────────────────────────────────────────────
_dim_date_c.unpersist()
_dim_sec_c.unpersist()
_dim_acct_c.unpersist()
_dim_trade_c.unpersist()
_dim_cust_c.unpersist()

print(f"\nFact tables gold complete.")
print(f"  gold.fact_cash_balances   : {count_fcb:,} rows")
print(f"  gold.fact_holdings        : {count_fh:,} rows")
print(f"  gold.fact_market_history  : {count_fmh:,} rows")
print(f"  gold.fact_watches         : {count_fw:,} rows (temporal SCD-2 join)")
