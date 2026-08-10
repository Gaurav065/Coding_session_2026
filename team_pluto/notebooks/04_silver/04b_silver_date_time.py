# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04b — Silver: DATE & TIME Reference
# Tables: silver.date, silver.time
# Pattern: CORT — parse date/time strings → write ALL rows to silver (no drops)
# Batch scope: B1 ONLY (static reference data)
#
# Every row from bronze.date / bronze.time lands in silver unchanged except
# that source_date_string / source_time_string is parsed into a typed
# DateValue / TimeValue column.  Rows that cannot be parsed receive
# DateValue / TimeValue = NULL — they are still kept.
# ═══════════════════════════════════════════════════════════════════════════════

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

BATCH_ID  = dbutils.widgets.get("batch_id")
RUN_ID    = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = tbl(cfg, "operations", "audit_log")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

if BATCH_ID != "1":
    print("Date / Time reference files are B1-only — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.date  — ALL rows kept; source_date_string parsed → DateValue (DATE)
#
# 5 formats tried in order (try_to_date returns NULL for no-match):
#   MM/dd/yyyy  — CRM-01
#   yyyy.MM.dd  — ERP-SAP
#   dd-MMM-yy   — MF-LEGACY
#   yyyyMMdd    — TRD-DESK
#   yyyy-MM-dd  — standard fallback
# ═══════════════════════════════════════════════════════════════════════════════
src_date = tbl(cfg, "bronze", "date")
tgt_date = tbl(cfg, "silver", "date")

df_date = spark.table(src_date)

d = "trim(source_date_string)"
df_date = df_date.withColumn("DateValue", F.coalesce(
    F.expr(f"try_to_date({d}, 'MM/dd/yyyy')"),
    F.expr(f"try_to_date({d}, 'yyyy.MM.dd')"),
    F.expr(f"try_to_date({d}, 'dd-MMM-yy')"),
    F.expr(f"try_to_date({d}, 'yyyyMMdd')"),
    F.expr(f"try_to_date({d}, 'yyyy-MM-dd')"),
))

df_date = bronze_to_silver(df_date)

df_date_final = df_date.select(
    F.col("record_id").cast("bigint").alias("record_id"),
    "source_system_code",
    "DateValue",
    "_load_ts", "_batch", "_run_id",
)

count_date = create_or_replace_table(df_date_final, tgt_date)

null_date = spark.sql(f"SELECT COUNT(*) FROM {tgt_date} WHERE DateValue IS NULL").collect()[0][0]
print(f"silver.date: {count_date:,} rows  ({null_date:,} with DateValue=NULL)")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_date,
              target_table=tgt_date, operation="OVERWRITE",
              rows_affected=count_date, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.time  — ALL rows kept; source_time_string parsed → TimeValue (STRING HH:mm:ss)
#
# 2 formats tried:
#   HH:mm:ss  — TRD-SYS
#   HHmmss    — MF-LEGACY compact
# ═══════════════════════════════════════════════════════════════════════════════
src_time = tbl(cfg, "bronze", "time")
tgt_time = tbl(cfg, "silver", "time")

df_time = spark.table(src_time)

t = "trim(source_time_string)"
parsed_ts = F.coalesce(
    F.expr(f"try_to_timestamp({t}, 'HH:mm:ss')"),
    F.expr(f"try_to_timestamp({t}, 'HHmmss')"),
)
df_time = df_time.withColumn("TimeValue", F.date_format(parsed_ts, "HH:mm:ss"))

df_time = bronze_to_silver(df_time)

df_time_final = df_time.select(
    F.col("record_id").cast("bigint").alias("record_id"),
    "source_system_code",
    "time_precision",
    "TimeValue",
    "_load_ts", "_batch", "_run_id",
)

count_time = create_or_replace_table(df_time_final, tgt_time)

null_time = spark.sql(f"SELECT COUNT(*) FROM {tgt_time} WHERE TimeValue IS NULL").collect()[0][0]
print(f"silver.time: {count_time:,} rows  ({null_time:,} with TimeValue=NULL)")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_time,
              target_table=tgt_time, operation="OVERWRITE",
              rows_affected=count_time, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nDate/Time silver complete — B1 only.")
print(f"  silver.date : {count_date:,} rows")
print(f"  silver.time : {count_time:,} rows")
