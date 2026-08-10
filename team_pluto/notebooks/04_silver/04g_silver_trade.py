# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04g — Silver: TRADE Domain
# Tables: silver.trade, silver.watchhistory
# Pattern: CORT (full rebuild each run from ALL bronze batches)
#
# silver.trade — One row per T_ID with current / final status:
#   - SCD-1 per T_ID: keep row with highest T_DTS (most recent state)
#   - opened_dts  : FIRST T_DTS seen for that T_ID (FIRST_VALUE over window)
#   - closed_dts  : T_DTS where final T_ST_ID IN ('CMPT','CNCL'), else NULL
#   - Financial cols (T_TRADE_PRICE, T_CHRG, T_COMM, T_TAX) carried from
#     the final row (populated when trade completes or is cancelled)
#
# silver.watchhistory — Active watches only (last W_ACTION = 'ACTV' per C+S pair):
#   - SCD-1 per (W_C_ID, W_S_SYMB): latest row by W_DTS
#   - Rows where final W_ACTION = 'CNCL' are excluded
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
from pyspark.sql.window import Window

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import bronze_to_silver
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

# ═══════════════════════════════════════════════════════════════════════════════
# silver.trade
#
# bronze.trade accumulates all batches (append-only).
# B1: CDC_FLAG='I' — initial trade rows + TradeHistory holds full status log
# B2/B3: CDC_FLAG='I' = new trade; CDC_FLAG='U' = status update (e.g. to CMPT)
#
# Window strategy:
#   w_asc  — partition by T_ID, order by T_DTS ASC  → FIRST_VALUE = opened_dts
#   w_desc — partition by T_ID, order by T_DTS DESC → ROW_NUMBER = 1 is latest row
# ═══════════════════════════════════════════════════════════════════════════════
src_trade = tbl(cfg, "bronze", "trade")
tgt_trade = tbl(cfg, "silver", "trade")

df_trade_raw = spark.table(src_trade)

# Cast bronze string columns to appropriate types
df_trade = (
    df_trade_raw
    .select(
        F.col("T_ID").cast("bigint").alias("T_ID"),
        # T_DTS: ISO timestamp string — cast to TIMESTAMP for proper ordering
        F.to_timestamp(F.col("T_DTS")).alias("T_DTS"),
        F.col("T_ST_ID").cast("string").alias("T_ST_ID"),
        F.col("T_TT_ID").cast("string").alias("T_TT_ID"),
        (F.col("T_IS_CASH").cast("int") == 1).alias("T_IS_CASH"),
        F.col("T_S_SYMB").cast("string").alias("T_S_SYMB"),
        F.col("T_QTY").cast("int").alias("T_QTY"),
        F.col("T_BID_PRICE").cast("decimal(8,2)").alias("T_BID_PRICE"),
        F.col("T_CA_ID").cast("bigint").alias("T_CA_ID"),
        F.col("T_EXEC_NAME").cast("string").alias("T_EXEC_NAME"),
        F.col("T_TRADE_PRICE").cast("decimal(8,2)").alias("T_TRADE_PRICE"),
        F.col("T_CHRG").cast("decimal(10,2)").alias("T_CHRG"),
        F.col("T_COMM").cast("decimal(10,2)").alias("T_COMM"),
        F.col("T_TAX").cast("decimal(10,2)").alias("T_TAX"),
        F.col("CDC_FLAG").cast("string").alias("CDC_FLAG"),
        F.col("CDC_DSN").cast("bigint").alias("CDC_DSN"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)

# ─── Window specs ─────────────────────────────────────────────────────────────
# Ascending: to find the very first DTS (opened_dts)
w_asc  = Window.partitionBy("T_ID").orderBy(F.col("T_DTS").asc())
# Descending: to identify the latest row (current state)
w_desc = Window.partitionBy("T_ID").orderBy(
    F.col("T_DTS").desc(),
    F.col("CDC_DSN").desc_nulls_last(),
)

df_trade = (
    df_trade
    # opened_dts: first T_DTS for this T_ID (unbounded preceding → current row)
    .withColumn("opened_dts", F.first("T_DTS").over(w_asc.rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)))
    # Row number descending — rn=1 is the latest (current) state
    .withColumn("_rn", F.row_number().over(w_desc))
)

# Keep only the latest row per T_ID
df_trade_latest = df_trade.filter(F.col("_rn") == 1).drop("_rn")

# closed_dts: T_DTS of the latest row when final status is CMPT or CNCL
df_trade_latest = df_trade_latest.withColumn(
    "closed_dts",
    F.when(F.col("T_ST_ID").isin("CMPT", "CNCL"), F.col("T_DTS")).otherwise(F.lit(None).cast("timestamp"))
)

df_trade_latest = bronze_to_silver(df_trade_latest)

df_trade_final = df_trade_latest.select(
    "T_ID", "T_DTS", "T_ST_ID", "T_TT_ID", "T_IS_CASH",
    "T_S_SYMB", "T_QTY", "T_BID_PRICE",
    "T_CA_ID", "T_EXEC_NAME",
    "T_TRADE_PRICE", "T_CHRG", "T_COMM", "T_TAX",
    "opened_dts", "closed_dts",
    "_load_ts", "_batch", "_run_id",
)

count_trade = create_or_replace_table(df_trade_final, tgt_trade)
print(f"silver.trade: {count_trade:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_trade,
              target_table=tgt_trade, operation="OVERWRITE",
              rows_affected=count_trade, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.watchhistory — Active watches only
#
# bronze.watchhistory accumulates all batches.
# For each (W_C_ID, W_S_SYMB) pair, keep the latest row by W_DTS.
# Exclude pairs where the final action is 'CNCL' (cancelled watches).
# ═══════════════════════════════════════════════════════════════════════════════
src_wh = tbl(cfg, "bronze", "watchhistory")
tgt_wh = tbl(cfg, "silver", "watchhistory")

df_wh_raw = spark.table(src_wh)

df_wh = (
    df_wh_raw
    .select(
        F.col("W_C_ID").cast("bigint").alias("W_C_ID"),
        F.col("W_S_SYMB").cast("string").alias("W_S_SYMB"),
        F.to_timestamp(F.col("W_DTS")).alias("W_DTS"),
        F.col("W_ACTION").cast("string").alias("W_ACTION"),
        F.col("CDC_FLAG").cast("string").alias("CDC_FLAG"),
        F.col("CDC_DSN").cast("bigint").alias("CDC_DSN"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)

# SCD-1 per (W_C_ID, W_S_SYMB): latest row by W_DTS then CDC_DSN
w_wh = Window.partitionBy("W_C_ID", "W_S_SYMB").orderBy(
    F.col("W_DTS").desc(),
    F.col("CDC_DSN").desc_nulls_last(),
)

df_wh_dedup = (
    df_wh
    .withColumn("_rn", F.row_number().over(w_wh))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
)

# Keep only active watches (exclude cancelled)
df_wh_active = df_wh_dedup.filter(F.col("W_ACTION") == "ACTV")

df_wh_active = bronze_to_silver(df_wh_active)

df_wh_final = df_wh_active.select(
    "W_C_ID", "W_S_SYMB", "W_DTS", "W_ACTION",
    "_load_ts", "_batch", "_run_id",
)

count_wh = create_or_replace_table(df_wh_final, tgt_wh)
print(f"silver.watchhistory: {count_wh:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_wh,
              target_table=tgt_wh, operation="OVERWRITE",
              rows_affected=count_wh, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── Status breakdown for trades ──────────────────────────────────────────────
df_trade_status = spark.table(tgt_trade).groupBy("T_ST_ID").count().orderBy("T_ST_ID")
print(f"\nTrade silver complete.")
print(f"  silver.trade       : {count_trade:,} rows")
print(f"  silver.watchhistory: {count_wh:,} rows (active watches only)")
display(df_trade_status)
