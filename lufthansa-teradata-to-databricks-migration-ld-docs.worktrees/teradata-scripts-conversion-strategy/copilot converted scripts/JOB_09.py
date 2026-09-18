# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_09 — Delete transaction detail for merged customers
# MAGIC
# MAGIC **Source:** `JOB_09.btq`
# MAGIC
# MAGIC Removes rows from the transaction detail table whose customer and sequence
# MAGIC appear as a merge source in the staged merge-key table.

# COMMAND ----------

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_CUST", "", "Customer schema")
dbutils.widgets.text("USR_TMPBAT", "", "Temp/batch schema")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_cust = dbutils.widgets.get("USR_CUST").strip()
schema_tmpbat = dbutils.widgets.get("USR_TMPBAT").strip()

if not (catalog and schema_cust and schema_tmpbat):
    raise ValueError("CATALOG, USR_CUST and USR_TMPBAT are all required")

tgt_tbl = f"{catalog}.{schema_cust}.FT_TXN_DETAIL"
key_tbl = f"{catalog}.{schema_tmpbat}.WT_MERGEKEY"

print(f"deleting from: {tgt_tbl}")
print(f"merge keys:    {key_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reading the original
# MAGIC
# MAGIC The `WHERE` clause names `WT_MERGEKEY` even though it never appears in a
# MAGIC `FROM`. This is Teradata's implicit correlated delete: naming a second
# MAGIC table in the predicate joins it in silently, and a target row is deleted
# MAGIC when **at least one** matching row exists there.
# MAGIC
# MAGIC Spark rejects the form outright, so it has to be rewritten. `EXISTS` is
# MAGIC the closest match — it preserves "at least one", so a merge key listed
# MAGIC twice still deletes the target row once.

# COMMAND ----------

before = spark.table(tgt_tbl).count()

spark.sql(f"""
    DELETE FROM {tgt_tbl} AS A
    WHERE EXISTS (
        SELECT 1
        FROM {key_tbl} AS B
        WHERE A.CUST_NO = B.SRC_CUST_NO
          AND A.TXN_SEQ = B.SRC_TXN_SEQ
    )
""")

after = spark.table(tgt_tbl).count()
print(f"rows before: {before}   after: {after}   deleted: {before - after}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_CUST}` / `${USR_TMPBAT}` | widgets resolved into three-part names |
# MAGIC | implicit correlated `DELETE` (second table named only in the `WHERE`) | `DELETE ... WHERE EXISTS (SELECT 1 FROM ...)`. Spark has no equivalent of the implicit form. |
# MAGIC | fully-qualified column references (`db.table.column`) | table aliases |
# MAGIC | `.IF ERRORCODE <> 0 THEN .GOTO ERR_PROC` | removed; exceptions fail the job |
# MAGIC
# MAGIC **Watch for:**
# MAGIC - Dropping either half of the two-part key. `CUST_NO` alone matches more
# MAGIC   rows than intended and deletes data that should survive. The row count
# MAGIC   is the only signal.
# MAGIC - Reading the statement as an unconditional delete. It is not — the
# MAGIC   predicate is doing real work even though the second table looks
# MAGIC   decorative.
# MAGIC - Not idempotent in the harmful direction, but safe to rerun: a second run
# MAGIC   finds nothing left to delete.
