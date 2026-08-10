# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02g — Landing: TRADE Domain
# Files:
#   Trade.txt          — all batches; B1=14 cols, B2/B3=16 cols (normalized)
#   TradeHistory.txt   — B1 only, 3 fields
#   HoldingHistory.txt — all batches; B1=4 cols, B2/B3=6 cols (normalized)
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

if landing_already_exists(spark, landing_volume_path(cfg, BATCH_ID, "trade")):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Trade.txt — all batches
# B1: 14 data cols, no CDC prefix → normalize by adding CDC_FLAG='I', CDC_DSN=NULL
# B2/B3: 16 cols (CDC_FLAG + CDC_DSN prefix + 14 data cols)
# Performance: B1 has 1.3M rows — use explicit schema, AQE handles partitions.
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_FILE = "Trade.txt"
raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
lvol_trade = landing_volume_path(cfg, BATCH_ID, "trade")

DATA_COLS = list(SR.TRADE_DATA_COLS)

if BATCH_ID == "1":
    df_trade = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .option("nullValue", "")
        .schema(SR.TRADE_B1)
        .csv(raw_path)
    )
    df_trade = (
        df_trade
        .withColumn("CDC_FLAG", F.lit("I"))
        .withColumn("CDC_DSN", F.lit(None).cast("string"))
        .select(*DATA_COLS, "CDC_FLAG", "CDC_DSN")
    )
else:
    df_trade = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .option("nullValue", "")
        .schema(SR.TRADE_B2B3)
        .csv(raw_path)
        .select(*DATA_COLS, "CDC_FLAG", "CDC_DSN")
    )

df_trade = add_landing_audit(df_trade, BATCH_ID, SOURCE_FILE, RUN_ID)
count = write_landing(df_trade, lvol_trade)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol_trade, operation="OVERWRITE", rows_affected=count,
              batch_id=BATCH_ID, run_id=RUN_ID)
print(f"Trade.txt (B{BATCH_ID}): {count:,} rows")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# TradeHistory.txt — B1 only, 3 fields, ~3.27M rows
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID == "1":
    SOURCE_FILE = "TradeHistory.txt"
    raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
    lvol_th = landing_volume_path(cfg, BATCH_ID, "tradehistory")

    df_th = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.TRADEHISTORY)
        .csv(raw_path)
    )
    df_th = add_landing_audit(df_th, BATCH_ID, SOURCE_FILE, RUN_ID)
    count = write_landing(df_th, lvol_th)
    log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
                  target_table=lvol_th, operation="OVERWRITE", rows_affected=count,
                  batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"TradeHistory.txt (B{BATCH_ID}): {count:,} rows")
else:
    print("TradeHistory.txt: Batch 1 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# HoldingHistory.txt — all batches
# B1: 4 data cols → normalize
# B2/B3: 6 cols (CDC prefix, all I=Insert)
# Performance: B1 has 1.2M rows — explicit schema
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_FILE = "HoldingHistory.txt"
raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
lvol_hh = landing_volume_path(cfg, BATCH_ID, "holdinghistory")

if BATCH_ID == "1":
    df_hh = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.HOLDINGHISTORY_B1)
        .csv(raw_path)
    )
    df_hh = (
        df_hh
        .withColumn("CDC_FLAG", F.lit("I"))
        .withColumn("CDC_DSN", F.lit(None).cast("string"))
        .select("HH_H_T_ID", "HH_T_ID", "HH_BEFORE_QTY", "HH_AFTER_QTY", "CDC_FLAG", "CDC_DSN")
    )
else:
    df_hh = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.HOLDINGHISTORY_B2B3)
        .csv(raw_path)
        .select("HH_H_T_ID", "HH_T_ID", "HH_BEFORE_QTY", "HH_AFTER_QTY", "CDC_FLAG", "CDC_DSN")
    )

df_hh = add_landing_audit(df_hh, BATCH_ID, SOURCE_FILE, RUN_ID)
count = write_landing(df_hh, lvol_hh)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol_hh, operation="OVERWRITE", rows_affected=count,
              batch_id=BATCH_ID, run_id=RUN_ID)
print(f"HoldingHistory (B{BATCH_ID}): {count:,} rows")

print("\n✅ Trade domain landing complete.")
