# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05b — Gold: DimDate + DimTime
# Tables: gold.dim_date, gold.dim_time
# Pattern: silver.date / silver.time → filter valid rows → compute calendar
#          attributes → add gold audit → CORT
# Batch scope: B1 ONLY (date/time dimensions are static reference data)
#
# silver.date schema:  record_id | source_system_code | DateValue | audit cols
# silver.time schema:  record_id | source_system_code | time_precision | TimeValue | audit cols
#
# DateValue / TimeValue may be NULL (rows that couldn't be parsed — kept in
# silver per CORT design). These rows are excluded from gold dims so the
# target counts match the TPC-DI specification:
#   gold.dim_date : 25 933 rows  (valid, deduplicated calendar dates)
#   gold.dim_time : 86 400 rows  (one row per second-of-day, 24×60×60)
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

# ─── B1-only guard ────────────────────────────────────────────────────────────
if BATCH_ID != "1":
    print("DimDate / DimTime are B1-only — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_date
#
# Source : silver.date
#   record_id  → SK_DateID  (natural integer key, already surrogate-ready)
#   DateValue  → DATE column (parsed by silver; NULL rows excluded here)
#
# Calendar attributes are computed from DateValue using Spark date functions:
#   CalendarYear             — F.year()
#   CalendarQuarterNumber    — F.quarter()           (1–4)
#   CalendarMonthNumber      — F.month()             (1–12)
#   CalendarDayOfWeekNumber  — F.dayofweek()         (1=Sunday … 7=Saturday)
#   CalendarDayOfMonthNumber — F.dayofmonth()        (1–31)
#   WeekOfYearNumber         — F.weekofyear()        (1–53)
#   DayOfYearNumber          — F.dayofyear()         (1–366)
#   IsWeekend                — dayofweek IN (1, 7)
#
# dropDuplicates on record_id guards against any duplicate silver rows.
# ═══════════════════════════════════════════════════════════════════════════════
src_dd = tbl(cfg, "silver", "date")
tgt_dd = tbl(cfg, "gold",   "dim_date")

df_dd = (
    spark.table(src_dd)
    .filter(F.col("DateValue").isNotNull())
    .dropDuplicates(["record_id"])
    .select(
        F.col("record_id").cast("bigint").alias("SK_DateID"),
        F.col("DateValue").cast("date").alias("DateValue"),
        F.year(F.col("DateValue")).cast("int").alias("CalendarYear"),
        F.quarter(F.col("DateValue")).cast("int").alias("CalendarQuarterNumber"),
        F.month(F.col("DateValue")).cast("int").alias("CalendarMonthNumber"),
        F.dayofweek(F.col("DateValue")).cast("int").alias("CalendarDayOfWeekNumber"),
        F.dayofmonth(F.col("DateValue")).cast("int").alias("CalendarDayOfMonthNumber"),
        F.weekofyear(F.col("DateValue")).cast("int").alias("WeekOfYearNumber"),
        F.dayofyear(F.col("DateValue")).cast("int").alias("DayOfYearNumber"),
        F.when(F.dayofweek(F.col("DateValue")).isin(1, 7), F.lit(True))
         .otherwise(F.lit(False))
         .alias("IsWeekend"),
    )
)
df_dd = add_gold_audit(df_dd, BATCH_ID, RUN_ID)

count_dd = create_or_replace_table(df_dd, tgt_dd)
print(f"gold.dim_date: {count_dd:,} rows  (target 25,933)")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_dd,
              target_table=tgt_dd, operation="OVERWRITE",
              rows_affected=count_dd, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_time
#
# Source : silver.time
#   record_id  → SK_TimeID  (natural integer key)
#   TimeValue  → STRING "HH:mm:ss" (parsed by silver; NULL rows excluded here)
#
# Time-of-day attributes are extracted by splitting the HH:mm:ss string —
# avoids any timestamp-parsing overhead or ANSI-mode exceptions:
#   HourID   — characters 0-1  (0–23)
#   MinuteID — characters 3-4  (0–59)
#   SecondID — characters 6-7  (0–59)
#
# dropDuplicates on record_id guards against any duplicate silver rows.
# ═══════════════════════════════════════════════════════════════════════════════
src_dt = tbl(cfg, "silver", "time")
tgt_dt = tbl(cfg, "gold",   "dim_time")

_tv = F.col("TimeValue")

df_dt = (
    spark.table(src_dt)
    .filter(_tv.isNotNull())
    .dropDuplicates(["record_id"])
    .select(
        F.col("record_id").cast("bigint").alias("SK_TimeID"),
        _tv.cast("string").alias("TimeValue"),          # HH:mm:ss
        F.split(_tv, ":").getItem(0).cast("int").alias("HourID"),
        F.split(_tv, ":").getItem(1).cast("int").alias("MinuteID"),
        F.split(_tv, ":").getItem(2).cast("int").alias("SecondID"),
    )
)
df_dt = add_gold_audit(df_dt, BATCH_ID, RUN_ID)

count_dt = create_or_replace_table(df_dt, tgt_dt)
print(f"gold.dim_time: {count_dt:,} rows  (target 86,400)")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_dt,
              target_table=tgt_dt, operation="OVERWRITE",
              rows_affected=count_dt, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nDimDate/DimTime gold complete — B1 only.")
print(f"  gold.dim_date : {count_dd:,} rows  (target 25,933)")
print(f"  gold.dim_time : {count_dt:,} rows  (target 86,400)")
