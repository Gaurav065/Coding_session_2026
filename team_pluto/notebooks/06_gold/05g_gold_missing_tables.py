# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05g — Gold: Missing Tables (Prospect, Financial, Cash Transactions, Trade History)
# Tables: gold.dim_prospect, gold.financial, gold.fact_cash_transactions, gold.fact_trade_history
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
from modules.delta_utils import create_or_replace_table, overwrite_table
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

# ═══════════════════════════════════════════════════════════════════════════════
# 1. gold.dim_prospect (Full Refresh / INSERT OVERWRITE)
# Source: staging.prospect_current
# ═══════════════════════════════════════════════════════════════════════════════
src_pros = tbl(cfg, "staging", "prospect_current")
tgt_cust = tbl(cfg, "gold", "dim_customer")
tgt_date = tbl(cfg, "gold", "dim_date")
tgt_pros = tbl(cfg, "gold", "dim_prospect")

df_pros = spark.table(src_pros)

# IsCustomer Match: 5-column match against active customers
df_cust = spark.table(tgt_cust).filter(F.col("IsCurrent") == True).select(
    F.upper(F.col("LastName")).alias("c_ln"),
    F.upper(F.col("FirstName")).alias("c_fn"),
    F.upper(F.col("AddressLine1")).alias("c_add1"),
    F.upper(F.col("AddressLine2")).alias("c_add2"),
    F.upper(F.col("PostalCode")).alias("c_zip")
).dropDuplicates()

# Marketing Nameplate Derivation (TPC-DI Business Rules)
nameplate_expr = F.concat_ws("+", 
    F.when((F.col("networth") > 1000000) | (F.col("income") > 200000), F.lit("HighValue")).otherwise(F.lit("")),
    F.when((F.col("numberchildren") > 3) | (F.col("numbercreditcards") > 5), F.lit("Expenses")).otherwise(F.lit("")),
    F.when(F.col("age") > 45, F.lit("Boomer")).otherwise(F.lit("")),
    F.when((F.col("income") < 50000) | (F.col("creditrating") < 600), F.lit("MoneyAlert")).otherwise(F.lit("")),
    F.when((F.col("numbercars") > 3) | (F.col("numbercreditcards") > 7), F.lit("Spender")).otherwise(F.lit("")),
    F.when((F.col("age") < 25) & (F.col("networth") > 1000000), F.lit("Inherited")).otherwise(F.lit(""))
)
# Clean up '+' from concatenation
nameplate_expr = F.when(nameplate_expr == "", F.lit(None)).otherwise(F.regexp_replace(nameplate_expr, r"^\++|\++$", "")) 

df_dim_prospect = (
    df_pros
    .join(df_cust, 
          (F.upper(df_pros["lastname"]) == df_cust["c_ln"]) &
          (F.upper(df_pros["firstname"]) == df_cust["c_fn"]) &
          (F.upper(df_pros["addressline1"]) == df_cust["c_add1"]) &
          (F.coalesce(F.upper(df_pros["addressline2"]), F.lit("")) == F.coalesce(df_cust["c_add2"], F.lit(""))) &
          (F.upper(df_pros["postalcode"]) == df_cust["c_zip"]),
          "left"
    )
    .select(
        F.col("agencyid").alias("AgencyID"),
        F.lit(-1).cast("bigint").alias("SK_RecordDateID"), # Can be enhanced with batch_date resolution
        F.lit(-1).cast("bigint").alias("SK_UpdateDateID"),
        F.col("first_batchid").cast("int").alias("BatchID"),
        F.col("c_ln").isNotNull().alias("IsCustomer"), # True if match found
        F.col("lastname").alias("LastName"),
        F.col("firstname").alias("FirstName"),
        F.col("middleinitial").alias("MiddleInitial"),
        F.col("gender").alias("Gender"),
        F.col("addressline1").alias("AddressLine1"),
        F.col("addressline2").alias("AddressLine2"),
        F.col("postalcode").alias("PostalCode"),
        F.col("city").alias("City"),
        F.col("state").alias("State"),
        F.col("country").alias("Country"),
        F.col("phone").alias("Phone"),
        F.col("income").cast("decimal(15,2)").alias("Income"),
        F.col("numbercars").cast("int").alias("NumberCars"),
        F.col("numberchildren").cast("int").alias("NumberChildren"),
        F.col("maritalstatus").alias("MaritalStatus"),
        F.col("age").cast("int").alias("Age"),
        F.col("creditrating").cast("int").alias("CreditRating"),
        F.col("ownorrentflag").alias("OwnOrRentFlag"),
        F.col("employer").alias("Employer"),
        F.col("numbercreditcards").cast("int").alias("NumberCreditCards"),
        F.col("networth").cast("decimal(15,2)").alias("NetWorth"),
        nameplate_expr.alias("MarketingNameplate")
    )
)
df_dim_prospect = add_gold_audit(df_dim_prospect, BATCH_ID, RUN_ID)

# OVERWRITE pattern as dictated by the Full Refresh CDC rule
count_pros = overwrite_table(df_dim_prospect, tgt_pros)
print(f"gold.dim_prospect: {count_pros:,} rows (INSERT OVERWRITE)")
log_row_count(spark, OPS_AUDIT, "gold", src_pros, tgt_pros, "OVERWRITE", count_pros, BATCH_ID, RUN_ID)


# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 2. gold.financial 
# Source: staging.finwire_parsed (FIN records) -> Temporal Join to dim_company
# ═══════════════════════════════════════════════════════════════════════════════
src_fin = tbl(cfg, "staging", "finwire_parsed")
tgt_comp = tbl(cfg, "gold", "dim_company")
tgt_fin = tbl(cfg, "gold", "financial")

if BATCH_ID == "1":
    df_fin = spark.table(src_fin).filter(F.col("rec_type").isin("FIN_COMPANYID", "FIN_NAME"))
    
    df_gco = spark.table(tgt_comp).select("SK_CompanyID", "CompanyID", "Name", "EffectiveDate", "EndDate")
    
    # Match on CIK
    df_c1 = F.broadcast(df_gco.select(
        F.col("SK_CompanyID").alias("_sk_cik"),
        F.col("CompanyID").cast("string").alias("_co_id_str"),
        F.col("EffectiveDate").alias("_co_eff1"),
        F.col("EndDate").alias("_co_end1")
    ))
    
    # Match on Name
    df_c2 = F.broadcast(df_gco.select(
        F.col("SK_CompanyID").alias("_sk_name"),
        F.col("Name").alias("_co_name"),
        F.col("EffectiveDate").alias("_co_eff2"),
        F.col("EndDate").alias("_co_end2")
    ))

    df_financial = (
        df_fin
        .join(
            df_c1,
            (F.trim(df_fin["co_name_or_cik"]) == df_c1["_co_id_str"]) & 
            (df_fin["effective_date"] >= df_c1["_co_eff1"]) & 
            (df_fin["effective_date"] < df_c1["_co_end1"]),
            "left"
        )
        .join(
            df_c2,
            (F.trim(df_fin["co_name_or_cik"]) == F.trim(df_c2["_co_name"])) & 
            (df_fin["effective_date"] >= df_c2["_co_eff2"]) & 
            (df_fin["effective_date"] < df_c2["_co_end2"]),
            "left"
        )
        .select(
            F.coalesce(F.col("_sk_cik"), F.col("_sk_name"), F.lit(-1).cast("bigint")).alias("SK_CompanyID"),
            F.col("fi_year").cast("int").alias("FI_YEAR"),
            F.col("fi_qtr").cast("int").alias("FI_QTR"),
            F.col("fi_qtr_start_date").cast("date").alias("FI_QTR_START_DATE"),
            F.col("fi_revenue").cast("decimal(15,2)").alias("FI_REVENUE"),
            F.col("fi_net_earn").cast("decimal(15,2)").alias("FI_NET_EARN"),
            F.col("fi_basic_eps").cast("decimal(10,2)").alias("FI_BASIC_EPS"),
            F.col("fi_dilut_eps").cast("decimal(10,2)").alias("FI_DILUT_EPS"),
            F.col("fi_margin").cast("decimal(10,2)").alias("FI_MARGIN"),
            F.col("fi_inventory").cast("decimal(15,2)").alias("FI_INVENTORY"),
            F.col("fi_assets").cast("decimal(15,2)").alias("FI_ASSETS"),
            F.col("fi_liability").cast("decimal(15,2)").alias("FI_LIABILITY"),
            F.col("fi_out_basic").cast("bigint").alias("FI_OUT_BASIC"),
            F.col("fi_out_dilut").cast("bigint").alias("FI_OUT_DILUT")
        )
    )
    df_financial = add_gold_audit(df_financial, BATCH_ID, RUN_ID)
    
    count_fin = create_or_replace_table(df_financial, tgt_fin)
    print(f"gold.financial: {count_fin:,} rows")
    log_row_count(spark, OPS_AUDIT, "gold", src_fin, tgt_fin, "OVERWRITE", count_fin, BATCH_ID, RUN_ID)
else:
    print(f"gold.financial is B1-only — SKIPPED for batch {BATCH_ID}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 3. gold.fact_cash_transactions
# Source: bronze.cashtransaction (Direct Cast Refined Star Schema)
# ═══════════════════════════════════════════════════════════════════════════════
src_ct = tbl(cfg, "bronze", "cashtransaction")
tgt_fct = tbl(cfg, "gold", "fact_cash_transactions")

df_ct = spark.table(src_ct)

df_fact_cash_transactions = (
    df_ct
    .select(
        F.col("CT_CA_ID").cast("bigint").alias("SK_AccountID"),
        F.to_timestamp(F.col("CT_DTS")).alias("TransactionDatetime"),
        F.col("CT_AMT").cast("decimal(12,2)").alias("Amount"),
        F.col("CT_NAME").alias("Description")
    )
)
df_fact_cash_transactions = add_gold_audit(df_fact_cash_transactions, BATCH_ID, RUN_ID)

count_fct = create_or_replace_table(df_fact_cash_transactions, tgt_fct)
print(f"gold.fact_cash_transactions: {count_fct:,} rows")
log_row_count(spark, OPS_AUDIT, "gold", src_ct, tgt_fct, "OVERWRITE", count_fct, BATCH_ID, RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# 4. gold.fact_trade_history
# Source: bronze.tradehistory (Direct Cast Refined Star Schema)
# ═══════════════════════════════════════════════════════════════════════════════
src_th = tbl(cfg, "bronze", "tradehistory")
tgt_fth = tbl(cfg, "gold", "fact_trade_history")

df_th = spark.table(src_th)

df_fact_trade_history = (
    df_th
    .select(
        F.col("TH_T_ID").cast("bigint").alias("SK_TradeID"),
        F.to_timestamp(F.col("TH_DTS")).alias("StatusDatetime"),
        F.col("TH_ST_ID").alias("StatusCode")
    )
)
df_fact_trade_history = add_gold_audit(df_fact_trade_history, BATCH_ID, RUN_ID)

count_fth = create_or_replace_table(df_fact_trade_history, tgt_fth)
print(f"gold.fact_trade_history: {count_fth:,} rows")
log_row_count(spark, OPS_AUDIT, "gold", src_th, tgt_fth, "OVERWRITE", count_fth, BATCH_ID, RUN_ID)

# COMMAND ----------

print(f"\nMissing Gold Tables complete.")