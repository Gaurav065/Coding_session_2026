# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05c — Gold: DimCompany + DimSecurity
# Tables: gold.dim_company, gold.dim_security
# Pattern: silver.company / silver.security → SCD-2 timeline calculation → 
#          temporal join → deterministic surrogate keys → CORT
# Batch scope: B1 ONLY — company/security data comes from FINWIRE (batch 1)
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
    print("DimCompany / DimSecurity are B1-only (FINWIRE) — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_company (SCD-2)
# ═══════════════════════════════════════════════════════════════════════════════
src_co  = tbl(cfg, "silver", "company")
src_ind = tbl(cfg, "silver", "industry")
src_st  = tbl(cfg, "silver", "statustype")
tgt_co  = tbl(cfg, "gold",   "dim_company")

df_co  = spark.table(src_co)
df_ind = F.broadcast(spark.table(src_ind).select(F.col("IN_ID").alias("_in_id"), F.col("IN_NAME").alias("_in_name")))
df_st  = F.broadcast(spark.table(src_st).select(F.col("ST_ID").alias("_st_id"), F.col("ST_NAME").alias("_st_name")))

# 1. SCD-2 Timeline Generation
w_hist = Window.partitionBy("cik").orderBy("pts")
df_co = df_co.withColumn("CompanyID", F.col("cik").cast("bigint"))
df_co = df_co.withColumn("EffectiveDate", F.to_date(F.col("pts")))
df_co = df_co.withColumn("EndDate", F.coalesce(F.lead("EffectiveDate").over(w_hist), F.lit("9999-12-31").cast("date")))
df_co = df_co.withColumn("IsCurrent", F.col("EndDate") == F.lit("9999-12-31").cast("date"))
df_co = df_co.withColumn("version_number", F.row_number().over(w_hist))

# 2. Surrogate Key Generation (Deterministic: YYYYMMDD + CompanyID)
df_co = df_co.withColumn("SK_CompanyID", F.expr("CAST(concat(date_format(EffectiveDate, 'yyyyMMdd'), CompanyID) AS BIGINT)"))

# 3. Tracked Hash for Metadata
df_co = df_co.withColumn("record_hash", F.md5(F.concat_ws("|", "company_name", "industry_id", "status", "sp_rating", "ceo_name")))

# 4. Join Lookups & Format
df_dim_company = (
    df_co
    .join(df_ind, df_co["industry_id"] == df_ind["_in_id"], "left")
    .join(df_st,  df_co["status"]      == df_st["_st_id"],  "left")
    .select(
        F.col("SK_CompanyID"),
        F.col("CompanyID"),
        F.coalesce(F.col("_st_name"), F.lit("Unknown")).alias("Status"),
        F.col("company_name").alias("Name"),
        F.coalesce(F.col("_in_name"), F.lit("Unknown")).alias("Industry"),
        F.col("sp_rating").alias("SPrating"),
        # TPC-DI isLowGrade rule: True if SPrating is below investment grade (BBB)
        F.when(F.col("sp_rating").rlike("^[CD]|BB?$"), True).otherwise(False).alias("isLowGrade"),
        F.col("ceo_name").alias("CEO"),
        F.col("description").alias("Description"),
        F.col("founding_date").cast("date").alias("FoundingDate"),
        F.col("city").alias("City"),
        F.col("postal_code").alias("ZipCode"),
        F.col("state_prov").alias("StateProvince"),
        F.col("country").alias("Country"),
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
df_dim_company = add_gold_audit(df_dim_company, BATCH_ID, RUN_ID)

count_co = create_or_replace_table(df_dim_company, tgt_co)
print(f"gold.dim_company: {count_co:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_co,
              target_table=tgt_co, operation="OVERWRITE",
              rows_affected=count_co, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# gold.dim_security (SCD-2 + Temporal Join to Company)
# ═══════════════════════════════════════════════════════════════════════════════
src_sec = tbl(cfg, "silver", "security")
tgt_sec = tbl(cfg, "gold",   "dim_security")

df_sec = spark.table(src_sec)
df_st2 = F.broadcast(spark.table(src_st).select(F.col("ST_ID").alias("_sec_st_id"), F.col("ST_NAME").alias("_sec_st_name")))

# 1. SCD-2 Timeline Generation
w_sec_hist = Window.partitionBy("symbol").orderBy("pts")
df_sec = df_sec.withColumn("EffectiveDate", F.to_date(F.col("pts")))
df_sec = df_sec.withColumn("EndDate", F.coalesce(F.lead("EffectiveDate").over(w_sec_hist), F.lit("9999-12-31").cast("date")))
df_sec = df_sec.withColumn("IsCurrent", F.col("EndDate") == F.lit("9999-12-31").cast("date"))
df_sec = df_sec.withColumn("version_number", F.row_number().over(w_sec_hist))

# 2. Surrogate Key Generation (Deterministic: YYYYMMDD + hash(symbol))
df_sec = df_sec.withColumn("SK_SecurityID", F.expr("CAST(concat(date_format(EffectiveDate, 'yyyyMMdd'), abs(hash(symbol))) AS BIGINT)"))
df_sec = df_sec.withColumn("record_hash", F.md5(F.concat_ws("|", "name", "status", "issue_type")))

# 3. Temporal Join Preparation to dim_company
df_gco = spark.table(tgt_co).select("SK_CompanyID", "CompanyID", "Name", "EffectiveDate", "EndDate")

# Path 1: Match on Numeric CIK
df_c1 = F.broadcast(df_gco.select(
    F.col("SK_CompanyID").alias("_sk_cik"),
    F.col("CompanyID").cast("string").alias("_co_id_str"),
    F.col("EffectiveDate").alias("_co_eff1"),
    F.col("EndDate").alias("_co_end1")
))

# Path 2: Match on Company Name
df_c2 = F.broadcast(df_gco.select(
    F.col("SK_CompanyID").alias("_sk_name"),
    F.col("Name").alias("_co_name"),
    F.col("EffectiveDate").alias("_co_eff2"),
    F.col("EndDate").alias("_co_end2")
))

# 4. Join & Format
df_dim_security = (
    df_sec
    .join(df_st2, df_sec["status"] == df_st2["_sec_st_id"], "left")
    # Temporal Join 1 (CIK)
    .join(
        df_c1,
        (F.trim(df_sec["co_name_or_cik"]) == df_c1["_co_id_str"]) & 
        (df_sec["EffectiveDate"] >= df_c1["_co_eff1"]) & 
        (df_sec["EffectiveDate"] < df_c1["_co_end1"]),
        "left"
    )
    # Temporal Join 2 (Name)
    .join(
        df_c2,
        (F.trim(df_sec["co_name_or_cik"]) == F.trim(df_c2["_co_name"])) & 
        (df_sec["EffectiveDate"] >= df_c2["_co_eff2"]) & 
        (df_sec["EffectiveDate"] < df_c2["_co_end2"]),
        "left"
    )
    .select(
        F.col("SK_SecurityID"),
        F.col("symbol").alias("Symbol"),
        F.col("issue_type").alias("IssueType"),
        F.coalesce(F.col("_sec_st_name"), F.lit("Unknown")).alias("Status"),
        F.col("name").alias("Name"),
        F.coalesce(F.col("_sk_cik"), F.col("_sk_name"), F.lit(-1).cast("bigint")).alias("SK_CompanyID"),
        F.col("co_name_or_cik").alias("CoNameOrCIK"),
        F.coalesce(
            F.try_to_date(F.col("ex_date").cast("string"), "yyyy-MM-dd"),
            F.try_to_date(F.col("ex_date").cast("string"), "yyyyMMdd"),
        ).alias("ExchangeDate"),
        F.when(
            F.trim(F.col("shares_outstanding").cast("string")).isNotNull()
            & (F.trim(F.col("shares_outstanding").cast("string")) != ""),
            F.regexp_extract(F.col("shares_outstanding").cast("string"), r"^\s*(\d+)", 1).cast("bigint"),
        ).alias("SharesOutstanding"),
        F.coalesce(
            F.try_to_date(F.col("first_trade").cast("string"), "yyyy-MM-dd"),
            F.try_to_date(F.col("first_trade").cast("string"), "yyyyMMdd"),
        ).alias("FirstTradeDate"),
        F.coalesce(
            F.try_to_date(F.col("first_trade_on_exchange").cast("string"), "yyyy-MM-dd"),
            F.try_to_date(F.col("first_trade_on_exchange").cast("string"), "yyyyMMdd"),
        ).alias("FirstTradeDateOnExchange"),
        F.when(
            F.trim(F.col("dividend").cast("string")).isNotNull()
            & (F.trim(F.col("dividend").cast("string")) != ""),
            F.regexp_extract(F.col("dividend").cast("string"), r"^\s*(-?\d+\.?\d*)", 1).cast("decimal(15,4)"),
        ).alias("Dividend"),
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
df_dim_security = add_gold_audit(df_dim_security, BATCH_ID, RUN_ID)

count_sec = create_or_replace_table(df_dim_security, tgt_sec)
print(f"gold.dim_security: {count_sec:,} rows")

log_row_count(spark, OPS_AUDIT, layer="gold", source_table=src_sec,
              target_table=tgt_sec, operation="OVERWRITE",
              rows_affected=count_sec, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nDimCompany / DimSecurity SCD-2 gold complete.")
print(f"  gold.dim_company  : {count_co:,} rows")
print(f"  gold.dim_security : {count_sec:,} rows")