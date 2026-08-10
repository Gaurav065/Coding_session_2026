# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02f — Landing: ACCOUNT Domain
# Files:
#   Account.txt         — B2/B3 only, 8 fields pipe-delimited
#   CashTransaction.txt — all batches; B1=4 cols, B2/B3=6 cols (normalized)
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

BATCH_ID = dbutils.widgets.get("batch_id")
RUN_ID = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
BATCH_PATH = raw_batch_path(cfg, BATCH_ID)
OPS_AUDIT = f"{cfg['catalog']['name']}.operations.audit_log"

if landing_already_exists(spark, landing_volume_path(cfg, BATCH_ID, "cashtransaction")):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Account.txt — B2/B3 only
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID in ("2", "3"):
    SOURCE_FILE = "Account.txt"
    raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
    lvol_acct = landing_volume_path(cfg, BATCH_ID, "account")

    df_acct = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .option("nullValue", "")
        .schema(SR.ACCOUNT)
        .csv(raw_path)
    )
    df_acct = add_landing_audit(df_acct, BATCH_ID, SOURCE_FILE, RUN_ID)
    count = write_landing(df_acct, lvol_acct)
    log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
                  target_table=lvol_acct, operation="OVERWRITE", rows_affected=count,
                  batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"Account.txt (B{BATCH_ID}): {count:,} rows")
else:
    print("Account.txt: B2/B3 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CashTransaction.txt — all batches
# B1: 4 data cols → normalize by adding CDC_FLAG='I', CDC_DSN=NULL
# B2/B3: 6 cols (CDC prefix already present, all I=Insert)
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_FILE = "CashTransaction.txt"
raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
lvol_ct = landing_volume_path(cfg, BATCH_ID, "cashtransaction")

if BATCH_ID == "1":
    df_ct = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.CASHTRANSACTION_B1)
        .csv(raw_path)
    )
    df_ct = (
        df_ct
        .withColumn("CDC_FLAG", F.lit("I"))
        .withColumn("CDC_DSN", F.lit(None).cast("string"))
        .select("CT_CA_ID", "CT_DTS", "CT_AMT", "CT_NAME", "CDC_FLAG", "CDC_DSN")
    )
else:
    df_ct = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.CASHTRANSACTION_B2B3)
        .csv(raw_path)
        .select("CT_CA_ID", "CT_DTS", "CT_AMT", "CT_NAME", "CDC_FLAG", "CDC_DSN")
    )

df_ct = add_landing_audit(df_ct, BATCH_ID, SOURCE_FILE, RUN_ID)
count = write_landing(df_ct, lvol_ct)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol_ct, operation="OVERWRITE", rows_affected=count,
              batch_id=BATCH_ID, run_id=RUN_ID)
print(f"CashTransaction (B{BATCH_ID}): {count:,} rows")

print("\n✅ Account domain landing complete.")
