# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05d — Gold: DimBroker + DimCustomer (SCD-2) + DimAccount (SCD-2)
# Tables: gold.dim_broker, gold.dim_customer, gold.dim_account
#
# dim_broker    — B1 only (HR file is static, JOB_CODE='314')
#                 SK_BrokerID = EMPLOYEE_ID (natural bigint, stable)
#
# dim_customer  — SCD-2 across all batches (computed in Staging)
#
# dim_account   — SCD-2 across all batches. We compute the timeline here
#                 using the update_ts, and perform temporal joins to dim_customer
#                 to find the exact SK_CustomerID valid at that point in time.
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'): del sys.modules[_k]
sys.path.insert(0, _root)

import warnings
warnings.filterwarnings("ignore", category=UserWarning,
                        message=".*No Partition Defined for Window.*")

from pyspark.sql import functions as F
from pyspark.sql import Window

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

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_broker
# ═══════════════════════════════════════════════════════════════════════════════
src_hr  = tbl(cfg, "silver", "hr")
tgt_brk = tbl(cfg, "gold",   "dim_broker")

if BATCH_ID == "1":
    df_hr = spark.table(src_hr).filter(F.col("JOB_CODE") == "314")

    df_dim_broker = (
        df_hr
        .select(
            F.col("EMPLOYEE_ID").cast("bigint").alias("SK_BrokerID"),
            F.col("EMPLOYEE_ID").cast("bigint").alias("BrokerID"),
            F.col("MANAGER_ID").cast("bigint").alias("ManagerID"),
            F.col("LAST_NAME").alias("LastName"),
            F.col("FIRST_NAME").alias("FirstName"),
            F.col("MIDDLE_INITIAL").alias("MiddleInitial"),
            F.col("BRANCH_ID").alias("Branch"),
            F.col("OFFICE").alias("Office"),
            F.col("PHONE").alias("Phone"),
        )
    )
    df_dim_broker = add_gold_audit(df_dim_broker, BATCH_ID, RUN_ID)

    count_brk = create_or_replace_table(df_dim_broker, tgt_brk)
    print(f"gold.dim_broker: {count_brk:,} rows")

    log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_hr,
                  target_table=tgt_brk, operation="OVERWRITE",
                  rows_affected=count_brk, batch_id=BATCH_ID, run_id=RUN_ID)
else:
    print("dim_broker is B1-only — skipping broker rebuild.")
    count_brk = spark.sql(f"SELECT COUNT(*) FROM {tgt_brk}").collect()[0][0]

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_customer  (SCD-2)
# ═══════════════════════════════════════════════════════════════════════════════
src_cust = tbl(cfg, "staging", "customer_scd2_versions")
src_tx   = tbl(cfg, "silver", "taxrate")
tgt_cust = tbl(cfg, "gold",   "dim_customer")

df_cust = spark.table(src_cust)
df_tx   = spark.table(src_tx)

df_tx_lcl = F.broadcast(df_tx.select(
    F.col("TX_ID").alias("_lcl_tx_id"),
    F.col("TX_NAME").alias("_lcl_tx_name"),
    F.col("TX_RATE").cast("decimal(15,4)").alias("_lcl_tx_rate"),
))
df_tx_nat = F.broadcast(df_tx.select(
    F.col("TX_ID").alias("_nat_tx_id"),
    F.col("TX_NAME").alias("_nat_tx_name"),
    F.col("TX_RATE").cast("decimal(15,4)").alias("_nat_tx_rate"),
))

w_cust = Window.orderBy(F.col("C_ID").cast("bigint"), F.col("effective_date"))

df_dim_customer = (
    df_cust
    .join(df_tx_lcl, df_cust["C_LCL_TX_ID"] == df_tx_lcl["_lcl_tx_id"], "left")
    .join(df_tx_nat, df_cust["C_NAT_TX_ID"] == df_tx_nat["_nat_tx_id"], "left")
    .withColumn("SK_CustomerID", F.row_number().over(w_cust).cast("bigint"))
    .select(
        F.col("SK_CustomerID"),
        F.col("C_ID").cast("bigint").alias("CustomerID"),
        F.col("effective_date").alias("EffectiveDate"),
        F.col("end_date").alias("EndDate"),
        F.col("is_current").alias("IsCurrent"),
        F.col("batch_id").alias("BatchID"),
        F.col("C_STATUS").alias("Status"),
        F.col("C_TAX_ID").alias("TaxID"),
        F.col("C_L_NAME").alias("LastName"),
        F.col("C_F_NAME").alias("FirstName"),
        F.col("C_M_NAME").alias("MiddleInitial"),
        F.col("C_GNDR").alias("Gender"),
        F.when(F.trim(F.col("C_TIER")) != "", F.col("C_TIER").cast("int")).alias("Tier"),
        F.coalesce(
            F.try_to_date(F.col("C_DOB"), "yyyy-MM-dd"),
            F.try_to_date(F.col("C_DOB"), "yyyyMMdd"),
        ).alias("DateOfBirth"),
        F.col("C_ADLINE1").alias("AddressLine1"),
        F.col("C_ADLINE2").alias("AddressLine2"),
        F.col("C_ZIPCODE").alias("PostalCode"),
        F.col("C_CITY").alias("City"),
        F.col("C_STATE_PROV").alias("StateProv"),
        F.col("C_CTRY").alias("Country"),
        F.concat_ws("",
            F.coalesce(F.when(F.trim(F.col("C_CTRY_1"))  != "", F.trim(F.col("C_CTRY_1"))),  F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_AREA_1"))  != "", F.trim(F.col("C_AREA_1"))),  F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_LOCAL_1")) != "", F.trim(F.col("C_LOCAL_1"))), F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_EXT_1"))   != "", F.trim(F.col("C_EXT_1"))),   F.lit("")),
        ).alias("Phone1"),
        F.concat_ws("",
            F.coalesce(F.when(F.trim(F.col("C_CTRY_2"))  != "", F.trim(F.col("C_CTRY_2"))),  F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_AREA_2"))  != "", F.trim(F.col("C_AREA_2"))),  F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_LOCAL_2")) != "", F.trim(F.col("C_LOCAL_2"))), F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_EXT_2"))   != "", F.trim(F.col("C_EXT_2"))),   F.lit("")),
        ).alias("Phone2"),
        F.concat_ws("",
            F.coalesce(F.when(F.trim(F.col("C_CTRY_3"))  != "", F.trim(F.col("C_CTRY_3"))),  F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_AREA_3"))  != "", F.trim(F.col("C_AREA_3"))),  F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_LOCAL_3")) != "", F.trim(F.col("C_LOCAL_3"))), F.lit("")),
            F.coalesce(F.when(F.trim(F.col("C_EXT_3"))   != "", F.trim(F.col("C_EXT_3"))),   F.lit("")),
        ).alias("Phone3"),
        F.col("C_PRIM_EMAIL").alias("Email1"),
        F.col("C_ALT_EMAIL").alias("Email2"),
        F.col("_lcl_tx_name").alias("LocalTaxRateDesc"),
        F.col("_lcl_tx_rate").alias("LocalTaxRate"),
        F.col("_nat_tx_name").alias("NationalTaxRateDesc"),
        F.col("_nat_tx_rate").alias("NationalTaxRate"),
    )
)
df_dim_customer = add_gold_audit(df_dim_customer, BATCH_ID, RUN_ID)

count_cust = create_or_replace_table(df_dim_customer, tgt_cust)

is_current_count = spark.sql(f"SELECT COUNT(*) FROM {tgt_cust} WHERE IsCurrent = TRUE").collect()[0][0]
unique_cid_count = spark.sql(f"SELECT COUNT(DISTINCT CustomerID) FROM {tgt_cust}").collect()[0][0]

print(f"gold.dim_customer: {count_cust:,} total versions (SCD-2)")
print(f"  IsCurrent=TRUE  : {is_current_count:,}")
print(f"  Unique customers: {unique_cid_count:,}")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_cust,
              target_table=tgt_cust, operation="OVERWRITE",
              rows_affected=count_cust, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_account (SCD-2 + Temporal Joins)
# ═══════════════════════════════════════════════════════════════════════════════
src_acct = tbl(cfg, "silver", "account")
tgt_acct = tbl(cfg, "gold",   "dim_account")

df_acct = spark.table(src_acct)

# Pre-cast join key columns defensively
df_acct = df_acct.withColumn(
    "_ca_c_id", F.when(F.trim(F.col("CA_C_ID")) != "", F.col("CA_C_ID").cast("bigint"))
).withColumn(
    "_ca_b_id", F.when(F.trim(F.col("CA_B_ID")) != "", F.col("CA_B_ID").cast("bigint"))
)

# 1. SCD-2 Timeline Generation
# We use update_ts and _sort_key to ensure deterministic chronological sorting
w_acct_hist = Window.partitionBy("CA_ID").orderBy("update_ts", "_sort_key")
df_acct = df_acct.withColumn("EffectiveDate", F.to_date(F.col("update_ts")))
df_acct = df_acct.withColumn("EndDate", F.coalesce(F.lead("EffectiveDate").over(w_acct_hist), F.lit("9999-12-31").cast("date")))
df_acct = df_acct.withColumn("IsCurrent", F.col("EndDate") == F.lit("9999-12-31").cast("date"))
df_acct = df_acct.withColumn("version_number", F.row_number().over(w_acct_hist))

# 2. Surrogate Key Generation
df_acct = df_acct.withColumn("SK_AccountID", F.expr("CAST(concat(date_format(EffectiveDate, 'yyyyMMdd'), CA_ID) AS BIGINT)"))
df_acct = df_acct.withColumn("record_hash", F.md5(F.concat_ws("|", "CA_NAME", "CA_B_ID", "CA_ST_ID")))

# 3. Temporal Join Preparation
# We must use ALL versions of dim_customer to fetch the correct historical SK_CustomerID
df_gcu = spark.table(tgt_cust).select(
    F.col("CustomerID").alias("_cust_id"),
    F.col("SK_CustomerID").alias("_sk_cust_id"),
    F.col("EffectiveDate").alias("_cust_eff"),
    F.col("EndDate").alias("_cust_end")
)

df_gbrk = F.broadcast(spark.table(tgt_brk).select(
    F.col("BrokerID").alias("_brk_id"),
    F.col("SK_BrokerID").alias("_sk_brk_id"),
))

# 4. Join and Format
df_dim_account = (
    df_acct
    # Temporal Point-in-Time Join: Match the Account event date to the active Customer window
    .join(
        df_gcu,
        (df_acct["_ca_c_id"] == df_gcu["_cust_id"]) &
        (df_acct["EffectiveDate"] >= df_gcu["_cust_eff"]) &
        (df_acct["EffectiveDate"] < df_gcu["_cust_end"]),
        "left"
    )
    .join(df_gbrk, df_acct["_ca_b_id"] == df_gbrk["_brk_id"], "left")
    .select(
        F.col("SK_AccountID"),
        F.col("CA_ID").cast("bigint").alias("AccountID"),
        F.coalesce(F.col("_sk_cust_id"), F.lit(-1).cast("bigint")).alias("SK_CustomerID"),
        F.coalesce(F.col("_sk_brk_id"),  F.lit(-1).cast("bigint")).alias("SK_BrokerID"),
        F.col("CA_NAME").alias("AccountDesc"),
        F.when(F.trim(F.col("CA_TAX_ST")) != "", F.col("CA_TAX_ST").cast("int")).alias("TaxStatus"),
        F.col("CA_ST_ID").alias("Status"),
        F.col("IsCurrent"),
        F.col("EffectiveDate").alias("valid_from"),
        F.col("EndDate").alias("valid_to"),
        F.col("EffectiveDate"),
        F.col("EndDate"),
        F.col("version_number"),
        F.col("record_hash"),
        F.current_timestamp().alias("system_valid_from"),
        F.lit("9999-12-31 23:59:59").cast("timestamp").alias("system_valid_to")
    )
)
df_dim_account = add_gold_audit(df_dim_account, BATCH_ID, RUN_ID)

count_acct = create_or_replace_table(df_dim_account, tgt_acct)
print(f"gold.dim_account: {count_acct:,} total versions (SCD-2)")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_acct,
              target_table=tgt_acct, operation="OVERWRITE",
              rows_affected=count_acct, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nDimBroker / DimCustomer (SCD-2) / DimAccount (SCD-2) gold complete.")
print(f"  gold.dim_broker   : {count_brk:,} rows")
print(f"  gold.dim_customer : {count_cust:,} versions ({is_current_count:,} current, {unique_cid_count:,} unique customers)")
print(f"  gold.dim_account  : {count_acct:,} versions")