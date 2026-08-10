# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 03f — Bronze: ACCOUNT Domain
# Tables:
#   bronze.account          — B2/B3 only (8-col CDC)
#   bronze.cashtransaction  — all batches (normalized 6-col schema)
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
# Account.txt → bronze.account — B2/B3 only
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID in ("2", "3"):
    land_acct = landing_volume_path(cfg, BATCH_ID, "account")
    btbl      = tbl(cfg, "bronze", "account")

    df = spark.read.parquet(land_acct)
    df = landing_to_bronze(df)
    df = cast_all_to_string(df)

    count, status = safe_append_bronze(spark, df, btbl, BATCH_ID, RUN_ID)
    log_row_count(spark, OPS_AUDIT, layer="bronze", source_table="Account.txt",
                  target_table=btbl, operation=status,
                  rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"Account.txt (B{BATCH_ID}) → {btbl}: {status} ({count:,} rows)")
else:
    print("Account.txt: B2/B3 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CashTransaction.txt → bronze.cashtransaction — all batches
# B1 has 1.2M rows
# ═══════════════════════════════════════════════════════════════════════════════
land_ct = landing_volume_path(cfg, BATCH_ID, "cashtransaction")
btbl    = tbl(cfg, "bronze", "cashtransaction")

df_ct = spark.read.parquet(land_ct)
df_ct = landing_to_bronze(df_ct)
df_ct = cast_all_to_string(df_ct)

if BATCH_ID == "1":
    df_ct = df_ct.repartition(20)   # ~60K rows per partition for 1.2M rows

count, status = safe_append_bronze(spark, df_ct, btbl, BATCH_ID, RUN_ID)
log_row_count(spark, OPS_AUDIT, layer="bronze", source_table="CashTransaction.txt",
              target_table=btbl, operation=status,
              rows_affected=count, batch_id=BATCH_ID, run_id=RUN_ID)
print(f"CashTransaction (B{BATCH_ID}) → {btbl}: {status} ({count:,} rows)")

# COMMAND ----------

# ─── Verify cumulative counts ────────────────────────────────────────────────
# Expected CashTransaction: B1=1,203,664 | B1+B2=1,204,301 | B1+B2+B3=1,204,943
ct_total = spark.sql(f"SELECT COUNT(*) FROM {tbl(cfg, 'bronze', 'cashtransaction')}").collect()[0][0]
print(f"bronze.cashtransaction total: {ct_total:,}")
print("\n✅ Account domain bronze ingestion complete.")
