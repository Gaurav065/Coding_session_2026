# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05a — Gold: REFERENCE Domain
# Tables: gold.industry, gold.status_type, gold.tax_rate, gold.trade_type
# Pattern: Silver → rename columns → add gold audit → CORT
# Batch scope: B1 ONLY (static reference data, loaded once)
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'): del sys.modules[_k]
sys.path.insert(0, _root)

from pyspark.sql import functions as F

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import add_gold_audit
from modules.delta_utils import create_or_replace_table
from modules.operations import log_row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")

BATCH_ID  = dbutils.widgets.get("batch_id")
RUN_ID    = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
OPS_AUDIT = tbl(cfg, "operations", "audit_log")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

# ─── B1-only guard ────────────────────────────────────────────────────────────
if BATCH_ID != "1":
    print("Reference tables are B1-only — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.industry
# Source : silver.industry
# Columns: IndustryID, IndustryName, SC_ID
# ═══════════════════════════════════════════════════════════════════════════════
src_in = tbl(cfg, "silver", "industry")
tgt_in = tbl(cfg, "gold",   "industry")

df_in = (
    spark.table(src_in)
    .select(
        F.col("IN_ID").alias("IndustryID"),
        F.col("IN_NAME").alias("IndustryName"),
        F.col("IN_SC_ID").alias("SC_ID"),
    )
)
df_in = add_gold_audit(df_in, BATCH_ID, RUN_ID)

count_in = create_or_replace_table(df_in, tgt_in)
print(f"gold.industry: {count_in:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_in,
              target_table=tgt_in, operation="OVERWRITE",
              rows_affected=count_in, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.status_type
# Source : silver.statustype
# Columns: StatusType, Status
# ═══════════════════════════════════════════════════════════════════════════════
src_st = tbl(cfg, "silver", "statustype")
tgt_st = tbl(cfg, "gold",   "status_type")

df_st = (
    spark.table(src_st)
    .select(
        F.col("ST_ID").alias("StatusType"),
        F.col("ST_NAME").alias("Status"),
    )
)
df_st = add_gold_audit(df_st, BATCH_ID, RUN_ID)

count_st = create_or_replace_table(df_st, tgt_st)
print(f"gold.status_type: {count_st:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_st,
              target_table=tgt_st, operation="OVERWRITE",
              rows_affected=count_st, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.tax_rate
# Source : silver.taxrate
# Columns: TaxID, TaxName, TaxRate
# ═══════════════════════════════════════════════════════════════════════════════
src_tx = tbl(cfg, "silver", "taxrate")
tgt_tx = tbl(cfg, "gold",   "tax_rate")

df_tx = (
    spark.table(src_tx)
    .select(
        F.col("TX_ID").alias("TaxID"),
        F.col("TX_NAME").alias("TaxName"),
        F.col("TX_RATE").cast("decimal(15,4)").alias("TaxRate"),
    )
)
df_tx = add_gold_audit(df_tx, BATCH_ID, RUN_ID)

count_tx = create_or_replace_table(df_tx, tgt_tx)
print(f"gold.tax_rate: {count_tx:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_tx,
              target_table=tgt_tx, operation="OVERWRITE",
              rows_affected=count_tx, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.trade_type
# Source : silver.tradetype
# Columns: TradeTypeID, TradeType, IsSell, IsMarket
# ═══════════════════════════════════════════════════════════════════════════════
src_tt = tbl(cfg, "silver", "tradetype")
tgt_tt = tbl(cfg, "gold",   "trade_type")

df_tt = (
    spark.table(src_tt)
    .select(
        F.col("TT_ID").alias("TradeTypeID"),
        F.col("TT_NAME").alias("TradeType"),
        F.col("TT_IS_SELL").cast("boolean").alias("IsSell"),
        F.col("TT_IS_MRKT").cast("boolean").alias("IsMarket"),
    )
)
df_tt = add_gold_audit(df_tt, BATCH_ID, RUN_ID)

count_tt = create_or_replace_table(df_tt, tgt_tt)
print(f"gold.trade_type: {count_tt:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_tt,
              target_table=tgt_tt, operation="OVERWRITE",
              rows_affected=count_tt, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nReference gold complete — B1 only.")
print(f"  gold.industry   : {count_in:,} rows")
print(f"  gold.status_type: {count_st:,} rows")
print(f"  gold.tax_rate   : {count_tx:,} rows")
print(f"  gold.trade_type : {count_tt:,} rows")
