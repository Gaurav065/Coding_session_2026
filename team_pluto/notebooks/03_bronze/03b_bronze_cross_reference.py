# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03b — Bronze: CROSS-DOMAIN REFERENCE Domain
# Tables: bronze.date, bronze.time, bronze.statustype, bronze.taxrate,
#         bronze.industry, bronze.tradetype
# All B1-only files. Pattern: Landing Parquet → append Delta (ALL STRING).
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
    print(f"Batch {BATCH_ID}: cross-domain reference is B1 only — skipping.")
    dbutils.notebook.exit("SKIPPED")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ─── Generic helper ──────────────────────────────────────────────────────────
def ingest_to_bronze(source_file: str, table_name: str) -> int:
    land_vol   = landing_volume_path(cfg, BATCH_ID, table_name)
    bronze_tbl = tbl(cfg, "bronze", table_name)

    df = spark.read.parquet(land_vol)
    df = landing_to_bronze(df)
    df = cast_all_to_string(df)

    count, status = safe_append_bronze(spark, df, bronze_tbl, BATCH_ID, RUN_ID)
    log_row_count(spark, OPS_AUDIT, layer="bronze", source_table=source_file,
                  target_table=bronze_tbl, operation=status,
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"  {source_file:<25} → {bronze_tbl:<45} {status} ({count:,} rows)")
    return count

# COMMAND ----------

# ─── Ingest all 6 cross-domain reference files ───────────────────────────────
ingest_to_bronze("Date.txt",       "date")
ingest_to_bronze("Time.txt",       "time")
ingest_to_bronze("StatusType.txt", "statustype")
ingest_to_bronze("TaxRate.txt",    "taxrate")
ingest_to_bronze("Industry.txt",   "industry")
ingest_to_bronze("TradeType.txt",  "tradetype")

print("\n✅ Cross-domain reference bronze ingestion complete.")

# COMMAND ----------

# ─── Quick verification ───────────────────────────────────────────────────────
for name, expected in [("statustype", 6), ("taxrate", 320), ("industry", 102), ("tradetype", 5)]:
    t = tbl(cfg, "bronze", name)
    cnt = spark.sql(f"SELECT COUNT(*) FROM {t}").collect()[0][0]
    ok = "✅" if cnt == expected else "⚠ "
    print(f"  {ok} {name}: {cnt} rows (expected {expected})")
