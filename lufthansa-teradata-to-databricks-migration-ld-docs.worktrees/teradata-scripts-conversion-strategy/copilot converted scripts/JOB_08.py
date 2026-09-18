# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_08 — Load the vehicle registration extract
# MAGIC
# MAGIC **Source:** `JOB_08.mld`
# MAGIC
# MAGIC Loads a semicolon-delimited file with a header line into the raw import
# MAGIC table. Every field stays text; typing happens downstream.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_LAND", "", "Trans-imports schema")
dbutils.widgets.text("DATAFILE", "", "Input file path (volume)")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_imp = dbutils.widgets.get("USR_LAND").strip()
datafile = dbutils.widgets.get("DATAFILE").strip()

if not (catalog and schema_imp and datafile):
    raise ValueError("CATALOG, USR_LAND and DATAFILE are required")

tgt_tbl = f"{catalog}.{schema_imp}.VEHICLE_REG_RAW"
rej_tbl = f"{catalog}.{schema_imp}.VEHICLE_REG_REJECT"

print(f"input:  {datafile}")
print(f"target: {tgt_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Declare the layout
# MAGIC
# MAGIC The schema is declared rather than inferred. The `.LAYOUT` block fixes
# MAGIC both the field order and the count, and inference would silently accept a
# MAGIC file whose columns had moved.
# MAGIC
# MAGIC Every field is `VARCHAR(100)` in the original, so every column is
# MAGIC `StringType` here — including the numeric-looking unit-count and weight fields.
# MAGIC MultiLoad did no conversion and neither does this.

# COMMAND ----------

# in file order, from the .LAYOUT block
FIELDS = [
    "OPER_SHORT_CD",
    "OPER_LONG_CD",
    "OPER_NAME",
    "VEH_SHORT_CD",
    "VEH_LONG_CD",
    "CAPCTY_CONFIG",
    "TOTAL_UNITS",
    "GROSS_WT_OPER_KG",
    "GROSS_WT_CERT_KG",
    "GROSS_WT_TYP_KG",
    "REG_NUM",
    "VEH_MODEL",
]

schema = StructType([StructField(f, StringType(), True) for f in FIELDS])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Read
# MAGIC
# MAGIC `.IMPORT ... FROM 2` skipped the first record, which is the header, so
# MAGIC `header` is `true`. Because an explicit schema is supplied, the header
# MAGIC line is discarded rather than used for column names — which is what is
# MAGIC wanted, since the file's header labels differ from the target's columns.
# MAGIC
# MAGIC `PERMISSIVE` mode with a corrupt-record column reproduces MultiLoad's
# MAGIC behaviour of routing bad records to the error table instead of failing.

# COMMAND ----------

CORRUPT_COL = "_corrupt_record"
read_schema = StructType(schema.fields + [StructField(CORRUPT_COL, StringType(), True)])

src = (spark.read
    .schema(read_schema)
    .option("sep", ";")
    .option("header", "true")
    .option("encoding", "cp1250")
    .option("mode", "PERMISSIVE")
    .option("columnNameOfCorruptRecord", CORRUPT_COL)
    .csv(datafile))

src.cache()
src_count = src.count()

if src_count == 0:
    raise ValueError(f"no data records found in {datafile}")

print(f"records read: {src_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Quarantine bad records

# COMMAND ----------

rejects = src.filter(F.col(CORRUPT_COL).isNotNull())
reject_count = rejects.count()

if reject_count:
    (rejects.select(
            F.col(CORRUPT_COL).alias("RAW_RECORD"),
            F.lit("PARSE_FAILED").alias("ERROR_CD"),
            F.current_timestamp().alias("DETECTED_TMS"))
        .write.mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(rej_tbl))
    print(f"WARNING: {reject_count:,} record(s) quarantined in {rej_tbl}")

clean = src.filter(F.col(CORRUPT_COL).isNull()).drop(CORRUPT_COL)

if clean.count() == 0:
    raise ValueError("every record was rejected")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Write
# MAGIC
# MAGIC The DML label carried no `IGNORE DUPLICATE INSERT ROWS`, so duplicates
# MAGIC were loaded as-is. No de-duplication here either — adding one would change
# MAGIC the result.

# COMMAND ----------

df = clean.select(
    *FIELDS,
    F.date_trunc("second", F.current_timestamp()).alias("UPD_TMS"),
)

# DELETE ALL + load = full replace, not append.
(df.write
   .mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(tgt_tbl))

print(f"rows loaded: {spark.table(tgt_tbl).count():,}")

src.unpersist()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_LAND}` / `${DATAFILE}` | widgets; the input path is a volume path |
# MAGIC | `DELETE FROM ... ALL` + MultiLoad | `write.mode("overwrite")` |
# MAGIC | `.LOGTABLE`, `WORKTABLES`, `UV_` error table | no equivalent; Delta writes are atomic |
# MAGIC | `ET_VEHICLE_REG` error table | reject table, fed by `PERMISSIVE` mode |
# MAGIC | `SESSIONS 10` | dropped |
# MAGIC | `.LAYOUT` / twelve `VARCHAR(100)` fields | explicit `StructType`, all `StringType` |
# MAGIC | `FORMAT VARTEXT ';'` | `.option("sep", ";")` |
# MAGIC | `.IMPORT ... FROM 2` | `.option("header", "true")` |
# MAGIC | CP1250 input encoding | `.option("encoding", "cp1250")` |
# MAGIC | `CURRENT_TIMESTAMP(0)` | `date_trunc("second", current_timestamp())` |
# MAGIC | no `IGNORE DUPLICATE INSERT ROWS` | no de-duplication — deliberately unlike JOB_06 |
# MAGIC
# MAGIC **Watch for:**
# MAGIC - Leaving out `encoding`. The default is UTF-8, so CP1250 accented
# MAGIC   characters in operator and model names are silently mangled. Nothing
# MAGIC   errors and the row counts match.
# MAGIC - `inferSchema` instead of a declared schema. Unit-count and weight fields
# MAGIC   become numeric, which is a type change the original never made.
# MAGIC - Copying JOB_06's `dropDuplicates` across. This script has no
# MAGIC   `IGNORE DUPLICATE INSERT ROWS`, and adding one loses rows.
# MAGIC - `header=false` because "MultiLoad had no header option". `FROM 2` is
# MAGIC   the header skip.
