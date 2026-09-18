# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_02 — Roll the calendar's relative-day offsets forward
# MAGIC
# MAGIC **Source:** `JOB_02.btq`
# MAGIC
# MAGIC Finds the current business date (the row where `REL_YMD = 1`), reads that
# MAGIC date's offset, then shifts every row by it so the business date lands on
# MAGIC `REL_YMD = 0`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_CTL", "", "Control schema")
dbutils.widgets.text("DATADATE", "", "Business date override (YYYYMMDD, optional)")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_ctl = dbutils.widgets.get("USR_CTL").strip()
datadate_override = dbutils.widgets.get("DATADATE").strip()

if not (catalog and schema_ctl):
    raise ValueError("CATALOG and USR_CTL are required")

cal_tbl = f"{catalog}.{schema_ctl}.MT_CALENDAR"
print(f"calendar: {cal_tbl}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Current business date
# MAGIC
# MAGIC The original wrote this single value to a file with `.EXPORT FILE` so the
# MAGIC shell could read it back. Here it is collected straight into a Python
# MAGIC variable — no intermediate file.

# COMMAND ----------

# CAST(DATA_YMD AS CHAR(8)) in Teradata renders a DATE as YYYYMMDD.
# CAST(... AS STRING) in Spark renders it as YYYY-MM-DD, which is not the same
# thing and breaks the comparison in step 2.
rows = spark.sql(f"""
    SELECT DATE_FORMAT(DATA_YMD, 'yyyyMMdd') AS DATA_YMD
    FROM {cal_tbl}
    WHERE REL_YMD = 1
""").collect()

if len(rows) != 1:
    raise ValueError(f"expected exactly one row with REL_YMD = 1, found {len(rows)}")

datadate = rows[0]["DATA_YMD"]

# The original allowed an optional 6th argument to override the date.
if datadate_override:
    datadate = datadate_override

print(f"business date: {datadate}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Offset of that date

# COMMAND ----------

# DATA_YMD is a DATE. The original compared it to a YYYYMMDD string and let
# Teradata cast implicitly. Spark casts the *string* to a date instead, and
# '20260316' is not an ISO date literal — it yields NULL, so the comparison
# matches nothing. Format the column instead of relying on the cast.
rows = spark.sql(f"""
    SELECT REL_YMD
    FROM {cal_tbl}
    WHERE DATE_FORMAT(DATA_YMD, 'yyyyMMdd') = '{datadate}'
""").collect()

if len(rows) != 1:
    raise ValueError(f"expected exactly one calendar row for {datadate}, found {len(rows)}")

rel_offset = rows[0]["REL_YMD"]
print(f"offset: {rel_offset}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Shift every row
# MAGIC
# MAGIC Not idempotent: running it twice shifts the calendar twice. The original
# MAGIC had the same property — it relied on the scheduler running it once a day.
# MAGIC Step 1 failing when no row has `REL_YMD = 1` is what stops a blind rerun.

# COMMAND ----------

if rel_offset == 0:
    print("calendar already current — nothing to do")
else:
    spark.sql(f"""
        UPDATE {cal_tbl}
           SET REL_YMD = REL_YMD - ({rel_offset})
    """)
    print(f"calendar shifted by {rel_offset}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_CTL}` | widget resolved into a three-part name |
# MAGIC | `.EXPORT FILE` + shell `cat` into a variable | `.collect()` into a Python variable |
# MAGIC | `CAST(DATA_YMD AS CHAR(8))` | `DATE_FORMAT(DATA_YMD, 'yyyyMMdd')` — `CAST(... AS STRING)` gives `YYYY-MM-DD` |
# MAGIC | `WHERE DATA_YMD = '20260316'` | `WHERE DATE_FORMAT(DATA_YMD, 'yyyyMMdd') = '...'` — Spark will not implicitly cast a non-ISO string to DATE |
# MAGIC | `.EXPORT RESET` | nothing — no export state to reset |
# MAGIC | `${DATADATE}` / `${REL_OFFSET}` substitution | Python f-string into the next statement |
# MAGIC | optional 6th shell argument | optional `DATADATE` widget |
# MAGIC | shell's empty-value checks after each export | explicit row-count assertions |
# MAGIC | `UPDATE` | supported directly on a Delta table |
# MAGIC | `.IF ERRORCODE <> 0 THEN .QUIT 8` | removed — exceptions propagate and fail the job |
# MAGIC
# MAGIC **Watch for:**
# MAGIC - `CAST(DATA_YMD AS STRING)`. Teradata's `CAST(date AS CHAR(8))` gives
# MAGIC   `20260316`; Spark's gives `2026-03-16`. Step 2 then matches nothing.
# MAGIC - Comparing the DATE column directly to the YYYYMMDD string. Teradata
# MAGIC   casts implicitly, Spark does not, and the result is zero rows rather
# MAGIC   than an error. This is the trap in this script.
# MAGIC - The two `.collect()` calls return one row each. Anyone who skips the
# MAGIC   count check and indexes `[0]` blindly gets a confusing `IndexError`
# MAGIC   instead of a clear failure — which is what catches the two problems
# MAGIC   above.
