# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02c — Landing: MARKET Domain
# Files: FINWIRE (B1, 203 files as raw text), DailyMarket.txt (all batches)
# Writes to: /Volumes/{catalog}/landing/landing_team_pluto/batch{N}/{finwire|dailymarket}/
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
from pyspark.sql import functions as F

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID   = dbutils.widgets.get("batch_id")
RUN_ID     = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
BATCH_PATH = raw_batch_path(cfg, BATCH_ID)
OPS_AUDIT  = f"{cfg['catalog']['name']}.operations.audit_log"

if landing_already_exists(spark, landing_volume_path(cfg, BATCH_ID, "dailymarket")):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ═══════════════════════════════════════════
# FINWIRE — B1 only, 203 files as raw text
# ═══════════════════════════════════════════
if BATCH_ID == "1":
    SOURCE_FILE = "FINWIRE"
    lvol_fw = landing_volume_path(cfg, BATCH_ID, "finwire")

    df_fw = (
        spark.read
        .text(f"{BATCH_PATH}/FINWIRE*")
        .withColumnRenamed("value", "line")
        .filter(F.col("line") != "")
    )
    df_fw = add_landing_audit(df_fw, BATCH_ID, SOURCE_FILE, RUN_ID)

    count = write_landing(df_fw, lvol_fw)
    log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
                  target_table=lvol_fw, operation="OVERWRITE",
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"FINWIRE: {count:,} lines → {lvol_fw}")
else:
    print("FINWIRE: Batch 1 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════
# DailyMarket.txt — all batches
# B1: 6 data cols → normalize (add DM_ACTION='I', DM_RECID=NULL)
# B2/B3: 8 cols (DM_ACTION + DM_RECID already present)
# ═══════════════════════════════════════════
SOURCE_FILE = "DailyMarket.txt"
raw_path    = f"{BATCH_PATH}/{SOURCE_FILE}"
lvol_dm     = landing_volume_path(cfg, BATCH_ID, "dailymarket")

if BATCH_ID == "1":
    df_dm = (
        spark.read
        .option("delimiter", "|").option("header", "false")
        .schema(SR.DAILYMARKET_B1)
        .csv(raw_path)
        .withColumn("DM_ACTION", F.lit("I"))
        .withColumn("DM_RECID",  F.lit(None).cast("string"))
        .select("DM_DATE","DM_S_SYMB","DM_CLOSE","DM_HIGH","DM_LOW","DM_VOL","DM_ACTION","DM_RECID")
    )
else:
    df_dm = (
        spark.read
        .option("delimiter", "|").option("header", "false")
        .schema(SR.DAILYMARKET_B2B3)
        .csv(raw_path)
        .select("DM_DATE","DM_S_SYMB","DM_CLOSE","DM_HIGH","DM_LOW","DM_VOL","DM_ACTION","DM_RECID")
    )

df_dm = add_landing_audit(df_dm, BATCH_ID, SOURCE_FILE, RUN_ID)
count = write_landing(df_dm, lvol_dm)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol_dm, operation="OVERWRITE",
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"DailyMarket (B{BATCH_ID}): {count:,} rows → {lvol_dm}")
