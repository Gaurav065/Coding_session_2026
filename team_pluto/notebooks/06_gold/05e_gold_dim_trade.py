# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05e — Gold: DimTrade
# Table : gold.dim_trade
# Pattern: silver.trade → join dim_account, dim_security, statustype,
#           tradetype, dim_date (create/close), dim_time (create/close) → CORT
#          *TEMPORAL POINT-IN-TIME JOINS FOR SCD-2 DIMENSIONS*
# Batch scope: all batches
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

src_trade  = tbl(cfg, "silver", "trade")
src_st     = tbl(cfg, "silver", "statustype")
src_tt     = tbl(cfg, "silver", "tradetype")
tgt_trade  = tbl(cfg, "gold",   "dim_trade")

tgt_acct   = tbl(cfg, "gold", "dim_account")
tgt_cust   = tbl(cfg, "gold", "dim_customer")
tgt_sec    = tbl(cfg, "gold", "dim_security")
tgt_comp   = tbl(cfg, "gold", "dim_company")
tgt_date   = tbl(cfg, "gold", "dim_date")
tgt_time   = tbl(cfg, "gold", "dim_time")
tgt_brk    = tbl(cfg, "gold", "dim_broker")

# COMMAND ----------

df_trade = spark.table(src_trade)

df_st = F.broadcast(spark.table(src_st).select(
    F.col("ST_ID").alias("_st_id"),
    F.col("ST_NAME").alias("_st_name"),
))

df_tt = F.broadcast(spark.table(src_tt).select(
    F.col("TT_ID").alias("_tt_id"),
    F.col("TT_NAME").alias("_tt_name"),
    F.col("TT_IS_MRKT").cast("boolean").alias("_tt_is_mrkt"),
))

df_cust = spark.table(tgt_cust).select(
    F.col("CustomerID").alias("_cust_id"),
    F.col("SK_CustomerID").alias("_sk_cust_id"),
    F.col("EffectiveDate").alias("_cust_eff"),
    F.col("EndDate").alias("_cust_end")
)

df_acct = spark.table(tgt_acct).select(
    F.col("AccountID").alias("_acct_id"),
    F.col("SK_AccountID").alias("_sk_acct_id"),
    F.col("SK_CustomerID").alias("_acct_sk_cust_id"),
    F.col("SK_BrokerID").alias("_acct_sk_brk_id"),
    F.col("EffectiveDate").alias("_acct_eff"),
    F.col("EndDate").alias("_acct_end")
)

df_sec = spark.table(tgt_sec).select(
    F.col("Symbol").alias("_sec_symbol"),
    F.col("SK_SecurityID").alias("_sk_sec_id"),
    F.col("SK_CompanyID").alias("_sec_sk_co_id"),
    F.col("EffectiveDate").alias("_sec_eff"),
    F.col("EndDate").alias("_sec_end")
)

df_brk = F.broadcast(spark.table(tgt_brk).select(
    F.col("BrokerID").alias("_brk_id"),
    F.col("SK_BrokerID").alias("_sk_brk_id"),
    F.concat_ws(" ", F.col("FirstName"), F.col("LastName")).alias("_brk_name1"),
    F.concat_ws(" ", F.col("FirstName"), F.col("MiddleInitial"), F.col("LastName")).alias("_brk_name2")
))

_df_date_base = spark.table(tgt_date).select(
    F.col("DateValue").alias("_date_val"),
    F.col("SK_DateID").alias("_sk_date_id"),
).cache()
_df_date_base.count()

_df_time_base = spark.table(tgt_time).select(
    F.col("TimeValue").alias("_time_val"),
    F.col("SK_TimeID").alias("_sk_time_id"),
).cache()
_df_time_base.count()

# COMMAND ----------

df_trade = (
    df_trade
    .withColumn("_open_date", F.to_date(F.col("opened_dts")))
    .withColumn("_open_time", F.date_format(F.col("opened_dts"), "HH:mm:ss"))
    .withColumn("_close_date", F.to_date(F.col("closed_dts")))
    .withColumn("_close_time", F.date_format(F.col("closed_dts"), "HH:mm:ss"))
    .withColumn("_trade_date", F.to_date(F.col("opened_dts")))
)

# COMMAND ----------

df_date_open  = F.broadcast(_df_date_base.select(
    F.col("_date_val").alias("_open_date_val"),
    F.col("_sk_date_id").alias("_sk_open_date_id"),
))
df_time_open  = F.broadcast(_df_time_base.select(
    F.col("_time_val").alias("_open_time_val"),
    F.col("_sk_time_id").alias("_sk_open_time_id"),
))
df_date_close = F.broadcast(_df_date_base.select(
    F.col("_date_val").alias("_close_date_val"),
    F.col("_sk_date_id").alias("_sk_close_date_id"),
))
df_time_close = F.broadcast(_df_time_base.select(
    F.col("_time_val").alias("_close_time_val"),
    F.col("_sk_time_id").alias("_sk_close_time_id"),
))

df_dim_trade = (
    df_trade
    .join(df_st, df_trade["T_ST_ID"] == df_st["_st_id"], "left")
    .join(df_tt, df_trade["T_TT_ID"] == df_tt["_tt_id"], "left")
    
    # 1. Temporal Join to Account
    .join(
        df_acct, 
        (df_trade["T_CA_ID"].cast("bigint") == df_acct["_acct_id"]) &
        (df_trade["_trade_date"] >= df_acct["_acct_eff"]) &
        (df_trade["_trade_date"] < df_acct["_acct_end"]),
        "left"
    )
    
    # 2. Temporal Join to Security
    .join(
        df_sec, 
        (df_trade["T_S_SYMB"] == df_sec["_sec_symbol"]) &
        (df_trade["_trade_date"] >= df_sec["_sec_eff"]) &
        (df_trade["_trade_date"] < df_sec["_sec_end"]),
        "left"
    )
    
    # 3. Join to Broker (By name, fallback to account cascade)
    .join(
        df_brk,
        (F.trim(df_trade["T_EXEC_NAME"]) == F.trim(df_brk["_brk_name1"])) |
        (F.trim(df_trade["T_EXEC_NAME"]) == F.trim(df_brk["_brk_name2"])),
        "left"
    )
    
    .join(df_date_open,  df_trade["_open_date"]  == df_date_open["_open_date_val"],   "left")
    .join(df_time_open,  df_trade["_open_time"]  == df_time_open["_open_time_val"],   "left")
    .join(df_date_close, df_trade["_close_date"] == df_date_close["_close_date_val"], "left")
    .join(df_time_close, df_trade["_close_time"] == df_time_close["_close_time_val"], "left")
    .select(
        F.col("T_ID").cast("bigint").alias("TradeID"),
        F.coalesce(F.col("_sk_brk_id"), F.col("_acct_sk_brk_id"), F.lit(-1).cast("bigint")).alias("SK_BrokerID"),
        F.coalesce(F.col("_sk_open_date_id"),  F.lit(-1).cast("bigint")).alias("SK_CreateDateID"),
        F.coalesce(F.col("_sk_open_time_id"),  F.lit(-1).cast("bigint")).alias("SK_CreateTimeID"),
        F.col("_sk_close_date_id").alias("SK_CloseDateID"),
        F.col("_sk_close_time_id").alias("SK_CloseTimeID"),
        F.coalesce(F.col("_st_name"),           F.lit("Unknown")).alias("Status"),
        F.coalesce(F.col("_tt_name"),           F.lit("Unknown")).alias("Type"),
        F.col("T_IS_CASH").cast("boolean").alias("CashFlag"),
        F.coalesce(F.col("_sk_sec_id"),         F.lit(-1).cast("bigint")).alias("SK_SecurityID"),
        F.coalesce(F.col("_sec_sk_co_id"),      F.lit(-1).cast("bigint")).alias("SK_CompanyID"),
        F.col("T_QTY").cast("int").alias("Quantity"),
        F.col("T_BID_PRICE").cast("decimal(8,2)").alias("BidPrice"),
        F.coalesce(F.col("_acct_sk_cust_id"),   F.lit(-1).cast("bigint")).alias("SK_CustomerID"),
        F.coalesce(F.col("_sk_acct_id"),        F.lit(-1).cast("bigint")).alias("SK_AccountID"),
        F.col("T_EXEC_NAME").alias("ExecutedBy"),
        F.col("T_TRADE_PRICE").cast("decimal(8,2)").alias("TradePrice"),
        F.col("T_CHRG").cast("decimal(10,2)").alias("Fee"),
        F.col("T_COMM").cast("decimal(10,2)").alias("Commission"),
        F.col("T_TAX").cast("decimal(10,2)").alias("Tax"),
    )
)
df_dim_trade = add_gold_audit(df_dim_trade, BATCH_ID, RUN_ID)

# COMMAND ----------

count_trade = create_or_replace_table(df_dim_trade, tgt_trade)

_df_date_base.unpersist()
_df_time_base.unpersist()

print(f"gold.dim_trade: {count_trade:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_trade,
              target_table=tgt_trade, operation="OVERWRITE",
              rows_affected=count_trade, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nDimTrade gold complete.")
print(f"  gold.dim_trade : {count_trade:,} rows")