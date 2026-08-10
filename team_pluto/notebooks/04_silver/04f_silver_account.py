# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04f — Silver: ACCOUNT Domain
# Tables: silver.account
# Pattern: Full timeline preservation for Gold SCD-2 computation
#
# silver.account — Unified account history:
#   B1 source : bronze.customermgmt
#               ActionType IN (NEW, ADDACCT, UPDACCT, CLOSEACCT)
#               Extract account columns: CA_ID, CA_C_ID (= C_ID), CA_B_ID,
#               CA_NAME, CA_TAX_ST
#               CA_ST_ID = CLOSEACCT → 'CLOS', else → 'ACTV'
#
#   B2/B3 src : bronze.account (CDC_FLAG I/U = active; D = inactive)
#               CA_C_ID already present
#
# Merge strategy: union B1 + B2/B3, retain ALL historical versions.
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'): del sys.modules[_k]
sys.path.insert(0, _root)

from functools import reduce

from pyspark.sql import DataFrame, functions as F

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import bronze_to_silver
from modules.delta_utils import create_or_replace_table, table_exists
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
# B1: Extract account rows from bronze.customermgmt
# ActionType NEW / ADDACCT / UPDACCT → CA_ST_ID = 'ACTV'
# ActionType CLOSEACCT               → CA_ST_ID = 'CLOS'
# ═══════════════════════════════════════════════════════════════════════════════
src_cm   = tbl(cfg, "bronze", "customermgmt")
all_frames = []

if table_exists(spark, src_cm):
    df_cm = (
        spark.table(src_cm)
        .filter(
            F.col("ActionType").isin("NEW", "ADDACCT", "UPDACCT", "CLOSEACCT")
            & F.col("CA_ID").isNotNull()
            & (F.col("CA_ID") != "")
        )
    )

    df_b1_acct = (
        df_cm
        .select(
            F.col("CA_ID").cast("bigint").alias("CA_ID"),
            F.col("C_ID").cast("bigint").alias("CA_C_ID"),
            F.col("CA_B_ID").cast("bigint").alias("CA_B_ID"),
            F.col("CA_NAME").cast("string").alias("CA_NAME"),
            F.col("CA_TAX_ST").cast("string").alias("CA_TAX_ST"),
            F.when(F.col("ActionType") == "CLOSEACCT", F.lit("CLOS"))
             .otherwise(F.lit("ACTV"))
             .alias("CA_ST_ID"),
            F.to_timestamp(F.regexp_replace(F.substring(F.col("ActionTS"), 1, 19), "T", " "), "yyyy-MM-dd HH:mm:ss").alias("update_ts"),
            F.lit(0).cast("bigint").alias("_sort_key"),
            F.col("_batch"),
            F.col("_run_id"),
            F.col("_ingest_ts"),
            F.col("_source_file"),
        )
    )
    all_frames.append(df_b1_acct)
    print(f"B1 customermgmt account rows: {df_b1_acct.count():,}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# B2/B3: bronze.account (CDC_FLAG I/U = active; D = inactive/closed)
# Requires join with silver.batchdate to resolve the effective timestamp
# ═══════════════════════════════════════════════════════════════════════════════
src_acct = tbl(cfg, "bronze", "account")
src_bd   = tbl(cfg, "silver", "batchdate")

if table_exists(spark, src_acct):
    df_acct_raw = spark.table(src_acct)
    df_bd = spark.table(src_bd).select(F.col("batchid"), F.col("batchdate").cast("timestamp").alias("batch_ts"))

    df_b23_acct = (
        df_acct_raw
        .join(F.broadcast(df_bd), F.col("_batch").cast("int") == df_bd["batchid"], "left")
        .select(
            F.col("CA_ID").cast("bigint").alias("CA_ID"),
            F.col("CA_C_ID").cast("bigint").alias("CA_C_ID"),
            F.col("CA_B_ID").cast("bigint").alias("CA_B_ID"),
            F.col("CA_NAME").cast("string").alias("CA_NAME"),
            F.col("CA_TAX_ST").cast("string").alias("CA_TAX_ST"),
            F.when(F.col("CDC_FLAG") == "D", F.lit("CLOS"))
             .otherwise(F.col("CA_ST_ID").cast("string"))
             .alias("CA_ST_ID"),
            F.col("batch_ts").alias("update_ts"),
            F.col("CDC_DSN").cast("bigint").alias("_sort_key"),
            F.col("_batch"),
            F.col("_run_id"),
            F.col("_ingest_ts"),
            F.col("_source_file"),
        )
    )
    all_frames.append(df_b23_acct)
    print(f"B2/B3 account rows: {df_b23_acct.count():,}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Union all sources (DO NOT DEDUPLICATE. Preserve full history for Gold SCD-2)
# ═══════════════════════════════════════════════════════════════════════════════
if not all_frames:
    raise RuntimeError("No account source data found in bronze (expected customermgmt and/or account tables).")

df_all_acct = reduce(DataFrame.unionByName, all_frames)

tgt_acct = tbl(cfg, "silver", "account")

df_acct_final = bronze_to_silver(df_all_acct).select(
    "CA_ID", "CA_C_ID", "CA_B_ID",
    "CA_NAME", "CA_TAX_ST", "CA_ST_ID", "update_ts", "_sort_key",
    "_load_ts", "_batch", "_run_id",
)

count_acct = create_or_replace_table(df_acct_final, tgt_acct)
print(f"silver.account: {count_acct:,} rows (Full history preserved for SCD-2)")

log_row_count(spark, OPS_AUDIT, layer="silver",
              source_table="bronze.customermgmt+bronze.account",
              target_table=tgt_acct, operation="OVERWRITE",
              rows_affected=count_acct, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── Status breakdown ─────────────────────────────────────────────────────────
df_status = spark.table(tgt_acct).groupBy("CA_ST_ID").count().orderBy("CA_ST_ID")
print(f"\nAccount silver complete.")
display(df_status)