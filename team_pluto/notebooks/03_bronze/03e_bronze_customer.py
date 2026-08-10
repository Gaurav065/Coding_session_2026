# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03e — Bronze: CUSTOMER Domain
# Tables:
#   bronze.customermgmt  — B1 only (XML flattened → 37-col wide table)
#   bronze.customer      — B2/B3 only (CDC, 33 cols)
#   bronze.prospect      — all batches (JSON/CSV, 22 cols; APPEND for history)
#   bronze.watchhistory  — all batches (normalized 6-col schema)
#
# IMPORTANT for bronze.prospect:
#   We append ALL batches to preserve history needed for first_batchid computation.
#   Staging layer extracts the current batch for CDC detection.
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

# ─── Generic bronze ingest helper ────────────────────────────────────────────
def to_bronze(source_file: str, table_name: str) -> tuple:
    lvol = landing_volume_path(cfg, BATCH_ID, table_name)
    btbl = tbl(cfg, "bronze", table_name)
    df = spark.read.parquet(lvol)
    df = landing_to_bronze(df)
    df = cast_all_to_string(df)
    count, status = safe_append_bronze(spark, df, btbl, BATCH_ID, RUN_ID)
    log_row_count(spark, OPS_AUDIT, layer="bronze", source_table=source_file,
                  target_table=btbl, operation=status,
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"  {source_file:<28} → {table_name:<20} {status} ({count:,} rows)")
    return count, status

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CustomerMgmt.xml → bronze.customermgmt — B1 only
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID == "1":
    to_bronze("CustomerMgmt.xml", "customermgmt")
else:
    print("CustomerMgmt.xml: B1 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Customer.txt → bronze.customer — B2/B3 only
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID in ("2", "3"):
    to_bronze("Customer.txt", "customer")
else:
    print("Customer.txt: B2/B3 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Prospect.json → bronze.prospect — ALL batches (append history for first_batchid)
# After B3 bronze.prospect has 149,820 rows (3 × 49,940)
# ═══════════════════════════════════════════════════════════════════════════════
to_bronze("Prospect.json", "prospect")

total_prospect = spark.sql(f"SELECT COUNT(*) FROM {tbl(cfg, 'bronze', 'prospect')}").collect()[0][0]
print(f"  → bronze.prospect cumulative total: {total_prospect:,} (expected B1=49940, B1+B2=99880, B1+B2+B3=149820)")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# WatchHistory.txt → bronze.watchhistory — all batches
# B1 has 3M rows — repartition for efficient write
# ═══════════════════════════════════════════════════════════════════════════════
land_wh = landing_volume_path(cfg, BATCH_ID, "watchhistory")
btbl    = tbl(cfg, "bronze", "watchhistory")

df_wh = spark.read.parquet(land_wh)
df_wh = landing_to_bronze(df_wh)
df_wh = cast_all_to_string(df_wh)

if BATCH_ID == "1":
    df_wh = df_wh.repartition(48)   # ~62K rows per partition for 3M rows

count, status = safe_append_bronze(spark, df_wh, btbl, BATCH_ID, RUN_ID)
log_row_count(spark, OPS_AUDIT, layer="bronze", source_table="WatchHistory.txt",
              target_table=btbl, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"  WatchHistory.txt             → watchhistory         {status} ({count:,} rows)")

print("\n✅ Customer domain bronze ingestion complete.")
