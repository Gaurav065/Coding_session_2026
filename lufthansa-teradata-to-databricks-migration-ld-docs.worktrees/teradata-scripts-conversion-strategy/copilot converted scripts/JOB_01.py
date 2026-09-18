# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_01 — Rebuild the logical-deletion work table
# MAGIC
# MAGIC **Source:** `JOB_01.btq`
# MAGIC
# MAGIC Selects campaigns flagged as logically deleted from the campaign master and
# MAGIC replaces the contents of the deletion work table with them.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_MST", "", "Master schema")
dbutils.widgets.text("USR_TMPBAT", "", "Temp/batch schema")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_mst = dbutils.widgets.get("USR_MST").strip()
schema_tmpbat = dbutils.widgets.get("USR_TMPBAT").strip()

if not (catalog and schema_mst and schema_tmpbat):
    raise ValueError("CATALOG, USR_MST and USR_TMPBAT are all required")

src_tbl = f"{catalog}.{schema_mst}.MT_CAMPAIGN"
tgt_tbl = f"{catalog}.{schema_tmpbat}.WT_LOGICALDEL"

print(f"source: {src_tbl}")
print(f"target: {tgt_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Rebuild WT_LOGICALDEL
# MAGIC
# MAGIC The original dropped and recreated the table on every run. The Delta
# MAGIC equivalent is a single overwrite, which keeps the table (and its grants)
# MAGIC in place. `CREATE OR REPLACE TABLE ... AS SELECT` would also be correct.

# COMMAND ----------

df = spark.sql(f"""
    SELECT
         T1.CMPGN_STORE_CD
        ,T1.CMPGN_NO
    FROM {src_tbl} T1
    WHERE T1.LOGICAL_DEL_FLG = '1'
""")

# The source was a SET table: Teradata silently discarded duplicate rows on
# insert. Delta does not, so the de-duplication has to be explicit or the row
# count will not match the Teradata baseline.
df = df.dropDuplicates(["CMPGN_STORE_CD", "CMPGN_NO"])

df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(tgt_tbl)

print(f"rows written: {spark.table(tgt_tbl).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_TMPBAT}` / `${USR_MST}` | notebook widgets resolved into three-part names |
# MAGIC | `DROP TABLE` + `CREATE TABLE` + `INSERT` | single `write.mode("overwrite")` |
# MAGIC | `CREATE SET TABLE` | no equivalent — explicit `dropDuplicates` on the index columns |
# MAGIC | `UNIQUE PRIMARY INDEX` | not a storage concept in Delta; uniqueness is not enforced. Distribution is automatic, so nothing replaces the PI. Add a post-write uniqueness check if the guarantee matters. |
# MAGIC | `CHARACTER SET LATIN NOT CASESPECIFIC` | **semantic gap.** Teradata compares these columns case-insensitively and ignores trailing blanks; Spark does neither. Joins and filters on these columns can return fewer rows after migration. Not reproduced here — flag it and confirm the real data is single-case. |
# MAGIC | `CHAR(6)` / `CHAR(12)` | `STRING`. Teradata blank-pads CHAR; Spark does not. |
# MAGIC | `.IF ERRORCODE <> 0 THEN .GOTO ERR_PROC` | removed — a failing statement raises and fails the notebook and job. BTEQ needed these only because it does not halt on error. |
# MAGIC | `.QUIT 0` / `.QUIT 8` | job task exit status |
