# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05c — Staging: PROSPECT CDC action detection
# Table: staging.prospect_current
#
# Strategy:
#   1. Read ALL bronze.prospect rows accumulated across all batches.
#   2. Compute first_batchid per agencyid = MIN(_batch).
#   3. Compute row_hash per row from the 22 business columns.
#   4. Keep the latest row per agencyid (highest _batch — the "current" state).
#   5. Keep the second-latest row per agencyid (the "previous" state for change
#      detection).
#   6. Derive cdc_action:
#        'N' — no previous row (new prospect in this batch)
#        'C' — previous row exists and row_hash differs (changed)
#        'X' — previous row exists and row_hash matches (unchanged)
#
# Batch scope: ALL batches (full rebuild from accumulated bronze each run).
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
from modules.delta_utils import overwrite_table
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
# Read ALL accumulated bronze.prospect rows
# ═══════════════════════════════════════════════════════════════════════════════
src_pros = tbl(cfg, "bronze", "prospect")
tgt_pros = tbl(cfg, "staging", "prospect_current")

df_bronze = spark.table(src_pros)
print(f"bronze.prospect total rows (all batches): {df_bronze.count():,}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Business columns — 22 fields that define a prospect's identity/attributes
# ═══════════════════════════════════════════════════════════════════════════════
BUSINESS_COLS = [
    "agencyid", "lastname", "firstname", "middleinitial", "gender",
    "addressline1", "addressline2", "postalcode", "city", "state", "country",
    "phone", "income", "numbercars", "numberchildren", "maritalstatus",
    "age", "creditrating", "ownorrentflag", "employer",
    "numbercreditcards", "networth",
]

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: Compute first_batchid per agencyid = MIN(_batch)
# ═══════════════════════════════════════════════════════════════════════════════
df_first = (
    df_bronze
    .groupBy("agencyid")
    .agg(F.min(F.col("_batch").cast("int")).cast("string").alias("first_batchid"))
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: Compute row_hash per row from the 22 business columns
# ═══════════════════════════════════════════════════════════════════════════════
hash_col = F.md5(F.concat_ws("|", *[F.col(c).cast("string") for c in BUSINESS_COLS]))
df_hashed = df_bronze.withColumn("row_hash", hash_col)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: Keep the latest row per agencyid (current state)
#   ROW_NUMBER per agencyid ORDER BY _batch DESC — rank 1 = most recent batch
# ═══════════════════════════════════════════════════════════════════════════════
w_latest = Window.partitionBy("agencyid").orderBy(F.col("_batch").cast("int").desc())

df_current = (
    df_hashed
    .withColumn("_rn", F.row_number().over(w_latest))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: Keep the second-latest row per agencyid (previous state for change
# detection — rank 2 in the same window)
# ═══════════════════════════════════════════════════════════════════════════════
w_prev = Window.partitionBy("agencyid").orderBy(F.col("_batch").cast("int").desc())

df_prev = (
    df_hashed
    .withColumn("_rn", F.row_number().over(w_prev))
    .filter(F.col("_rn") == 2)
    .drop("_rn")
    .select("agencyid", F.col("row_hash").alias("prev_hash"))
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: Join current + prev + first_batchid, then derive cdc_action
#   'N' — no previous row (new prospect, no prior batch entry)
#   'C' — previous row exists but row_hash differs (data changed between batches)
#   'X' — previous row exists and row_hash matches (unchanged)
# ═══════════════════════════════════════════════════════════════════════════════
df_joined = (
    df_current
    .join(df_prev, on="agencyid", how="left")
    .join(df_first, on="agencyid", how="left")
)

df_with_cdc = df_joined.withColumn(
    "cdc_action",
    F.when(F.col("prev_hash").isNull(), F.lit("N"))
     .when(F.col("row_hash") != F.col("prev_hash"), F.lit("C"))
     .otherwise(F.lit("X"))
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: Select final columns and write staging.prospect_current
#   Output: 22 business cols + first_batchid + cdc_action + row_hash + audit
# ═══════════════════════════════════════════════════════════════════════════════
df_final = df_with_cdc.select(
    *BUSINESS_COLS,
    "first_batchid",
    "cdc_action",
    "row_hash",
)

df_final = add_staging_audit(df_final, BATCH_ID, RUN_ID)

count_total = overwrite_table(df_final, tgt_pros)
print(f"staging.prospect_current written: {count_total:,} rows")

log_row_count(spark, OPS_AUDIT, layer="staging", source_table=src_pros,
              target_table=tgt_pros, operation="OVERWRITE",
              rows_affected=count_total, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── CDC action breakdown ─────────────────────────────────────────────────────
count_n = df_final.filter(F.col("cdc_action") == "N").count()
count_c = df_final.filter(F.col("cdc_action") == "C").count()
count_x = df_final.filter(F.col("cdc_action") == "X").count()

print(f"\nProspect staging complete.")
print(f"  staging.prospect_current: {count_total:,} rows")
print(f"    N (new)      : {count_n:,}")
print(f"    C (changed)  : {count_c:,}")
print(f"    X (unchanged): {count_x:,}")