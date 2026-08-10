# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 04e — Silver: CUSTOMER Domain
# Tables: silver.customer, silver.prospect
# Pattern: CORT (full rebuild each run from ALL bronze batches)
#
# silver.customer — Unified current customer state (SCD-1 per C_ID):
#   B1 source : bronze.customermgmt (ActionType IN ADDCUST/UPDCUST/INACTIVECUST)
#   B2/B3 src : bronze.customer     (CDC_FLAG I=insert, U=update, D=deactivate)
#   Merge     : union B1 + B2/B3, dedup per C_ID taking latest event
#
# silver.prospect — Latest state per agencyid + first_batchid:
#   Source    : bronze.prospect (all batches accumulated)
#   Dedup     : per agencyid — first_batchid = MIN(_batch), latest = ROW_NUMBER
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
from pyspark.sql.window import Window

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import bronze_to_silver
from modules.delta_utils import create_or_replace_table, table_exists
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
# silver.customer — SCD-1 per C_ID (current state)
#
# Common final columns for both bronze sources:
# C_ID, C_TAX_ID, C_STATUS, C_L_NAME, C_F_NAME, C_M_NAME, C_GNDR, C_TIER, C_DOB,
# C_ADLINE1, C_ADLINE2, C_ZIPCODE, C_CITY, C_STATE_PROV, C_CTRY,
# C_PRIM_EMAIL, C_ALT_EMAIL,
# C_CTRY_1..3, C_AREA_1..3, C_LOCAL_1..3, C_EXT_1..3,
# C_LCL_TX_ID, C_NAT_TX_ID
# + _sort_ts (ordering), _batch, _run_id, _ingest_ts, _source_file
# ═══════════════════════════════════════════════════════════════════════════════

CUST_COLS = [
    "C_ID", "C_TAX_ID", "C_STATUS",
    "C_L_NAME", "C_F_NAME", "C_M_NAME",
    "C_GNDR", "C_TIER", "C_DOB",
    "C_ADLINE1", "C_ADLINE2", "C_ZIPCODE", "C_CITY", "C_STATE_PROV", "C_CTRY",
    "C_PRIM_EMAIL", "C_ALT_EMAIL",
    "C_CTRY_1", "C_AREA_1", "C_LOCAL_1", "C_EXT_1",
    "C_CTRY_2", "C_AREA_2", "C_LOCAL_2", "C_EXT_2",
    "C_CTRY_3", "C_AREA_3", "C_LOCAL_3", "C_EXT_3",
    "C_LCL_TX_ID", "C_NAT_TX_ID",
    "_sort_ts",
    "_batch", "_run_id", "_ingest_ts", "_source_file",
]

# ─── B1: bronze.customermgmt ─────────────────────────────────────────────────
src_mgmt = tbl(cfg, "bronze", "customermgmt")
df_mgmt  = spark.table(src_mgmt)

df_b1 = (
    df_mgmt
    .filter(F.col("ActionType").isin("ADDCUST", "UPDCUST", "INACTIVECUST"))
    .select(
        F.col("C_ID").cast("bigint").alias("C_ID"),
        F.col("C_TAX_ID").cast("string").alias("C_TAX_ID"),
        F.when(F.col("ActionType") == "INACTIVECUST", F.lit("Inactive"))
         .otherwise(F.lit("Active")).alias("C_STATUS"),
        F.col("C_L_NAME").alias("C_L_NAME"),
        F.col("C_F_NAME").alias("C_F_NAME"),
        F.col("C_M_NAME").alias("C_M_NAME"),
        F.col("C_GNDR").alias("C_GNDR"),
        F.col("C_TIER").alias("C_TIER"),
        F.col("C_DOB").alias("C_DOB"),
        F.col("C_ADLINE1").alias("C_ADLINE1"),
        F.col("C_ADLINE2").alias("C_ADLINE2"),
        F.col("C_ZIPCODE").alias("C_ZIPCODE"),
        F.col("C_CITY").alias("C_CITY"),
        F.col("C_STATE_PROV").alias("C_STATE_PROV"),
        F.col("C_CTRY").alias("C_CTRY"),
        F.col("C_PRIM_EMAIL").alias("C_PRIM_EMAIL"),
        F.col("C_ALT_EMAIL").alias("C_ALT_EMAIL"),
        F.col("C_CTRY_1").alias("C_CTRY_1"), F.col("C_AREA_1").alias("C_AREA_1"),
        F.col("C_LOCAL_1").alias("C_LOCAL_1"), F.col("C_EXT_1").alias("C_EXT_1"),
        F.col("C_CTRY_2").alias("C_CTRY_2"), F.col("C_AREA_2").alias("C_AREA_2"),
        F.col("C_LOCAL_2").alias("C_LOCAL_2"), F.col("C_EXT_2").alias("C_EXT_2"),
        F.col("C_CTRY_3").alias("C_CTRY_3"), F.col("C_AREA_3").alias("C_AREA_3"),
        F.col("C_LOCAL_3").alias("C_LOCAL_3"), F.col("C_EXT_3").alias("C_EXT_3"),
        F.col("C_LCL_TX_ID").alias("C_LCL_TX_ID"),
        F.col("C_NAT_TX_ID").alias("C_NAT_TX_ID"),
        # Sort key: batch takes highest precedence, ActionTS breaks ties within B1.
        # Formula must be BIGINT and comparable with the B2/B3 key (batch * 10^12 + DSN).
        # batch=1 * 10^12 + unix_ts(ActionTS) ≈ 1.001 × 10^12
        # batch=2 * 10^12 + CDC_DSN           ≈ 2.000 × 10^12  → always > B1, correct.
        #
        # ActionTS root cause: customermgmt uses ISO 8601 format '2015-01-07T10:25:51'
        # (literal T separator). unix_timestamp() defaults to 'yyyy-MM-dd HH:mm:ss'
        # (space separator) and throws in DBR 15+ ANSI mode at the T (index 10).
        # Fix: substring(1,19) strips trailing tz/fractional info, regexp_replace
        # swaps the T → space producing a cleanly parseable 'yyyy-MM-dd HH:mm:ss' string.
        (F.col("_batch").cast("bigint") * F.lit(1_000_000_000_000)
         + F.coalesce(
             F.unix_timestamp(
                 F.regexp_replace(F.substring(F.col("ActionTS"), 1, 19), "T", " "),
                 "yyyy-MM-dd HH:mm:ss",
             ),
             F.lit(0),
         )).alias("_sort_ts"),
        F.col("_batch"), F.col("_run_id"), F.col("_ingest_ts"), F.col("_source_file"),
    )
)

# ─── B2/B3: bronze.customer (if table exists) ────────────────────────────────
src_cdc = tbl(cfg, "bronze", "customer")

if table_exists(spark, src_cdc):
    df_cdc = spark.table(src_cdc)

    df_b2b3 = (
        df_cdc
        .filter(F.col("CDC_FLAG").isin("I", "U", "D"))
        .select(
            F.col("C_ID").cast("bigint").alias("C_ID"),
            F.col("C_TAX_ID").cast("string").alias("C_TAX_ID"),
            F.when(F.col("CDC_FLAG") == "D", F.lit("Inactive"))
             .otherwise(F.lit("Active")).alias("C_STATUS"),
            F.col("C_L_NAME").alias("C_L_NAME"),
            F.col("C_F_NAME").alias("C_F_NAME"),
            F.col("C_M_NAME").alias("C_M_NAME"),
            F.col("C_GNDR").alias("C_GNDR"),
            F.col("C_TIER").alias("C_TIER"),
            F.col("C_DOB").alias("C_DOB"),
            F.col("C_ADLINE1").alias("C_ADLINE1"),
            F.col("C_ADLINE2").alias("C_ADLINE2"),
            F.col("C_ZIPCODE").alias("C_ZIPCODE"),
            F.col("C_CITY").alias("C_CITY"),
            F.col("C_STATE_PROV").alias("C_STATE_PROV"),
            F.col("C_CTRY").alias("C_CTRY"),
            # B2/B3 uses C_EMAIL_1 / C_EMAIL_2 instead of C_PRIM_EMAIL / C_ALT_EMAIL
            F.col("C_EMAIL_1").alias("C_PRIM_EMAIL"),
            F.col("C_EMAIL_2").alias("C_ALT_EMAIL"),
            F.col("C_CTRY_1").alias("C_CTRY_1"), F.col("C_AREA_1").alias("C_AREA_1"),
            F.col("C_LOCAL_1").alias("C_LOCAL_1"), F.col("C_EXT_1").alias("C_EXT_1"),
            F.col("C_CTRY_2").alias("C_CTRY_2"), F.col("C_AREA_2").alias("C_AREA_2"),
            F.col("C_LOCAL_2").alias("C_LOCAL_2"), F.col("C_EXT_2").alias("C_EXT_2"),
            F.col("C_CTRY_3").alias("C_CTRY_3"), F.col("C_AREA_3").alias("C_AREA_3"),
            F.col("C_LOCAL_3").alias("C_LOCAL_3"), F.col("C_EXT_3").alias("C_EXT_3"),
            F.col("C_LCL_TX_ID").alias("C_LCL_TX_ID"),
            F.col("C_NAT_TX_ID").alias("C_NAT_TX_ID"),
            # Sort key: same formula as B1 — batch * 10^12 + CDC_DSN.
            # batch=2+ guarantees B2/B3 events always supersede B1 events.
            (F.col("_batch").cast("bigint") * F.lit(1_000_000_000_000)
             + F.coalesce(F.col("CDC_DSN").cast("bigint"), F.lit(0))).alias("_sort_ts"),
            F.col("_batch"), F.col("_run_id"), F.col("_ingest_ts"), F.col("_source_file"),
        )
    )

    df_all = df_b1.unionByName(df_b2b3)
else:
    # B1-only run — no bronze.customer yet
    df_all = df_b1

# ─── SCD-1 dedup per C_ID: keep latest event ─────────────────────────────────
w_cust = Window.partitionBy("C_ID").orderBy(F.col("_sort_ts").desc())

df_latest = (
    df_all
    .withColumn("_rn", F.row_number().over(w_cust))
    .filter(F.col("_rn") == 1)
    .drop("_rn", "_sort_ts")
)

df_latest = bronze_to_silver(df_latest)

tgt_cust = tbl(cfg, "silver", "customer")
count_cust = create_or_replace_table(df_latest, tgt_cust)
print(f"silver.customer: {count_cust:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_mgmt,
              target_table=tgt_cust, operation="OVERWRITE",
              rows_affected=count_cust, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# silver.prospect — Latest state per agencyid + first_batchid
#
# bronze.prospect accumulates all batches.
# For each agencyid: first_batchid = MIN(_batch), current = highest _batch row.
# ═══════════════════════════════════════════════════════════════════════════════
src_pro = tbl(cfg, "bronze", "prospect")
tgt_pro = tbl(cfg, "silver", "prospect")

df_pro_raw = spark.table(src_pro)

# First batchid per agencyid
df_first = (
    df_pro_raw
    .groupBy("agencyid")
    .agg(F.min("_batch").alias("first_batchid"))
)

# Latest row per agencyid
w_pro = Window.partitionBy("agencyid").orderBy(F.col("_batch").cast("int").desc())

df_pro_latest = (
    df_pro_raw
    .withColumn("_rn", F.row_number().over(w_pro))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
    .join(df_first, on="agencyid", how="left")
)

df_pro_latest = bronze_to_silver(df_pro_latest)

df_pro_final = df_pro_latest.select(
    "agencyid", "lastname", "firstname", "middleinitial", "gender",
    "addressline1", "addressline2", "postalcode", "city", "state", "country",
    "phone", "income", "numbercars", "numberchildren", "maritalstatus",
    "age", "creditrating", "ownorrentflag", "employer",
    "numbercreditcards", "networth",
    "first_batchid",
    "_load_ts", "_batch", "_run_id",
)

count_pro = create_or_replace_table(df_pro_final, tgt_pro)
print(f"silver.prospect: {count_pro:,} rows")

log_row_count(spark, OPS_AUDIT, layer="silver", source_table=src_pro,
              target_table=tgt_pro, operation="OVERWRITE",
              rows_affected=count_pro, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nCustomer silver complete.")
print(f"  silver.customer : {count_cust:,} rows (SCD-1, latest per C_ID)")
print(f"  silver.prospect : {count_pro:,} rows (latest per agencyid)")
