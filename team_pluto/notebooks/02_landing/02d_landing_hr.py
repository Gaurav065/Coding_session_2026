# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02d — Landing: HR/BROKER Domain
# Files: HR.csv — B1 only
# Writes to: catalog.landing.hr
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
import modules.schema_registry as SR

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID = dbutils.widgets.get("batch_id")
RUN_ID   = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = f"{cfg['catalog']['name']}.operations.audit_log"

if BATCH_ID != "1":
    print(f"Batch {BATCH_ID}: HR.csv is Batch 1 only — skipping.")
    dbutils.notebook.exit("SKIPPED")

if landing_already_exists(spark, landing_volume_path(cfg, BATCH_ID, "hr")):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")

SOURCE_FILE = "HR.csv"
raw_path    = f"{raw_batch_path(cfg, BATCH_ID)}/{SOURCE_FILE}"
lvol        = landing_volume_path(cfg, BATCH_ID, "hr")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")
print(f"Source : {raw_path}")
print(f"Target : {lvol}")

# COMMAND ----------

df = (
    spark.read
    .option("delimiter", ",").option("header", "false").option("nullValue", "")
    .schema(SR.HR)
    .csv(raw_path)
)
df = add_landing_audit(df, BATCH_ID, SOURCE_FILE, RUN_ID)

count = write_landing(df, lvol)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol, operation="OVERWRITE",
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"✅ HR.csv → {lvol} ({count:,} rows)")