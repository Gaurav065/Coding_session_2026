# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03c — Bronze: MARKET Domain
# Tables: bronze.finwire, bronze.dailymarket
#
# FINWIRE: raw text lines → bronze.finwire (single STRING column "line")
#   - 203 quarterly files → ~471K lines total
#   - _batch set from actual source batch ("1"), not current run
#   - Bronze accumulates ALL lines; no dedup at bronze (dedup happens in staging)
#
# DailyMarket: normalized 8-col schema
#   - B1: 5.27M rows (large) — partitioned write for performance
#   - B2/B3: 7,360 rows each — normal append
#   - _batch set from DM_DATE-derived batch context or source batch parameter
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
# Evict any stale 'modules' cached from other repos on this shared cluster
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'):
        del sys.modules[_k]
sys.path.insert(0, _root)

from modules.config_loader import load_config, tbl, landing_volume_path, apply_spark_conf
from modules.audit_utils import landing_to_bronze, cast_all_to_string
from modules.delta_utils import safe_append_bronze
from modules.operations import log_row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID = dbutils.widgets.get("batch_id")
RUN_ID = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = tbl(cfg, "operations", "audit_log")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# FINWIRE → bronze.finwire — B1 only
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID == "1":
    SOURCE_FILE = "FINWIRE"
    LAND_FW    = landing_volume_path(cfg, BATCH_ID, "finwire")
    BRONZE_FW  = tbl(cfg, "bronze", "finwire")

    df_fw = spark.read.parquet(LAND_FW)
    df_fw = landing_to_bronze(df_fw)
    df_fw = cast_all_to_string(df_fw)

    # For FINWIRE the "line" column is already a string (raw text)
    # _batch = "1" since all FINWIRE data is historical batch 1

    count, status = safe_append_bronze(spark, df_fw, BRONZE_FW, BATCH_ID, RUN_ID)
    log_row_count(spark, OPS_AUDIT, layer="bronze", source_table=SOURCE_FILE,
                  target_table=BRONZE_FW, operation=status,
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"FINWIRE → {BRONZE_FW}: {status} ({count:,} lines)")

    # Sanity check: show record type distribution from raw lines
    from pyspark.sql import functions as F
    rec_dist = (
        spark.sql(f"SELECT SUBSTRING(line, 16, 3) AS rec_type, COUNT(*) AS cnt FROM {BRONZE_FW} GROUP BY 1 ORDER BY 1")
    )
    print("Record type distribution:")
    rec_dist.show()
else:
    print("FINWIRE: Batch 1 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# DailyMarket → bronze.dailymarket — all batches
# Key: _batch is set from the _source_batch (actual data batch) not run batch.
# This matters because a single pipeline run might process multiple batches.
# The landing notebook already wrote _batch correctly, so we carry it through.
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_FILE = "DailyMarket.txt"
LAND_DM    = landing_volume_path(cfg, BATCH_ID, "dailymarket")
BRONZE_DM  = tbl(cfg, "bronze", "dailymarket")

df_dm = spark.read.parquet(LAND_DM)
df_dm = landing_to_bronze(df_dm)
df_dm = cast_all_to_string(df_dm)

# Repartition before large B1 write for better file sizing
if BATCH_ID == "1":
    df_dm = df_dm.repartition(64)  # ~82K rows per partition for 5.27M rows

count, status = safe_append_bronze(spark, df_dm, BRONZE_DM, BATCH_ID, RUN_ID)
log_row_count(spark, OPS_AUDIT, layer="bronze", source_table=SOURCE_FILE,
              target_table=BRONZE_DM, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"DailyMarket (B{BATCH_ID}) → {BRONZE_DM}: {status} ({count:,} rows)")

# COMMAND ----------

# ─── Cumulative count verification ───────────────────────────────────────────
# Expected: B1=5,270,304 | B1+B2=5,277,664 | B1+B2+B3=5,285,024
total = spark.sql(f"SELECT COUNT(*) FROM {BRONZE_DM}").collect()[0][0]
by_batch = spark.sql(f"SELECT _batch, COUNT(*) as cnt FROM {BRONZE_DM} GROUP BY _batch ORDER BY _batch")
print(f"\nBronze DailyMarket cumulative total: {total:,}")
by_batch.show()
