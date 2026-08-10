# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05d — Staging: CUSTOMER SCD-2 version history
# Table: staging.customer_scd2_versions
#
# Strategy:
#   Build a complete SCD-2 version history for every customer across all batches.
#   B1 source : bronze.customermgmt (ActionType: ADDCUST, UPDCUST, INACTIVECUST)
#   B2/B3 src : bronze.customer     (CDC_FLAG: I=insert, U=update, D=deactivate)
#
#   For each C_ID, rows are ordered by a sort_key:
#     - B1: unix_timestamp(event_ts) — ActionTS drives the ordering
#     - B2/B3: batch * 1000000 + CDC_DSN — batch sequence number
#
#   effective_date:
#     - B1: DATE(event_ts) from ActionTS
#     - B2/B3: lookup from bronze.batchdate keyed on _batch
#
#   end_date = DATE_SUB(LEAD(effective_date) OVER (PARTITION BY C_ID ORDER BY sort_key), 1)
#   is_current = (end_date IS NULL)
#
# Batch scope: ALL batches (CORT — full rebuild from all bronze each run).
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'): del sys.modules[_k]
sys.path.insert(0, _root)

from functools import reduce

from pyspark.sql import DataFrame, functions as F
from pyspark.sql.window import Window

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.audit_utils import add_staging_audit
from modules.delta_utils import overwrite_table, table_exists
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
# Step 1: Load batch dates from bronze.batchdate
# Maps batchid → effective date for B2/B3 events (no ActionTS available).
# ═══════════════════════════════════════════════════════════════════════════════
src_bd  = tbl(cfg, "bronze", "batchdate")
tgt_scd = tbl(cfg, "staging", "customer_scd2_versions")

df_batchdates = (
    spark.table(src_bd)
    .select(
        F.col("batchid").alias("_bid"),
        F.to_date(F.col("batchdate")).alias("batch_dt"),
    )
)
print("Batch dates loaded:")
df_batchdates.show()

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Canonical column list shared by both event sources
# (after normalisation from their respective bronze schemas)
# ═══════════════════════════════════════════════════════════════════════════════
PHONE_COLS = [
    "C_CTRY_1", "C_AREA_1", "C_LOCAL_1", "C_EXT_1",
    "C_CTRY_2", "C_AREA_2", "C_LOCAL_2", "C_EXT_2",
    "C_CTRY_3", "C_AREA_3", "C_LOCAL_3", "C_EXT_3",
]

EVENT_FRAMES = []

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: Build B1 events from bronze.customermgmt
# ═══════════════════════════════════════════════════════════════════════════════
src_cm = tbl(cfg, "bronze", "customermgmt")

if table_exists(spark, src_cm):
    df_cm = (
        spark.table(src_cm)
        .filter(F.col("ActionType").isin("ADDCUST", "UPDCUST", "INACTIVECUST"))
    )

    df_b1 = df_cm.select(
        F.col("C_ID").cast("bigint").alias("C_ID"),
        F.col("C_TAX_ID").cast("string").alias("C_TAX_ID"),
        F.when(F.col("ActionType") == "INACTIVECUST", F.lit("Inactive"))
         .otherwise(F.lit("Active"))
         .alias("C_STATUS"),
        F.col("C_L_NAME").cast("string").alias("C_L_NAME"),
        F.col("C_F_NAME").cast("string").alias("C_F_NAME"),
        F.col("C_M_NAME").cast("string").alias("C_M_NAME"),
        F.col("C_GNDR").cast("string").alias("C_GNDR"),
        F.col("C_TIER").cast("string").alias("C_TIER"),
        F.col("C_DOB").cast("string").alias("C_DOB"),
        F.col("C_ADLINE1").cast("string").alias("C_ADLINE1"),
        F.col("C_ADLINE2").cast("string").alias("C_ADLINE2"),
        F.col("C_ZIPCODE").cast("string").alias("C_ZIPCODE"),
        F.col("C_CITY").cast("string").alias("C_CITY"),
        F.col("C_STATE_PROV").cast("string").alias("C_STATE_PROV"),
        F.col("C_CTRY").cast("string").alias("C_CTRY"),
        # B1 uses C_PRIM_EMAIL / C_ALT_EMAIL directly
        F.col("C_PRIM_EMAIL").cast("string").alias("C_PRIM_EMAIL"),
        F.col("C_ALT_EMAIL").cast("string").alias("C_ALT_EMAIL"),
        F.col("C_CTRY_1").cast("string").alias("C_CTRY_1"),
        F.col("C_AREA_1").cast("string").alias("C_AREA_1"),
        F.col("C_LOCAL_1").cast("string").alias("C_LOCAL_1"),
        F.col("C_EXT_1").cast("string").alias("C_EXT_1"),
        F.col("C_CTRY_2").cast("string").alias("C_CTRY_2"),
        F.col("C_AREA_2").cast("string").alias("C_AREA_2"),
        F.col("C_LOCAL_2").cast("string").alias("C_LOCAL_2"),
        F.col("C_EXT_2").cast("string").alias("C_EXT_2"),
        F.col("C_CTRY_3").cast("string").alias("C_CTRY_3"),
        F.col("C_AREA_3").cast("string").alias("C_AREA_3"),
        F.col("C_LOCAL_3").cast("string").alias("C_LOCAL_3"),
        F.col("C_EXT_3").cast("string").alias("C_EXT_3"),
        F.col("C_LCL_TX_ID").cast("string").alias("C_LCL_TX_ID"),
        F.col("C_NAT_TX_ID").cast("string").alias("C_NAT_TX_ID"),
        # event_ts: parse ActionTS as timestamp for B1 sort ordering
        F.to_timestamp(F.col("ActionTS")).alias("event_ts"),
        F.lit("1").alias("event_batch"),
        F.col("ActionType").alias("event_type"),
        # sort_key for B1: unix seconds of event_ts
        F.unix_timestamp(F.to_timestamp(F.col("ActionTS"))).cast("bigint").alias("sort_key"),
    )

    EVENT_FRAMES.append(df_b1)
    print(f"B1 customermgmt events (ADDCUST/UPDCUST/INACTIVECUST): {df_b1.count():,}")
else:
    print(f"WARNING: {src_cm} not found — skipping B1 events.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: Build B2/B3 events from bronze.customer (if table exists)
# ═══════════════════════════════════════════════════════════════════════════════
src_cust = tbl(cfg, "bronze", "customer")

if table_exists(spark, src_cust):
    df_cust_raw = spark.table(src_cust)

    df_b23 = df_cust_raw.select(
        F.col("C_ID").cast("bigint").alias("C_ID"),
        F.col("C_TAX_ID").cast("string").alias("C_TAX_ID"),
        F.when(F.col("CDC_FLAG") == "D", F.lit("Inactive"))
         .otherwise(F.lit("Active"))
         .alias("C_STATUS"),
        F.col("C_L_NAME").cast("string").alias("C_L_NAME"),
        F.col("C_F_NAME").cast("string").alias("C_F_NAME"),
        F.col("C_M_NAME").cast("string").alias("C_M_NAME"),
        F.col("C_GNDR").cast("string").alias("C_GNDR"),
        F.col("C_TIER").cast("string").alias("C_TIER"),
        F.col("C_DOB").cast("string").alias("C_DOB"),
        F.col("C_ADLINE1").cast("string").alias("C_ADLINE1"),
        F.col("C_ADLINE2").cast("string").alias("C_ADLINE2"),
        F.col("C_ZIPCODE").cast("string").alias("C_ZIPCODE"),
        F.col("C_CITY").cast("string").alias("C_CITY"),
        F.col("C_STATE_PROV").cast("string").alias("C_STATE_PROV"),
        F.col("C_CTRY").cast("string").alias("C_CTRY"),
        # B2/B3 bronze uses C_EMAIL_1 / C_EMAIL_2
        F.col("C_EMAIL_1").cast("string").alias("C_PRIM_EMAIL"),
        F.col("C_EMAIL_2").cast("string").alias("C_ALT_EMAIL"),
        F.col("C_CTRY_1").cast("string").alias("C_CTRY_1"),
        F.col("C_AREA_1").cast("string").alias("C_AREA_1"),
        F.col("C_LOCAL_1").cast("string").alias("C_LOCAL_1"),
        F.col("C_EXT_1").cast("string").alias("C_EXT_1"),
        F.col("C_CTRY_2").cast("string").alias("C_CTRY_2"),
        F.col("C_AREA_2").cast("string").alias("C_AREA_2"),
        F.col("C_LOCAL_2").cast("string").alias("C_LOCAL_2"),
        F.col("C_EXT_2").cast("string").alias("C_EXT_2"),
        F.col("C_CTRY_3").cast("string").alias("C_CTRY_3"),
        F.col("C_AREA_3").cast("string").alias("C_AREA_3"),
        F.col("C_LOCAL_3").cast("string").alias("C_LOCAL_3"),
        F.col("C_EXT_3").cast("string").alias("C_EXT_3"),
        F.col("C_LCL_TX_ID").cast("string").alias("C_LCL_TX_ID"),
        F.col("C_NAT_TX_ID").cast("string").alias("C_NAT_TX_ID"),
        # B2/B3 has no ActionTS; event_ts is null (batch_dt used for effective_date)
        F.lit(None).cast("timestamp").alias("event_ts"),
        F.col("_batch").alias("event_batch"),
        F.col("CDC_FLAG").alias("event_type"),
        # sort_key for B2/B3: batch * 1_000_000 + CDC_DSN ensures global ordering
        (
            F.col("_batch").cast("bigint") * F.lit(1000000).cast("bigint")
            + F.coalesce(F.col("CDC_DSN").cast("bigint"), F.lit(0).cast("bigint"))
        ).alias("sort_key"),
    )

    EVENT_FRAMES.append(df_b23)
    print(f"B2/B3 customer events (all CDC flags): {df_b23.count():,}")
else:
    print(f"INFO: {src_cust} not found — B2/B3 events skipped (expected for B1-only run).")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: Union all event frames
# ═══════════════════════════════════════════════════════════════════════════════
if not EVENT_FRAMES:
    raise RuntimeError(
        "No customer source data found in bronze. "
        "Expected at least bronze.customermgmt (B1) or bronze.customer (B2/B3)."
    )

df_all = reduce(DataFrame.unionByName, EVENT_FRAMES)
print(f"Total events after union: {df_all.count():,}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: Compute effective_date per event
#   - B1: DATE(event_ts) from ActionTS
#   - B2/B3: join with df_batchdates on event_batch → batch_dt
# ═══════════════════════════════════════════════════════════════════════════════
df_all = df_all.join(
    df_batchdates,
    df_all["event_batch"] == df_batchdates["_bid"],
    "left",
)

df_all = df_all.withColumn(
    "effective_date",
    F.when(F.col("event_batch") == "1", F.to_date(F.col("event_ts")))
     .otherwise(F.col("batch_dt"))
)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: SCD-2 window — compute end_date and is_current per C_ID
#   end_date  = DATE_SUB(LEAD(effective_date), 1)   [NULL for the current row]
#   is_current = (end_date IS NULL)
# ═══════════════════════════════════════════════════════════════════════════════
w_scd2 = Window.partitionBy("C_ID").orderBy("sort_key")

df_all = df_all.withColumn(
    "next_effective_date",
    F.lead("effective_date").over(w_scd2),
)

df_all = df_all.withColumn(
    "end_date",
    F.when(
        F.col("next_effective_date").isNotNull(),
        F.date_sub(F.col("next_effective_date"), 1),
    ).otherwise(F.lit(None).cast("date"))
)

df_all = df_all.withColumn("is_current", F.col("end_date").isNull())

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Step 7: Select final columns for staging.customer_scd2_versions
# ═══════════════════════════════════════════════════════════════════════════════
df_final = df_all.select(
    "C_ID",
    F.col("event_batch").alias("batch_id"),
    "effective_date",
    "end_date",
    "is_current",
    "C_STATUS",
    "C_TAX_ID",
    "C_L_NAME", "C_F_NAME", "C_M_NAME",
    "C_GNDR", "C_TIER", "C_DOB",
    "C_ADLINE1", "C_ADLINE2", "C_ZIPCODE", "C_CITY", "C_STATE_PROV", "C_CTRY",
    "C_PRIM_EMAIL", "C_ALT_EMAIL",
    "C_CTRY_1", "C_AREA_1", "C_LOCAL_1", "C_EXT_1",
    "C_CTRY_2", "C_AREA_2", "C_LOCAL_2", "C_EXT_2",
    "C_CTRY_3", "C_AREA_3", "C_LOCAL_3", "C_EXT_3",
    "C_LCL_TX_ID", "C_NAT_TX_ID",
)

df_final = add_staging_audit(df_final, BATCH_ID, RUN_ID)

count_total = overwrite_table(df_final, tgt_scd)
print(f"staging.customer_scd2_versions written: {count_total:,} rows")

log_row_count(spark, OPS_AUDIT, layer="staging",
              source_table=f"{src_cm} + {src_cust}",
              target_table=tgt_scd, operation="OVERWRITE",
              rows_affected=count_total, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ─── Summary ─────────────────────────────────────────────────────────────────
count_current  = df_final.filter(F.col("is_current") == True).count()
count_unique   = df_final.select("C_ID").distinct().count()

print(f"\nCustomer SCD-2 staging complete.")
print(f"  staging.customer_scd2_versions: {count_total:,} total versions")
print(f"    is_current = TRUE : {count_current:,}")
print(f"    unique C_ID       : {count_unique:,}")
