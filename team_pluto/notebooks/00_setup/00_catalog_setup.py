# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 00 — Catalog Verification
# The catalog and all schemas are pre-created by the admin team.
# This notebook VERIFIES they exist — it does NOT create anything.
# Run once before the first pipeline execution to confirm the environment.
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

from modules.config_loader import load_config, schema_name, apply_spark_conf

cfg = load_config()
apply_spark_conf(spark, cfg)

CATALOG = cfg["catalog"]["name"]
SCHEMAS = cfg["schemas"]

print(f"Catalog : {CATALOG}")
print(f"UC mode : {cfg['catalog']['use_unity_catalog']}")

# COMMAND ----------

# ─── Set active catalog ──────────────────────────────────────────────────────
spark.sql(f"USE CATALOG `{CATALOG}`")
print(f"Active catalog set to: {CATALOG}")

# COMMAND ----------

# ─── Verify all required schemas exist ──────────────────────────────────────
print(f"\nVerifying schemas in {CATALOG}:")

existing = {row.databaseName for row in spark.sql("SHOW SCHEMAS").collect()}
required = set(SCHEMAS.values())

all_ok = True
for key, schema in sorted(SCHEMAS.items()):
    status = "✅" if schema in existing else "� MISSING"
    print(f"  {status}  {schema:<20}  ({key})")
    if schema not in existing:
        all_ok = False

if all_ok:
    print(f"\n✅ All {len(required)} schemas present — pipeline ready.")
else:
    missing = required - existing
    print(f"\n� Missing schemas: {missing}")
    print("   Contact your admin to create the missing schemas.")
    raise RuntimeError(f"Missing schemas: {missing}")

# COMMAND ----------

# ─── Display full catalog schema listing ─────────────────────────────────────
display(spark.sql("SHOW SCHEMAS"))
