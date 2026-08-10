# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04c — Silver: MARKET Domain
# Tables:
#   silver.company     — FINWIRE CMP records, ALL VERSIONS KEPT for SCD-2 (B1 only)
#   silver.security    — FINWIRE SEC records, ALL VERSIONS KEPT for SCD-2 (B1 only)
#   silver.dailymarket — DailyMarket prices, SCD-1 per symbol+date  (all batches)
#
# FINWIRE: fixed-width text in bronze.finwire.line; positions are 1-based.
# DailyMarket: accumulate all batches, keep latest per (DM_S_SYMB, DM_DATE).
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
# FINWIRE — silver.company + silver.security  (B1 only)
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID == "1":

    src_fw = tbl(cfg, "bronze", "finwire")
    df_fw  = spark.table(src_fw)

    # ─── Helper: extract fixed-width field (Spark F.substring is 1-based) ────
    def fw(col_name: str, start: int, length: int):
        return F.trim(F.substring(F.col("line"), start, length)).alias(col_name)

    # ─── CMP records → silver.company ────────────────────────────────────────
    tgt_cmp = tbl(cfg, "silver", "company")

    df_cmp_raw = df_fw.filter(F.trim(F.substring(F.col("line"), 16, 3)) == "CMP")

    df_cmp = (
        df_cmp_raw
        .select(
            fw("pts",           1,  15),
            fw("company_name", 19,  60),
            fw("cik",          79,  10),
            fw("status",       89,   4),
            fw("industry_id",  93,   8),
            fw("sp_rating",   101,   9),
            F.try_to_date(F.trim(F.substring(F.col("line"), 110, 8)), "yyyyMMdd").alias("founding_date"),
            fw("addr_line1",  118,  80),
            fw("addr_line2",  198,  80),
            fw("postal_code", 278,  12),
            fw("city",        290,  25),
            fw("state_prov",  315,  20),
            fw("country",     335,  24),
            fw("ceo_name",    359,  46),
            fw("description", 405, 150),
            F.col("_batch"),
            F.col("_run_id"),
            F.col("_ingest_ts"),
            F.col("_source_file"),
        )
    )

    _cmp_total     = df_cmp.count()
    _cmp_empty_cik = df_cmp.filter(F.col("cik").isNull() | (F.col("cik") == "")).count()
    print(f"  CMP raw lines  : {_cmp_total:,}")
    print(f"  Empty/null CIK : {_cmp_empty_cik:,} (excluded)")
    print(f"  Valid CIK rows : {_cmp_total - _cmp_empty_cik:,} ← expected silver.company count (History Preserved for SCD-2)")

    df_cmp = df_cmp.filter(F.col("cik").isNotNull() & (F.col("cik") != ""))

    df_cmp = bronze_to_silver(df_cmp)

    count_cmp = create_or_replace_table(df_cmp, tgt_cmp)
    print(f"silver.company: {count_cmp:,} rows")

    log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_fw,
                  target_table=tgt_cmp, operation="OVERWRITE",
                  rows_affected=count_cmp, batch_id=BATCH_ID, run_id=RUN_ID)

    # ─── SEC records → silver.security ───────────────────────────────────────
    tgt_sec = tbl(cfg, "silver", "security")

    df_sec_raw = df_fw.filter(F.trim(F.substring(F.col("line"), 16, 3)) == "SEC")

    df_sec = (
        df_sec_raw
        .select(
            fw("pts",                       1,  15),
            fw("symbol",                   19,  15),
            fw("issue_type",               34,   6),
            fw("status",                   40,   4),
            fw("name",                     44,  70),
            F.try_to_date(F.trim(F.substring(F.col("line"), 114, 8)), "yyyyMMdd").alias("ex_date"),
            F.when(
                F.trim(F.substring(F.col("line"), 122, 13)) != "",
                F.regexp_extract(F.substring(F.col("line"), 122, 13), r"^\s*(\d+)", 1)
                 .cast("bigint"),
            ).alias("shares_outstanding"),
            F.try_to_date(F.trim(F.substring(F.col("line"), 135, 8)), "yyyyMMdd").alias("first_trade"),
            F.try_to_date(F.trim(F.substring(F.col("line"), 143, 8)), "yyyyMMdd").alias("first_trade_on_exchange"),
            F.when(
                F.trim(F.substring(F.col("line"), 151, 12)) != "",
                F.regexp_extract(F.substring(F.col("line"), 151, 12), r"^\s*(-?\d+\.?\d*)", 1)
                 .cast("decimal(15,4)"),
            ).alias("dividend"),
            fw("co_name_or_cik",          163,  60),
            F.col("_batch"),
            F.col("_run_id"),
            F.col("_ingest_ts"),
            F.col("_source_file"),
        )
    )

    _sec_total     = df_sec.count()
    _sec_empty_sym = df_sec.filter(F.col("symbol").isNull() | (F.col("symbol") == "")).count()
    print(f"  SEC raw lines  : {_sec_total:,}")
    print(f"  Empty/null sym : {_sec_empty_sym:,}  (excluded)")
    print(f"  Valid sym rows : {_sec_total - _sec_empty_sym:,} ← expected silver.security count (History Preserved for SCD-2)")

    df_sec = df_sec.filter(F.col("symbol").isNotNull() & (F.col("symbol") != ""))

    df_sec = bronze_to_silver(df_sec)

    count_sec = create_or_replace_table(df_sec, tgt_sec)
    print(f"silver.security: {count_sec:,} rows")

    log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_fw,
                  target_table=tgt_sec, operation="OVERWRITE",
                  rows_affected=count_sec, batch_id=BATCH_ID, run_id=RUN_ID)

else:
    print(f"  silver.company   : B1-only — SKIPPED for batch {BATCH_ID}")
    print(f"  silver.security  : B1-only — SKIPPED for batch {BATCH_ID}")
    count_cmp = count_sec = None

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.dailymarket  (all batches — bronze.dailymarket)
# ═══════════════════════════════════════════════════════════════════════════════
src_dm = tbl(cfg, "bronze", "dailymarket")
tgt_dm = tbl(cfg, "silver", "dailymarket")

df_dm_raw = spark.table(src_dm)

df_dm = (
    df_dm_raw
    .select(
        F.to_date(F.col("DM_DATE"), "yyyy-MM-dd").alias("DM_DATE"),
        F.col("DM_S_SYMB").cast("string").alias("DM_S_SYMB"),
        F.col("DM_CLOSE").cast("decimal(15,4)").alias("DM_CLOSE"),
        F.col("DM_HIGH").cast("decimal(15,4)").alias("DM_HIGH"),
        F.col("DM_LOW").cast("decimal(15,4)").alias("DM_LOW"),
        F.col("DM_VOL").cast("bigint").alias("DM_VOL"),
        F.col("DM_RECID").cast("bigint").alias("DM_RECID"),
        F.col("_batch"),
        F.col("_run_id"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
    )
)

w_dm = Window.partitionBy("DM_S_SYMB", "DM_DATE").orderBy(F.col("DM_RECID").desc_nulls_last())
df_dm = (
    df_dm
    .withColumn("_rn", F.row_number().over(w_dm))
    .filter(F.col("_rn") == 1)
    .drop("_rn", "DM_RECID")
)

df_dm = bronze_to_silver(df_dm)

count_dm = create_or_replace_table(df_dm, tgt_dm)
print(f"silver.dailymarket: {count_dm:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_dm,
              target_table=tgt_dm, operation="OVERWRITE",
              rows_affected=count_dm, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nMarket silver complete.")
if BATCH_ID == "1":
    print(f"  silver.company   : {count_cmp:,} rows (CMP, ALL VERSIONS KEPT)")
    print(f"  silver.security  : {count_sec:,} rows (SEC, ALL VERSIONS KEPT)")
print(f"  silver.dailymarket: {count_dm:,} rows (SCD-1 per symbol+date)")