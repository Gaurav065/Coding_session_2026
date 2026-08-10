# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05b — Staging: MARKET — DailyMarket CDC Detection
# Table: staging.dailymarket_current
#
# Strategy (Incremental CDC Pattern):
#   1. Read bronze.dailymarket but ONLY FOR THE CURRENT BATCH.
#   2. Cast price/volume columns to proper types.
#   3. Compute row_hash from the four price/volume columns.
#   4. Read existing silver.markethistory (to find prior state).
#   5. Compare current batch against silver to emit cdc_action:
#        'N' — New (Date, Symbol) not in silver
#        'C' — Changed (Date, Symbol) exists but hash differs
#        'X' — Unchanged (Date, Symbol) exists and hash matches
#        'D' — Deleted (from source DM_ACTION = 'D')
#   6. Write staging.dailymarket_current (overwrite per batch).
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
from modules.audit_utils import add_staging_audit
from modules.delta_utils import overwrite_table, table_exists
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
# 1. Read CURRENT BATCH from bronze.dailymarket
# ═══════════════════════════════════════════════════════════════════════════════
src_dm = tbl(cfg, "bronze", "dailymarket")
tgt_dm = tbl(cfg, "staging", "dailymarket_current")

df_bronze_all = spark.table(src_dm)

# IMPORTANT: Isolate ONLY the current batch for CDC processing
df_current_batch = df_bronze_all.filter(F.col("_batch") == BATCH_ID)
print(f"bronze.dailymarket (Batch {BATCH_ID} only): {df_current_batch.count():,} rows")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Cast Types & Deduplicate Current Batch
# ═══════════════════════════════════════════════════════════════════════════════
df_typed = df_current_batch.select(
    F.try_to_date(F.col("DM_DATE"), "yyyy-MM-dd").alias("DM_DATE"),
    F.col("DM_S_SYMB").cast("string").alias("DM_S_SYMB"),
    F.col("DM_CLOSE").cast("decimal(15,4)").alias("DM_CLOSE"),
    F.col("DM_HIGH").cast("decimal(15,4)").alias("DM_HIGH"),
    F.col("DM_LOW").cast("decimal(15,4)").alias("DM_LOW"),
    F.col("DM_VOL").cast("bigint").alias("DM_VOL"),
    F.col("DM_RECID").cast("bigint").alias("DM_RECID"),
    # Default to 'I' if action is missing (B1 historical)
    F.coalesce(F.upper(F.trim(F.col("DM_ACTION"))), F.lit("I")).alias("DM_ACTION") 
)

# Dedup within the current batch just in case of multiple updates same day
w_dedup = Window.partitionBy("DM_S_SYMB", "DM_DATE").orderBy(F.col("DM_RECID").desc_nulls_last())

df_dedup = (
    df_typed
    .withColumn("_rn", F.row_number().over(w_dedup))
    .filter(F.col("_rn") == 1)
    .drop("_rn", "DM_RECID")
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Compute row_hash
# ═══════════════════════════════════════════════════════════════════════════════
df_hashed = df_dedup.withColumn(
    "row_hash",
    F.md5(F.concat_ws(
        "|",
        F.col("DM_CLOSE").cast("string"),
        F.col("DM_HIGH").cast("string"),
        F.col("DM_LOW").cast("string"),
        F.col("DM_VOL").cast("string"),
    ))
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Compare with Silver History (if it exists) to get cdc_action
# ═══════════════════════════════════════════════════════════════════════════════
silver_tbl = tbl(cfg, "silver", "dailymarket")

if BATCH_ID == "1" or not table_exists(spark, silver_tbl):
    # Batch 1 is purely historical load. Everything is New.
    df_with_cdc = df_hashed.withColumn("cdc_action", F.lit("N"))
else:
    # Read existing silver history for comparison
    df_silver = spark.table(silver_tbl).select(
        F.col("DM_DATE").alias("s_date"),
        F.col("DM_S_SYMB").alias("s_symb"),
        F.col("row_hash").alias("s_hash")
    )
    
    df_joined = df_hashed.join(
        df_silver,
        (df_hashed["DM_DATE"] == df_silver["s_date"]) & 
        (df_hashed["DM_S_SYMB"] == df_silver["s_symb"]),
        "left"
    )
    
    # Assign CDC Action
    df_with_cdc = df_joined.withColumn(
        "cdc_action",
        F.when(F.col("DM_ACTION") == "D", F.lit("D"))                  # Explicit Delete
         .when(F.col("s_hash").isNull(), F.lit("N"))                   # New (not in Silver)
         .when(F.col("row_hash") != F.col("s_hash"), F.lit("C"))       # Changed
         .otherwise(F.lit("X"))                                        # Unchanged
    ).drop("s_date", "s_symb", "s_hash")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Write staging.dailymarket_current
# ═══════════════════════════════════════════════════════════════════════════════
df_final = df_with_cdc.select(
    "DM_DATE", "DM_S_SYMB",
    "DM_CLOSE", "DM_HIGH", "DM_LOW", "DM_VOL",
    "DM_ACTION", "row_hash", "cdc_action"
)

df_final = add_staging_audit(df_final, BATCH_ID, RUN_ID)

count_dm = overwrite_table(df_final, tgt_dm)
print(f"staging.dailymarket_current written: {count_dm:,} rows")

log_row_count(spark, OPS_AUDIT, layer="staging", source_table=src_dm,
              target_table=tgt_dm, operation="OVERWRITE",
              rows_affected=count_dm, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── Summary ─────────────────────────────────────────────────────────────────
if BATCH_ID != "1":
    count_n = df_final.filter(F.col("cdc_action") == "N").count()
    count_c = df_final.filter(F.col("cdc_action") == "C").count()
    count_x = df_final.filter(F.col("cdc_action") == "X").count()
    count_d = df_final.filter(F.col("cdc_action") == "D").count()
    
    print(f"\nDailyMarket Staging CDC Summary (Batch {BATCH_ID}):")
    print(f"  New (N)      : {count_n:,}")
    print(f"  Changed (C)  : {count_c:,}")
    print(f"  Unchanged (X): {count_x:,}")
    print(f"  Deleted (D)  : {count_d:,}")
else:
    print(f"\nDailyMarket Staging complete (Batch 1 Full Load)")