# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02a — Landing: CONTROL Domain
# Files: BatchDate.txt (all batches)
# Writes to: /Volumes/{catalog}/landing/landing_team_pluto/batch{N}/batchdate/
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

from modules.config_loader import load_config, raw_batch_path, landing_volume_path, apply_spark_conf
from modules.audit_utils import add_landing_audit
from modules.delta_utils import write_landing, landing_already_exists
from modules.operations import log_row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID   = dbutils.widgets.get("batch_id")
RUN_ID     = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
SOURCE_FILE = "BatchDate.txt"
RAW_PATH   = f"{raw_batch_path(cfg, BATCH_ID)}/{SOURCE_FILE}"
LAND_VOL   = landing_volume_path(cfg, BATCH_ID, "batchdate")

if landing_already_exists(spark, LAND_VOL):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")
OPS_AUDIT  = f"{cfg['catalog']['name']}.operations.audit_log"

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")
print(f"Source : {RAW_PATH}")
print(f"Target : {LAND_VOL}")

# COMMAND ----------

from pyspark.sql import functions as F

df = (
    spark.read.text(RAW_PATH)
    .select(F.trim(F.col("value")).alias("batchdate"))
    .withColumn("batchid", F.lit(BATCH_ID))
    .filter(F.col("batchdate") != "")
)
df = add_landing_audit(df, BATCH_ID, SOURCE_FILE, RUN_ID)
df.show(truncate=False)

# COMMAND ----------

count = write_landing(df, LAND_VOL)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=LAND_VOL, operation="OVERWRITE",
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"✅ {SOURCE_FILE} → {LAND_VOL} ({count} row)")
