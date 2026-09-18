# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_05 — Load the profit-centre master file
# MAGIC
# MAGIC **Source:** `JOB_05.mld`
# MAGIC
# MAGIC The original used MultiLoad to load a fixed-width file into the work table,
# MAGIC applying one derivation on the way in.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_TMPBAT", "", "Temp/batch schema")
dbutils.widgets.text("DATAFILE", "", "Input file path (volume)")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_tmpbat = dbutils.widgets.get("USR_TMPBAT").strip()
datafile = dbutils.widgets.get("DATAFILE").strip()

if not (catalog and schema_tmpbat and datafile):
    raise ValueError("CATALOG, USR_TMPBAT and DATAFILE are required")

tgt_tbl = f"{catalog}.{schema_tmpbat}.WT_PROFITCTR"
bad_tbl = f"{catalog}.{schema_tmpbat}.WT_PROFITCTR_REJECT"

print(f"input:  {datafile}")
print(f"target: {tgt_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Parse the fixed-width layout
# MAGIC
# MAGIC `.FIELD name * CHAR(n)` means "next n bytes". Spark has no fixed-width
# MAGIC reader, so the file is read as whole lines and sliced by offset. The
# MAGIC offsets are derived from the widths in order — keep them in one place so
# MAGIC the layout stays readable and reviewable against the original.

# COMMAND ----------

# (column name, width) — in file order, from the .LAYOUT block
LAYOUT = [
    ("MGMT_AREA_CD",    4),
    ("VALID_STA_YMD",   8),
    ("VALID_END_YMD",   8),
    ("PROFITCTR_CD",    9),
    ("PROFITCTR_CD_BR", 1),
    ("PROFITCTR_NAME", 40),
    ("CMP_CD",          4),
    ("LOCK_FLG",        1),
]

RECORD_LEN = sum(w for _, w in LAYOUT)
print(f"expected record length: {RECORD_LEN}")

raw = spark.read.text(datafile)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Split good and bad records
# MAGIC
# MAGIC MultiLoad routed unparseable rows to the `ET_` error table instead of
# MAGIC failing the load. That behaviour is reproduced by quarantining short
# MAGIC records rather than letting them silently truncate.

# COMMAND ----------

flagged = raw.withColumn("_ok", F.length("value") >= RECORD_LEN)

rejects = flagged.filter(~F.col("_ok")).drop("_ok")
reject_count = rejects.count()

if reject_count:
    rejects.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(bad_tbl)
    print(f"WARNING: {reject_count} record(s) quarantined in {bad_tbl}")

src = flagged.filter("_ok").drop("_ok")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Slice, derive, load
# MAGIC
# MAGIC Teradata CHAR columns are blank-padded, so every field is right-trimmed.
# MAGIC `PROFITCTR_CD` is the concatenation of the 9-byte code and the 1-byte
# MAGIC branch suffix — and it is the concatenation that is trimmed, not the
# MAGIC parts, otherwise a short code loses its alignment with the suffix.

# COMMAND ----------

pos = 1
cols = []
for name, width in LAYOUT:
    cols.append(F.substring("value", pos, width).alias(f"_{name}"))
    pos += width

sliced = src.select(*cols)

df = sliced.select(
    F.rtrim("_MGMT_AREA_CD").alias("MGMT_AREA_CD"),
    F.rtrim("_VALID_STA_YMD").alias("VALID_STA_YMD"),
    F.rtrim("_VALID_END_YMD").alias("VALID_END_YMD"),
    F.rtrim(F.concat("_PROFITCTR_CD", "_PROFITCTR_CD_BR")).alias("PROFITCTR_CD"),
    F.rtrim("_PROFITCTR_CD_BR").alias("PROFITCTR_CD_BR"),
    F.rtrim("_PROFITCTR_NAME").alias("PROFITCTR_NAME"),
    F.rtrim("_CMP_CD").alias("CMP_CD"),
    F.rtrim("_LOCK_FLG").alias("LOCK_FLG"),
)

# The original emptied the target with DELETE ... ALL before loading, so the
# load is a full replace, not an append.
df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(tgt_tbl)

print(f"rows loaded: {spark.table(tgt_tbl).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_TMPBAT}` / `${DATAFILE}` | widgets; the input path is a volume path |
# MAGIC | `DELETE FROM ... ALL` + MultiLoad | `write.mode("overwrite")` |
# MAGIC | `.LOGTABLE` and the `ET_` / `WT_` / `UV_` tables | no equivalent. MultiLoad needed them to restart a partially-applied load; Delta writes are atomic. The `ET_` error table's *purpose* survives as the reject table. |
# MAGIC | `.LAYOUT` / `.FIELD name * CHAR(n)` | `substring` by computed offset — Spark has no fixed-width reader |
# MAGIC | `:FIELD` bind variables | DataFrame columns |
# MAGIC | `:PROFITCTR_CD\|\|:PROFITCTR_CD_BR` | `concat(...)`, trimmed after concatenation |
# MAGIC | `.BEGIN MLOAD` / `.END MLOAD` / `.LOGOFF` | dropped |
# MAGIC | `FORMAT UNFORMAT` | raw byte records; read as text and sliced |
# MAGIC
# MAGIC **Watch for:**
# MAGIC - Trimming `PROFITCTR_CD` and `PROFITCTR_CD_BR` separately before joining
# MAGIC   them. That changes the value whenever the code is shorter than 9 bytes.
# MAGIC - Using `read.csv` with a delimiter. There is no delimiter — the layout is
# MAGIC   positional.
# MAGIC - Dropping short records silently, or letting `substring` pad them out,
# MAGIC   instead of quarantining them the way the `ET_` table did.
# MAGIC - Multi-byte character sets: the original loaded with a Shift-JIS session
# MAGIC   character set, where `CHAR(n)` counts bytes, not characters.
# MAGIC   `substring` counts characters. For an ASCII file these agree; for a
# MAGIC   multi-byte one they do not, and the layout must be sliced on bytes.
