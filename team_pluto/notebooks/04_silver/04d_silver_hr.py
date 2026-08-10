# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04d — Silver: HR Domain
# Tables: silver.hr
# Pattern: Bronze → Cast Types → Dedup (Latest Wins) → bronze_to_silver → CORT
# Batch scope: B1 ONLY (HR data is a static full snapshot)
#
# Notes:
#   - All 50,000 HR employees are written to silver.hr.
#   - Filtering for brokers (job code 314) happens in the Gold layer.
# ═══════════════════════════════════════════════════════════════════════════════

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

# ─── B1-only guard ────────────────────────────────────────────────────────────
if BATCH_ID != "1":
    print("HR table is B1-only — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.hr
# Source: bronze.hr (9 columns, comma-delimited, NO header)
# ═══════════════════════════════════════════════════════════════════════════════
src_hr = tbl(cfg, "bronze", "hr")
tgt_hr = tbl(cfg, "silver", "hr")

df_hr = spark.table(src_hr)

# 1. Type Casting and Renaming
df_hr_typed = (
    df_hr
    .select(
        F.col("EMPLOYEE_ID").cast("bigint").alias("EMPLOYEE_ID"),
        F.col("MANAGER_ID").cast("bigint").alias("MANAGER_ID"),
        F.col("LAST_NAME"),
        F.col("FIRST_NAME"),
        F.col("MIDDLE_INITIAL"),
        F.col("JOB_CODE"),
        F.col("BRANCH_ID"),
        F.col("OFFICE"),
        F.col("PHONE"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file")
    )
)

# 2. Deduplication (Safety step: latest ingestion per Employee ID wins)
w_hr = Window.partitionBy("EMPLOYEE_ID").orderBy(F.col("_ingest_ts").desc())
df_hr_dedup = (
    df_hr_typed
    .withColumn("_rn", F.row_number().over(w_hr))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
)

# 3. Audit Column Rotation
df_hr_silver = bronze_to_silver(df_hr_dedup)

# 4. Final Select for Silver Schema
df_hr_final = df_hr_silver.select(
    "EMPLOYEE_ID", "MANAGER_ID", "LAST_NAME", "FIRST_NAME", 
    "MIDDLE_INITIAL", "JOB_CODE", "BRANCH_ID", "OFFICE", "PHONE",
    "_load_ts", "_batch", "_run_id"
)

count_hr = create_or_replace_table(df_hr_final, tgt_hr)
print(f"silver.hr: {count_hr:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_hr,
              target_table=tgt_hr, operation="OVERWRITE",
              rows_affected=count_hr, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nHR silver complete — B1 only.")