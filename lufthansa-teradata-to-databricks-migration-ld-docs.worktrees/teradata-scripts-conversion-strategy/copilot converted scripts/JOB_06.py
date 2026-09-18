# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_06 — Load the consignment feed file
# MAGIC
# MAGIC **Source:** `JOB_06.mld`
# MAGIC
# MAGIC Loads each line of the daily consignment feed file into the raw import table
# MAGIC as text. Parsing happens downstream in JOB_07.

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_LAND", "", "Trans-imports schema")
dbutils.widgets.text("DATAFILE", "", "Input file path (volume)")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_imp = dbutils.widgets.get("USR_LAND").strip()
datafile = dbutils.widgets.get("DATAFILE").strip()

if not (catalog and schema_imp and datafile):
    raise ValueError("CATALOG, USR_LAND and DATAFILE are required")

tgt_tbl = f"{catalog}.{schema_imp}.CONSGN_RAW"
rej_tbl = f"{catalog}.{schema_imp}.CONSGN_RAW_REJECT"

MAX_LEN = 3000  # from .FIELD CONTENT 1 VARCHAR(3000)

print(f"input:  {datafile}")
print(f"target: {tgt_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Read
# MAGIC
# MAGIC The layout declares one field covering the whole record, so the file is
# MAGIC read as lines. `FORMAT VARTEXT ';'` names a delimiter, but with a single
# MAGIC field there is nothing to split on — the delimiter only matters if it
# MAGIC appears inside a record, in which case MultiLoad would have taken the text
# MAGIC up to it. Reading whole lines assumes it does not appear. If that
# MAGIC assumption is wrong for this feed, split on `;` and keep the first part.

# COMMAND ----------

src = spark.read.text(datafile).select(F.col("value").alias("REC_TXT"))
src_count = src.count()

if src_count == 0:
    raise ValueError(f"no records found in {datafile}")

print(f"records read: {src_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Quarantine over-long records
# MAGIC
# MAGIC MultiLoad routed records it could not apply to the `ET_` error table
# MAGIC rather than failing the load. A record longer than the declared field is
# MAGIC the case that arises here.

# COMMAND ----------

too_long = F.length("REC_TXT") > F.lit(MAX_LEN)

rejects = src.filter(too_long).select(
    "REC_TXT",
    F.lit("LENGTH_EXCEEDED").alias("ERROR_CD"),
    F.current_timestamp().alias("DETECTED_TMS"),
)
reject_count = rejects.count()

if reject_count:
    (rejects.write
        .mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(rej_tbl))
    print(f"WARNING: {reject_count:,} record(s) quarantined in {rej_tbl}")

clean = src.filter(~too_long)

if clean.count() == 0:
    raise ValueError("every record was rejected")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Drop duplicates and write
# MAGIC
# MAGIC `IGNORE DUPLICATE INSERT ROWS` made MultiLoad discard duplicate rows
# MAGIC silently instead of raising. Delta has no such mode, so it is explicit.
# MAGIC
# MAGIC `CURRENT_TIMESTAMP(0)` is second precision in Teradata; Spark's
# MAGIC `current_timestamp()` is microsecond, so it is truncated to match.

# COMMAND ----------

before = clean.count()
unique = clean.dropDuplicates(["REC_TXT"])
after = unique.count()

print(f"duplicate records ignored: {before - after:,}")

df = unique.select(
    "REC_TXT",
    F.date_trunc("second", F.current_timestamp()).alias("UPD_TMS"),
)

# DELETE ALL + load = full replace, not append.
(df.write
   .mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(tgt_tbl))

print(f"rows loaded: {spark.table(tgt_tbl).count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_LAND}` / `${DATAFILE}` | widgets; the input path is a volume path |
# MAGIC | `DELETE FROM ... ALL` + MultiLoad | `write.mode("overwrite")` |
# MAGIC | `.LOGTABLE`, `WORKTABLES`, `UV_` error table | no equivalent — needed for restart and uniqueness tracking, both handled by Delta's atomic writes |
# MAGIC | `ET_CONSGN_RAW` error table | reject table; the purpose survives even though the mechanism does not |
# MAGIC | `SESSIONS 20` | dropped — a Teradata load-parallelism knob with no counterpart |
# MAGIC | `.LAYOUT` / `.FIELD CONTENT 1 VARCHAR(3000)` | single-column read; the declared width becomes an explicit length check |
# MAGIC | `FORMAT VARTEXT ';'` | assumption documented above, not silently ignored |
# MAGIC | `IGNORE DUPLICATE INSERT ROWS` | `dropDuplicates(["REC_TXT"])` |
# MAGIC | `CURRENT_TIMESTAMP(0)` | `date_trunc("second", current_timestamp())` |
# MAGIC | `COLLECT STATISTICS COLUMN (REC_TXT)` | dropped — Databricks collects statistics on write and predictive optimization maintains them |
# MAGIC | `.LOGOFF` | dropped |
# MAGIC
# MAGIC **Watch for:** dropping the `(0)` from `CURRENT_TIMESTAMP` and leaving
# MAGIC microsecond precision. It passes review easily and breaks any downstream
# MAGIC equality comparison on the timestamp.
