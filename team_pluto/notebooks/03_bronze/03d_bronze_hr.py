# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03d — Bronze: HR/BROKER Domain
# Table: bronze.hr
# B1 only, 50,000 employee rows. ALL STRING, append-only.
# Silver keeps all employees; Gold filters to JOB_CODE='314' (brokers).
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

if BATCH_ID != "1":
    print(f"Batch {BATCH_ID}: HR.csv is Batch 1 only — skipping.")
    dbutils.notebook.exit("SKIPPED")

SOURCE_FILE  = "HR.csv"
LAND_HR      = landing_volume_path(cfg, BATCH_ID, "hr")
BRONZE_TABLE = tbl(cfg, "bronze", "hr")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")
print(f"Target: {BRONZE_TABLE}")

# COMMAND ----------

df = spark.read.parquet(LAND_HR)
df = landing_to_bronze(df)
df = cast_all_to_string(df)

count, status = safe_append_bronze(spark, df, BRONZE_TABLE, BATCH_ID, RUN_ID)
log_row_count(spark, OPS_AUDIT, layer="bronze", source_table=SOURCE_FILE,
              target_table=BRONZE_TABLE, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"HR.csv → {BRONZE_TABLE}: {status} ({count:,} rows)")

# COMMAND ----------

# Verify: all 50K rows present
total = spark.sql(f"SELECT COUNT(*) FROM {BRONZE_TABLE}").collect()[0][0]
ok = "✅" if total == 50000 else "⚠ "
print(f"{ok} Total HR rows: {total:,} (expected 50,000)")
