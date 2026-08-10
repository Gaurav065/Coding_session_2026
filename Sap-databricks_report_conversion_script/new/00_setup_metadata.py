# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup: Metadata Tables & Configuration
# MAGIC
# MAGIC **Run ONCE** per environment to create metadata/result tables and register file pairs.
# MAGIC Re-run to update registration (existing entry is replaced).
# MAGIC
# MAGIC ### Widgets
# MAGIC | # | Widget | Purpose |
# MAGIC |---|--------|---------|
# MAGIC | 1 | `metadata_db` | Database for metadata tables |
# MAGIC | 2 | `results_db` | Database for validation results |
# MAGIC | 3 | `source_file` | Full Volume/DBFS path to source Excel |
# MAGIC | 4 | `target_file` | Full Volume/DBFS path to target Excel |
# MAGIC | 5 | `source_sheet` | Sheet name in source file |
# MAGIC | 6 | `target_sheet` | Sheet name in target file |
# MAGIC | 7 | `stream_name` | Unique ID for this validation pair |
# MAGIC | 8 | `sap_table` | SAP table name (for schema fetcher) |
# MAGIC | 9 | `primary_key_columns` | Comma-separated PK column names |
# MAGIC | 10 | `exclude_columns` | Columns excluded from MINUS query |
# MAGIC | 11 | `numeric_precision` | Decimal places for numeric comparison |

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════

VOLUME_PATH = "/Volumes/training/default/validation_volume"

dbutils.widgets.text("metadata_db",          "metadata_db",                                    "1. Metadata Database")
dbutils.widgets.text("results_db",           "results_db",                                     "2. Results Database")
dbutils.widgets.text("source_file",          f"{VOLUME_PATH}/zlofoa01_source_sap.XLSX",        "3. Source File Path")
dbutils.widgets.text("target_file",          f"{VOLUME_PATH}/GB_YRFORECAST_databrisks.xlsx",   "4. Target File Path")
dbutils.widgets.text("source_sheet",         "Sheet1",                                         "5. Source Sheet Name")
dbutils.widgets.text("target_sheet",         "result",                                         "6. Target Sheet Name")
dbutils.widgets.text("stream_name",          "yrforecastn_dc02",                               "7. Stream Name")
dbutils.widgets.text("sap_table",            "YRFORECAST",                                     "8. SAP Table Name")
dbutils.widgets.text("primary_key_columns",  "0FISCVARNT,0MATERIAL,0PLANT,0SALES_DIST,0VENDOR,0CALWEEK,0CALMONTH,0CALYEAR,0CALMONTH2,0FISCPER,0FISCYEAR,0CALDAY,0FISCPER3,ZFCTYPE,ZPARREG", "9. Primary Key Columns")
dbutils.widgets.text("exclude_columns",      "",                                               "10. Exclude Columns (blank=none)")
dbutils.widgets.text("numeric_precision",    "2",                                              "11. Numeric Precision")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  READ WIDGET VALUES
# ══════════════════════════════════════════════════════════════════

METADATA_DB       = dbutils.widgets.get("metadata_db").strip()
RESULTS_DB        = dbutils.widgets.get("results_db").strip()
source_file       = dbutils.widgets.get("source_file").strip()
target_file       = dbutils.widgets.get("target_file").strip()
source_sheet      = dbutils.widgets.get("source_sheet").strip()
target_sheet      = dbutils.widgets.get("target_sheet").strip()
stream_name       = dbutils.widgets.get("stream_name").strip()
sap_table         = dbutils.widgets.get("sap_table").strip()
numeric_precision = int(dbutils.widgets.get("numeric_precision").strip())

pk_raw = dbutils.widgets.get("primary_key_columns").strip()
primary_key_columns = [c.strip() for c in pk_raw.split(",") if c.strip()]

excl_raw = dbutils.widgets.get("exclude_columns").strip()
exclude_columns = [c.strip() for c in excl_raw.split(",") if c.strip()] if excl_raw else []

print("=" * 70)
print("  CONFIGURATION (from widgets)")
print("=" * 70)
print(f"  Metadata DB       : {METADATA_DB}")
print(f"  Results DB        : {RESULTS_DB}")
print(f"  Stream            : {stream_name}")
print(f"  SAP Table         : {sap_table}")
print(f"  Source             : {source_file} [{source_sheet}]")
print(f"  Target             : {target_file} [{target_sheet}]")
print(f"  PK Columns  ({len(primary_key_columns):>2d})  : {primary_key_columns}")
print(f"  Exclude Columns    : {exclude_columns if exclude_columns else '(none)'}")
print(f"  Numeric Precision  : {numeric_precision}")
print("=" * 70)

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CREATE DATABASES
# ══════════════════════════════════════════════════════════════════

spark.sql(f"CREATE DATABASE IF NOT EXISTS {METADATA_DB}")
spark.sql(f"CREATE DATABASE IF NOT EXISTS {RESULTS_DB}")
print(f"  Databases: {METADATA_DB}, {RESULTS_DB}")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 1: Validation File Registry
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {METADATA_DB}.validation_file_registry")
spark.sql(f"""
CREATE TABLE {METADATA_DB}.validation_file_registry (
    stream_name          STRING   COMMENT 'Unique identifier for this file pair',
    source_file_path     STRING   COMMENT 'Volume/DBFS path to source Excel',
    source_sheet         STRING   COMMENT 'Sheet name in source file',
    target_file_path     STRING   COMMENT 'Volume/DBFS path to target Excel',
    target_sheet         STRING   COMMENT 'Sheet name in target file',
    sap_table_name       STRING   COMMENT 'SAP table name',
    primary_key_columns  STRING   COMMENT 'Comma-separated PK column names',
    exclude_columns      STRING   COMMENT 'Comma-separated exclude columns for MINUS',
    numeric_precision    INT      COMMENT 'Decimal places for numeric comparison',
    is_active            STRING   COMMENT 'Y=active, N=disabled'
) USING DELTA
""")

spark.sql(f"""
INSERT INTO {METADATA_DB}.validation_file_registry VALUES (
    '{stream_name}', '{source_file}', '{source_sheet}',
    '{target_file}', '{target_sheet}', '{sap_table}',
    '{",".join(primary_key_columns)}', '{",".join(exclude_columns)}',
    {numeric_precision}, 'Y'
)
""")
print(f"  {METADATA_DB}.validation_file_registry — '{stream_name}' registered")
display(spark.table(f"{METADATA_DB}.validation_file_registry"))

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 2: Dynamic Column Mapping
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {METADATA_DB}.dynamic_column_mapping")
spark.sql(f"""
CREATE TABLE {METADATA_DB}.dynamic_column_mapping (
    stream_name           STRING,
    source_column_name    STRING,
    source_column_index   INT,
    target_column_name    STRING,
    target_column_index   INT,
    mapping_method        STRING  COMMENT 'EXACT | NORMALIZED | FUZZY(score)',
    source_dtype          STRING,
    target_dtype          STRING,
    sap_field_name        STRING,
    sap_datatype          STRING,
    is_mapped             STRING,
    is_active             STRING
) USING DELTA
""")
print(f"  {METADATA_DB}.dynamic_column_mapping")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 3: SAP Source Schemas
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {METADATA_DB}.sap_source_schemas")
spark.sql(f"""
CREATE TABLE {METADATA_DB}.sap_source_schemas (
    sap_table       STRING,
    field_name      STRING,
    data_element    STRING,
    data_type       STRING,
    field_length    STRING,
    description     STRING
) USING DELTA
""")
print(f"  {METADATA_DB}.sap_source_schemas")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 4: Validation Summary (all 17 checks)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_validation_summary")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_validation_summary (
    run_id          STRING, stream_name    STRING,
    source_file     STRING, target_file    STRING,
    check_name      STRING, check_category STRING,
    status          STRING, details        STRING,
    source_value    STRING, target_value   STRING,
    created_ts      TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_validation_summary")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 5: Column-Level Detail
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_column_validation")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_column_validation (
    run_id         STRING, stream_name   STRING,
    source_column  STRING, target_column STRING,
    check_name     STRING, status        STRING,
    source_value   STRING, target_value  STRING,
    difference     STRING, created_ts    TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_column_validation")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 6: Row-Level Mismatches
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_row_mismatches")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_row_mismatches (
    run_id        STRING, stream_name  STRING,
    row_number    BIGINT, column_name  STRING,
    source_value  STRING, target_value STRING,
    mismatch_type STRING, created_ts   TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_row_mismatches")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 7: PK-Based Key Mismatches (Checks 11-13)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_key_mismatches")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_key_mismatches (
    run_id             STRING, stream_name        STRING,
    check_type         STRING, primary_key_values STRING,
    column_name        STRING, source_value       STRING,
    target_value       STRING, details            STRING,
    created_ts         TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_key_mismatches")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 8: Column-Wise Success Percentage (Check 14)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_column_success_pct")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_column_success_pct (
    run_id             STRING,  stream_name       STRING,
    source_column      STRING,  target_column     STRING,
    total_rows_compared BIGINT, matched_rows      BIGINT,
    mismatched_rows    BIGINT,  success_pct       DOUBLE,
    status             STRING,  created_ts        TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_column_success_pct")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 9: Mismatch Detail with PK Context (Check 15)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_mismatch_with_pk")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_mismatch_with_pk (
    run_id             STRING,  stream_name       STRING,
    primary_key_values STRING,  column_name       STRING,
    source_column      STRING,  target_column     STRING,
    source_value       STRING,  target_value      STRING,
    row_number         BIGINT,  created_ts        TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_mismatch_with_pk")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 10: PK Issue Summary (Check 16)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_pk_issue_summary")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_pk_issue_summary (
    run_id             STRING,  stream_name       STRING,
    issue_type         STRING,  primary_key_values STRING,
    mismatched_columns STRING,  details           STRING,
    created_ts         TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_pk_issue_summary")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 11: Exclude Column Audit (Check 17)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_excluded_columns")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_excluded_columns (
    run_id          STRING, stream_name      STRING,
    column_name     STRING, exclusion_source STRING,
    reason          STRING, created_ts       TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_excluded_columns")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  TABLE 12: MINUS Query Results (Check 17)
# ══════════════════════════════════════════════════════════════════

spark.sql(f"DROP TABLE IF EXISTS {RESULTS_DB}.src_tgt_minus_results")
spark.sql(f"""
CREATE TABLE {RESULTS_DB}.src_tgt_minus_results (
    run_id      STRING, stream_name STRING,
    direction   STRING, row_data    STRING,
    created_ts  TIMESTAMP
) USING DELTA
""")
print(f"  {RESULTS_DB}.src_tgt_minus_results")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  VERIFY SETUP
# ══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SETUP COMPLETE")
print("=" * 70)

for db in [METADATA_DB, RESULTS_DB]:
    tables = [t['tableName'] for t in spark.sql(f"SHOW TABLES IN {db}").collect()]
    print(f"\n  {db} ({len(tables)} tables):")
    for t in sorted(tables):
        print(f"    {t}")

print(f"\n  Stream '{stream_name}' registered with {len(primary_key_columns)} PK columns")
print("=" * 70)
print(f"\n  NEXT -> Run 02_dynamic_column_mapper (stream_name={stream_name})")