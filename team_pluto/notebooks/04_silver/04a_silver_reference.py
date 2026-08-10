# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04a — Silver: REFERENCE Domain
# Tables: silver.statustype, silver.taxrate, silver.tradetype, silver.industry
# Pattern: Bronze → cast types → bronze_to_silver → CORT
# Batch scope: B1 ONLY (static reference data loaded once)
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

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import bronze_to_silver
from modules.delta_utils import create_or_replace_table
from modules.operations import log_row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID = dbutils.widgets.get("batch_id")
RUN_ID   = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = tbl(cfg, "operations", "audit_log")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ─── B1-only guard ────────────────────────────────────────────────────────────
if BATCH_ID != "1":
    print("Reference tables are B1-only — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.statustype
# Columns: ST_ID (string), ST_NAME (string)
# ═══════════════════════════════════════════════════════════════════════════════
src_st  = tbl(cfg, "bronze", "statustype")
tgt_st  = tbl(cfg, "silver", "statustype")

df_st = spark.table(src_st)

df_st = (
    df_st
    .select(
        F.col("ST_ID").cast("string").alias("ST_ID"),
        F.col("ST_NAME").cast("string").alias("ST_NAME"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)
df_st = bronze_to_silver(df_st)

count_st = create_or_replace_table(df_st, tgt_st)
print(f"silver.statustype: {count_st:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_st,
              target_table=tgt_st, operation="OVERWRITE",
              rows_affected=count_st, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.taxrate
# Columns: TX_ID (string), TX_NAME (string), TX_RATE (decimal(15,4))
# ═══════════════════════════════════════════════════════════════════════════════
src_tx = tbl(cfg, "bronze", "taxrate")
tgt_tx = tbl(cfg, "silver", "taxrate")

df_tx = spark.table(src_tx)

df_tx = (
    df_tx
    .select(
        F.col("TX_ID").cast("string").alias("TX_ID"),
        F.col("TX_NAME").cast("string").alias("TX_NAME"),
        F.col("TX_RATE").cast("decimal(15,4)").alias("TX_RATE"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)
df_tx = bronze_to_silver(df_tx)

count_tx = create_or_replace_table(df_tx, tgt_tx)
print(f"silver.taxrate: {count_tx:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_tx,
              target_table=tgt_tx, operation="OVERWRITE",
              rows_affected=count_tx, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.tradetype
# Columns: TT_ID (string), TT_NAME (string), TT_IS_SELL (boolean), TT_IS_MRKT (boolean)
# ═══════════════════════════════════════════════════════════════════════════════
src_tt = tbl(cfg, "bronze", "tradetype")
tgt_tt = tbl(cfg, "silver", "tradetype")

df_tt = spark.table(src_tt)

df_tt = (
    df_tt
    .select(
        F.col("TT_ID").cast("string").alias("TT_ID"),
        F.col("TT_NAME").cast("string").alias("TT_NAME"),
        # Bronze stores "1"/"0" strings — cast to boolean
        (F.col("TT_IS_SELL").cast("int") == 1).alias("TT_IS_SELL"),
        (F.col("TT_IS_MRKT").cast("int") == 1).alias("TT_IS_MRKT"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)
df_tt = bronze_to_silver(df_tt)

count_tt = create_or_replace_table(df_tt, tgt_tt)
print(f"silver.tradetype: {count_tt:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_tt,
              target_table=tgt_tt, operation="OVERWRITE",
              rows_affected=count_tt, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.industry
# Columns: IN_ID (string), IN_NAME (string), IN_SC_ID (string)
# ═══════════════════════════════════════════════════════════════════════════════
src_in = tbl(cfg, "bronze", "industry")
tgt_in = tbl(cfg, "silver", "industry")

df_in = spark.table(src_in)

df_in = (
    df_in
    .select(
        F.col("IN_ID").cast("string").alias("IN_ID"),
        F.col("IN_NAME").cast("string").alias("IN_NAME"),
        F.col("IN_SC_ID").cast("string").alias("IN_SC_ID"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)
df_in = bronze_to_silver(df_in)

count_in = create_or_replace_table(df_in, tgt_in)
print(f"silver.industry: {count_in:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_in,
              target_table=tgt_in, operation="OVERWRITE",
              rows_affected=count_in, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nReference silver complete — B1 only.")
print(f"  silver.statustype : {count_st:,} rows")
print(f"  silver.taxrate    : {count_tx:,} rows")
print(f"  silver.tradetype  : {count_tt:,} rows")
print(f"  silver.industry   : {count_in:,} rows")
