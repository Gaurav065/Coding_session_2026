# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 05a — Staging: FINWIRE Parser
# Table: staging.finwire_parsed
#
# Parses all fixed-width FINWIRE lines from bronze.finwire into 5 typed
# RecType partitions:
#   CMP          — Company records       (positions 1-554)
#   SEC_CIK      — Security w/ numeric CIK reference
#   SEC_NAME     — Security w/ company name reference
#   FIN_COMPANYID— Financial w/ numeric CIK reference
#   FIN_NAME     — Financial w/ company name reference
#
# co_name_or_cik classification rule (SEC + FIN):
#   purely numeric (trimmed) → CIK variant  (SEC_CIK / FIN_COMPANYID)
#   otherwise                → NAME variant (SEC_NAME / FIN_NAME)
#
# Output uses unionByName(allowMissingColumns=True) so each RecType DataFrame
# only declares its own columns; missing columns auto-fill NULL.
#
# Batch scope: B1 ONLY — FINWIRE is a full historical load, never incremental.
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
from modules.audit_utils import add_staging_audit
from modules.delta_utils import overwrite_table
from modules.operations import log_row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")
BATCH_ID  = dbutils.widgets.get("batch_id")
RUN_ID    = dbutils.widgets.get("run_id") or spark.sql(
    "SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')"
).collect()[0][0]
OPS_AUDIT = tbl(cfg, "operations", "audit_log")
print(f"Batch={BATCH_ID}  RunID={RUN_ID}")

# COMMAND ----------

if BATCH_ID != "1":
    print("FINWIRE is batch 1 only — skipping.")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------

src_fw = tbl(cfg, "bronze", "finwire")
tgt_fw = tbl(cfg, "staging", "finwire_parsed")
df_fw  = spark.table(src_fw)
print(f"bronze.finwire total lines: {df_fw.count():,}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers (ANSI Mode Safe)
# ═══════════════════════════════════════════════════════════════════════════════
def fw(col_name: str, start: int, length: int):
    """Trim a fixed-width substring field (1-based positions)."""
    return F.trim(F.substring(F.col("line"), start, length)).alias(col_name)

def fw_date(col_name: str, start: int, length: int):
    """Parse a fixed-width yyyyMMdd date field; return NULL on invalid input."""
    return F.try_to_date(
        F.trim(F.substring(F.col("line"), start, length)), "yyyyMMdd"
    ).alias(col_name)

def fw_decimal(col_name: str, start: int, length: int, prec: str = "decimal(15,4)"):
    """Extract leading numeric portion of a fixed-width decimal field safely."""
    raw = F.substring(F.col("line"), start, length)
    extracted = F.regexp_extract(raw, r"^\s*(-?\d+\.?\d*)", 1)
    return F.when(
        (F.trim(raw) != "") & (extracted != ""),
        extracted.cast(prec),
    ).alias(col_name)

def fw_bigint(col_name: str, start: int, length: int):
    """Extract leading integer from a fixed-width field safely."""
    raw = F.substring(F.col("line"), start, length)
    extracted = F.regexp_extract(raw, r"^\s*(\d+)", 1)
    return F.when(
        (F.trim(raw) != "") & (extracted != ""),
        extracted.cast("bigint"),
    ).alias(col_name)

def fw_int(col_name: str, start: int, length: int):
    """Extract leading integer and cast to INT safely."""
    raw = F.substring(F.col("line"), start, length)
    extracted = F.regexp_extract(raw, r"^\s*(\d+)", 1)
    return F.when(
        (F.trim(raw) != "") & (extracted != ""),
        extracted.cast("int"),
    ).alias(col_name)

def _eff_date():
    """Effective date = first 8 chars of PTS field (yyyyMMdd)."""
    return F.try_to_date(F.substring(F.col("line"), 1, 8), "yyyyMMdd").alias("effective_date")

def _is_numeric_cik(field_expr):
    """Return True when the trimmed field contains only digits → CIK path."""
    return F.regexp_extract(F.trim(field_expr), r"^(\d+)$", 1) != ""

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CMP — Company records  (pos 19-554)
# ═══════════════════════════════════════════════════════════════════════════════
df_cmp_raw = df_fw.filter(F.trim(F.substring(F.col("line"), 16, 3)) == "CMP")

df_cmp = df_cmp_raw.select(
    F.lit("CMP").alias("rec_type"),
    fw("pts",            1,  15),
    _eff_date(),
    # ── CMP fields ────────────────────────────────────────────────────────────
    fw("company_name",  19,  60),
    fw("cik",           79,  10),
    fw("cmp_status",    89,   4),
    fw("industry_id",   93,   8),
    fw("sp_rating",    101,   9),
    fw_date("founding_date", 110, 8),
    fw("addr_line1",   118,  80),
    fw("addr_line2",   198,  80),
    fw("postal_code",  278,  12),
    fw("city",         290,  25),
    fw("state_prov",   315,  20),
    fw("country",      335,  24),
    fw("ceo_name",     359,  46),
    fw("description",  405, 150),
)
count_cmp = df_cmp.count()
print(f"  CMP rows: {count_cmp:,}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SEC — Security records  (pos 19-222)
# ═══════════════════════════════════════════════════════════════════════════════
df_sec_raw = df_fw.filter(F.trim(F.substring(F.col("line"), 16, 3)) == "SEC")

_co_sec   = F.substring(F.col("line"), 163, 60)          # raw co_name_or_cik field
_sec_type = F.when(_is_numeric_cik(_co_sec), F.lit("SEC_CIK")).otherwise(F.lit("SEC_NAME"))

df_sec = df_sec_raw.select(
    _sec_type.alias("rec_type"),
    fw("pts",            1,  15),
    _eff_date(),
    # ── SEC fields ────────────────────────────────────────────────────────────
    fw("symbol",        19,  15),
    fw("issue_type",    34,   6),
    fw("sec_status",    40,   4),
    fw("sec_name",      44,  70),
    fw_date("ex_date",          114, 8),
    fw_bigint("shares_outstanding", 122, 13),
    fw_date("first_trade",          135, 8),
    fw_date("first_trade_on_exchange", 143, 8),
    fw_decimal("dividend",          151, 12),
    fw("co_name_or_cik", 163, 60),
)
count_sec = df_sec.count()
count_sec_cik  = df_sec.filter(F.col("rec_type") == "SEC_CIK").count()
count_sec_name = count_sec - count_sec_cik
print(f"  SEC rows: {count_sec:,}  (SEC_CIK={count_sec_cik:,}  SEC_NAME={count_sec_name:,})")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# FIN — Financial records  (pos 19-240)
# ═══════════════════════════════════════════════════════════════════════════════
df_fin_raw = df_fw.filter(F.trim(F.substring(F.col("line"), 16, 3)) == "FIN")

_co_fin   = F.substring(F.col("line"), 181, 60)
_fin_type = F.when(_is_numeric_cik(_co_fin), F.lit("FIN_COMPANYID")).otherwise(F.lit("FIN_NAME"))

df_fin = df_fin_raw.select(
    _fin_type.alias("rec_type"),
    fw("pts",           1,  15),
    _eff_date(),
    # ── FIN fields ────────────────────────────────────────────────────────────
    fw_int("fi_year",             19,  4),
    fw_int("fi_qtr",              23,  1),
    fw_date("fi_qtr_start_date",  24,  8),
    fw_date("fi_posting_date",    32,  8),
    fw_decimal("fi_revenue",      40, 17, "decimal(15,2)"),
    fw_decimal("fi_net_earn",     57, 17, "decimal(15,2)"),
    fw_decimal("fi_basic_eps",    74,  9, "decimal(10,2)"),
    fw_decimal("fi_dilut_eps",    83,  9, "decimal(10,2)"),
    fw_decimal("fi_margin",       92,  9, "decimal(10,4)"),
    fw_decimal("fi_inventory",   101, 18, "decimal(15,2)"),
    fw_decimal("fi_assets",      119, 18, "decimal(15,2)"),
    fw_decimal("fi_liability",   137, 18, "decimal(15,2)"),
    fw_bigint("fi_out_basic",    155, 13),
    fw_bigint("fi_out_dilut",    168, 13),
    fw("co_name_or_cik",         181, 60),
)
count_fin = df_fin.count()
count_fin_cid  = df_fin.filter(F.col("rec_type") == "FIN_COMPANYID").count()
count_fin_name = count_fin - count_fin_cid
print(f"  FIN rows: {count_fin:,}  (FIN_COMPANYID={count_fin_cid:,}  FIN_NAME={count_fin_name:,})")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Union all 5 RecType DataFrames
# ═══════════════════════════════════════════════════════════════════════════════
df_parsed = (
    df_cmp
    .unionByName(df_sec,  allowMissingColumns=True)
    .unionByName(df_fin,  allowMissingColumns=True)
)

df_parsed = add_staging_audit(df_parsed, BATCH_ID, RUN_ID)

count_total = overwrite_table(df_parsed, tgt_fw)
print(f"staging.finwire_parsed written: {count_total:,} rows")

log_row_count(spark, OPS_AUDIT, layer="staging", source_table=src_fw,
              target_table=tgt_fw, operation="OVERWRITE",
              rows_affected=count_total, batch_id=BATCH_ID, run_id=RUN_ID)

# COMMAND ----------

print(f"\nFINWIRE staging complete — B1 only.")