# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03g — Bronze: TRADE Domain
# Tables:
#   bronze.trade          — all batches (normalized 16-col schema)
#   bronze.tradehistory   — B1 only (3 cols, 3.27M rows)
#   bronze.holdinghistory — all batches (normalized 6-col schema)
#
# Performance notes:
#   Trade B1:        1.3M rows  → repartition(22)
#   TradeHistory B1: 3.27M rows → repartition(50)
#   HoldingHistory B1: 1.2M rows → repartition(20)
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

# ═══════════════════════════════════════════════════════════════════════════════
# Trade.txt → bronze.trade — all batches
# ═══════════════════════════════════════════════════════════════════════════════
land_trade = landing_volume_path(cfg, BATCH_ID, "trade")
btbl_trade = tbl(cfg, "bronze", "trade")

df_trade = spark.read.parquet(land_trade)
df_trade = landing_to_bronze(df_trade)
df_trade = cast_all_to_string(df_trade)

if BATCH_ID == "1":
    df_trade = df_trade.repartition(22)  # ~59K rows per partition

count, status = safe_append_bronze(spark, df_trade, btbl_trade, BATCH_ID, RUN_ID)
log_row_count(spark, OPS_AUDIT, layer="bronze", source_table="Trade.txt",
              target_table=btbl_trade, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"Trade.txt (B{BATCH_ID}) → {btbl_trade}: {status} ({count:,} rows)")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# TradeHistory.txt → bronze.tradehistory — B1 only, 3.27M rows
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID == "1":
    land_th = landing_volume_path(cfg, BATCH_ID, "tradehistory")
    btbl_th = tbl(cfg, "bronze", "tradehistory")

    df_th = spark.read.parquet(land_th)
    df_th = landing_to_bronze(df_th)
    df_th = cast_all_to_string(df_th)
    df_th = df_th.repartition(50)   # ~65K rows per partition for 3.27M rows

    count, status = safe_append_bronze(spark, df_th, btbl_th, BATCH_ID, RUN_ID)
    log_row_count(spark, OPS_AUDIT, layer="bronze", source_table="TradeHistory.txt",
                  target_table=btbl_th, operation=status,
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"TradeHistory.txt (B{BATCH_ID}) → {btbl_th}: {status} ({count:,} rows)")
else:
    print("TradeHistory.txt: B1 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# HoldingHistory.txt → bronze.holdinghistory — all batches
# ═══════════════════════════════════════════════════════════════════════════════
land_hh = landing_volume_path(cfg, BATCH_ID, "holdinghistory")
btbl_hh = tbl(cfg, "bronze", "holdinghistory")

df_hh = spark.read.parquet(land_hh)
df_hh = landing_to_bronze(df_hh)
df_hh = cast_all_to_string(df_hh)

if BATCH_ID == "1":
    df_hh = df_hh.repartition(20)   # ~60K rows per partition for 1.2M rows

count, status = safe_append_bronze(spark, df_hh, btbl_hh, BATCH_ID, RUN_ID)
log_row_count(spark, OPS_AUDIT, layer="bronze", source_table="HoldingHistory.txt",
              target_table=btbl_hh, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"HoldingHistory (B{BATCH_ID}) → {btbl_hh}: {status} ({count:,} rows)")

# COMMAND ----------

# ─── Verify cumulative counts ────────────────────────────────────────────────
for table_name, exp_b1, exp_total, label in [
    ("trade",          1_300_824, 1_304_387, "Trade"),
    ("tradehistory",   3_267_433, 3_267_433, "TradeHistory"),
    ("holdinghistory", 1_205_282, 1_206_578, "HoldingHistory"),
]:
    t = tbl(cfg, "bronze", table_name)
    if spark.catalog.tableExists(t.split(".")[-1], t.split(".")[0] if "." in t else None):
        total = spark.sql(f"SELECT COUNT(*) FROM {t}").collect()[0][0]
        print(f"{label}: {total:,} rows cumulative")

print("\n✅ Trade domain bronze ingestion complete.")
