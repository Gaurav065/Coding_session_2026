# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02b — Landing: CROSS-DOMAIN REFERENCE Domain
# Files: Date.txt, Time.txt, StatusType.txt, TaxRate.txt, Industry.txt,
#        TradeType.txt — all Batch 1 ONLY
# Writes to: /Volumes/{catalog}/landing/landing_team_pluto/batch1/{date|time|statustype|taxrate|industry|tradetype}/
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

BATCH_ID  = dbutils.widgets.get("batch_id")
RUN_ID    = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = f"{cfg['catalog']['name']}.operations.audit_log"

if BATCH_ID != "1":
    print(f"Batch {BATCH_ID}: cross-domain reference files are Batch 1 only — skipping.")
    dbutils.notebook.exit("SKIPPED")

if landing_already_exists(spark, landing_volume_path(cfg, BATCH_ID, "date")):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")

B1_PATH = raw_batch_path(cfg, BATCH_ID)
print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

from pyspark.sql.types import StructType

def land_file(source_file: str, table_name: str, schema: StructType, has_header: bool) -> int:
    raw_path = f"{B1_PATH}/{source_file}"
    lvol     = landing_volume_path(cfg, BATCH_ID, table_name)

    df = (
        spark.read
        .option("delimiter", "|")
        .option("header", str(has_header).lower())
        .option("nullValue", "")
        .schema(schema)
        .csv(raw_path)
    )
    df = add_landing_audit(df, BATCH_ID, source_file, RUN_ID)
    count = write_landing(df, lvol)
    log_row_count(spark, OPS_AUDIT, layer="landing", source_table=source_file,
                  target_table=lvol, operation="OVERWRITE",
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"  {source_file:<25} → {lvol}  ({count:,} rows)")
    return count

# COMMAND ----------

land_file("Date.txt",       "date",       SR.DATE,       has_header=True)
land_file("Time.txt",       "time",       SR.TIME,       has_header=True)
land_file("StatusType.txt", "statustype", SR.STATUSTYPE, has_header=False)
land_file("TaxRate.txt",    "taxrate",    SR.TAXRATE,    has_header=False)
land_file("Industry.txt",   "industry",   SR.INDUSTRY,   has_header=False)
land_file("TradeType.txt",  "tradetype",  SR.TRADETYPE,  has_header=False)

print("\n✅ Cross-domain reference landing complete.")
