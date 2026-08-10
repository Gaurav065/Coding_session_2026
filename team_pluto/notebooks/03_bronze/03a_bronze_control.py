# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03a — Bronze: CONTROL Domain
# Tables: bronze.batchdate
# Pattern: Landing Parquet → drop _landing_ts → add _ingest_ts → append Delta
# Bronze iron rule: ALL STRING, append-only, partitioned by _batch
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

SOURCE_FILE  = "BatchDate.txt"
LAND_VOL     = landing_volume_path(cfg, BATCH_ID, "batchdate")
BRONZE_TABLE = tbl(cfg, "bronze", "batchdate")
OPS_AUDIT    = tbl(cfg, "operations", "audit_log")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")
print(f"Source : {LAND_VOL}")
print(f"Target : {BRONZE_TABLE}")

# COMMAND ----------

# ─── Read from Landing ───────────────────────────────────────────────────────
df = spark.read.parquet(LAND_VOL)

# ─── Landing → Bronze transformation ────────────────────────────────────────
# 1. Swap _landing_ts → _ingest_ts
# 2. Ensure ALL data columns are STRING (Bronze iron rule)
df = landing_to_bronze(df)
df = cast_all_to_string(df)

df.printSchema()
print(f"Rows to ingest: {df.count()}")

# COMMAND ----------

# ─── Append to Bronze Delta (idempotent: skip if batch+run_id already loaded) ─
count, status = safe_append_bronze(spark, df, BRONZE_TABLE, BATCH_ID, RUN_ID)
print(f"Bronze append: {status} — {count} rows")

log_row_count(spark, OPS_AUDIT, layer="bronze", source_table=SOURCE_FILE,
              target_table=BRONZE_TABLE, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── Verify ──────────────────────────────────────────────────────────────────
display(spark.sql(f"SELECT * FROM {BRONZE_TABLE} ORDER BY batchid"))