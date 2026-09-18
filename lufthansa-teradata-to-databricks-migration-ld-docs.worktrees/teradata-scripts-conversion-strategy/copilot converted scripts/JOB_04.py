# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_04 — Extract the deletion-key work table
# MAGIC
# MAGIC **Source:** `JOB_04.fex`
# MAGIC
# MAGIC The original ran FastExport to write `WT_DELKEY` to a flat file that a
# MAGIC downstream job then read.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_TMPBAT", "", "Temp/batch schema")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_tmpbat = dbutils.widgets.get("USR_TMPBAT").strip()

if not (catalog and schema_tmpbat):
    raise ValueError("CATALOG and USR_TMPBAT are required")

src_tbl = f"{catalog}.{schema_tmpbat}.WT_DELKEY"
exp_tbl = f"{catalog}.{schema_tmpbat}.WT_DELKEY_EXP"

print(f"source: {src_tbl}")
print(f"target: {exp_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Materialise the extract
# MAGIC
# MAGIC The flat file existed only to move rows between two jobs on the same
# MAGIC platform. Both jobs now read the same Delta tables, so the file is
# MAGIC unnecessary — the extract becomes a Delta table the downstream job reads
# MAGIC directly. Writing an actual file here would reintroduce a hand-off the
# MAGIC lakehouse removes.
# MAGIC
# MAGIC Write a file only if something outside Databricks consumes it. In that
# MAGIC case the target is a volume path, not DBFS, and the fixed-width
# MAGIC `FORMAT UNFORMAT` layout has to be reconstructed column by column —
# MAGIC Spark has no fixed-width writer.

# COMMAND ----------

df = spark.sql(f"""
    SELECT
         STORE_CD
        ,ORDER_NO
    FROM {src_tbl}
""")

df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(exp_tbl)

print(f"rows written: {spark.table(exp_tbl).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_TMPBAT}` | widget resolved into a three-part name |
# MAGIC | `.LOGTABLE` | dropped. FastExport's restart log has no counterpart — Delta writes are atomic, so a failed run leaves nothing to restart from. |
# MAGIC | `DROP TABLE ... LG_WT_DELKEY_FEX` (pre-run cleanup) | dropped with the log table it cleaned up |
# MAGIC | `.BEGIN EXPORT` / `.END EXPORT` | dropped — no session wrapper needed |
# MAGIC | `.EXPORT OUTFILE` + `MODE RECORD FORMAT UNFORMAT` | Delta table `WT_DELKEY_EXP`; the fixed-width binary format disappears with the file |
# MAGIC | `.LOGOFF` | dropped |
# MAGIC
# MAGIC **Watch for:** replacing the file with a file — writing CSV to a path and
# MAGIC having the next notebook read it back. That works but keeps a hand-off
# MAGIC that no longer needs to exist, and loses schema and transactionality.
# MAGIC Either answer is defensible if the reasoning is stated; silently emitting
# MAGIC a file because the original had one is not.
