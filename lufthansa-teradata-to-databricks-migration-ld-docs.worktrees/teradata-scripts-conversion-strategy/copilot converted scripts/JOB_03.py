# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_03 — Monthly campaign response summary
# MAGIC
# MAGIC **Source:** `JOB_03.btq`
# MAGIC
# MAGIC Builds the monthly summary work table from the campaign fact table joined
# MAGIC to the campaign aggregate and campaign master. The original ran one INSERT
# MAGIC per contact channel, appending into the same table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_MST", "", "Master schema")
dbutils.widgets.text("USR_CUST", "", "Customer schema")
dbutils.widgets.text("USR_TMPBAT", "", "Temp/batch schema")
dbutils.widgets.text("MIN_YM", "", "First month to process (YYYYMM)")
dbutils.widgets.text("MAX_YM", "", "Last month to process (YYYYMM)")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_mst = dbutils.widgets.get("USR_MST").strip()
schema_cust = dbutils.widgets.get("USR_CUST").strip()
schema_tmpbat = dbutils.widgets.get("USR_TMPBAT").strip()
min_ym = dbutils.widgets.get("MIN_YM").strip()
max_ym = dbutils.widgets.get("MAX_YM").strip()

if not all([catalog, schema_mst, schema_cust, schema_tmpbat, min_ym, max_ym]):
    raise ValueError("all widgets are required")

if not (min_ym.isdigit() and max_ym.isdigit() and len(min_ym) == len(max_ym) == 6):
    raise ValueError("MIN_YM and MAX_YM must be YYYYMM")

fct_tbl = f"{catalog}.{schema_cust}.FT_CMPGN_STORE_M"
agg_tbl = f"{catalog}.{schema_mst}.MT_CAMPAIGN_AGG"
cmp_tbl = f"{catalog}.{schema_mst}.MT_CAMPAIGN"
tgt_tbl = f"{catalog}.{schema_tmpbat}.WD_CMPGN_MON_SUM"

print(f"target: {tgt_tbl}   months: {min_ym}–{max_ym}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Build both channels
# MAGIC
# MAGIC The two INSERTs differ only in the quantity columns selected and the
# MAGIC channel predicate, so they are expressed as one query with a `UNION ALL`.
# MAGIC Writing them as two sequential appends is equally correct; the union is
# MAGIC preferred here because the target is overwritten in a single atomic write
# MAGIC rather than left half-populated if the second append fails.

# COMMAND ----------

df = spark.sql(f"""
    SELECT
        AGG.CMPGN_PLAN_NO,
        AGG.STORE_CD,
        FCT.CMPGN_MM,
        FCT.MEMBER_TYPE_CD,
        FCT.SEND_QTY,
        FCT.RESP_QTY,
        CURRENT_DATE() AS REG_YMD,
        ''             AS REG_USR_ID,
        CURRENT_DATE() AS UPD_YMD,
        ''             AS UPD_USR_ID
    FROM {fct_tbl} FCT
    INNER JOIN {agg_tbl} AGG
        ON  FCT.SEND_STORE_CD = AGG.STORE_CD
        AND FCT.CMPGN_NO      = AGG.PROMO_PLAN_NO
        AND FCT.CMPGN_MM     >= AGG.PERIOD_STA_M
        AND FCT.CMPGN_MM     <= AGG.PERIOD_END_M
    INNER JOIN {cmp_tbl} CMP
        ON  FCT.CMPGN_STORE_CD = CMP.CMPGN_STORE_CD
        AND FCT.CMPGN_NO       = CMP.CMPGN_NO
    WHERE AGG.PLAN_TYPE_CD = '6'
      AND CMP.CH_TYPE_CD   = '1'
      AND FCT.CMPGN_MM BETWEEN {min_ym} AND {max_ym}

    UNION ALL

    SELECT
        AGG.CMPGN_PLAN_NO,
        AGG.STORE_CD,
        FCT.CMPGN_MM,
        FCT.MEMBER_TYPE_CD,
        FCT.MAIL_SEND_QTY,
        FCT.MAIL_RESP_QTY,
        CURRENT_DATE() AS REG_YMD,
        ''             AS REG_USR_ID,
        CURRENT_DATE() AS UPD_YMD,
        ''             AS UPD_USR_ID
    FROM {fct_tbl} FCT
    INNER JOIN {agg_tbl} AGG
        ON  FCT.SEND_STORE_CD = AGG.STORE_CD
        AND FCT.CMPGN_NO      = AGG.PROMO_PLAN_NO
        AND FCT.CMPGN_MM     >= AGG.PERIOD_STA_M
        AND FCT.CMPGN_MM     <= AGG.PERIOD_END_M
    INNER JOIN {cmp_tbl} CMP
        ON  FCT.CMPGN_STORE_CD = CMP.CMPGN_STORE_CD
        AND FCT.CMPGN_NO       = CMP.CMPGN_NO
    WHERE AGG.PLAN_TYPE_CD = '6'
      AND CMP.EMAIL_FLG    = '1'
      AND CMP.CH_TYPE_CD  <> '1'
      AND FCT.CMPGN_MM BETWEEN {min_ym} AND {max_ym}
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Write
# MAGIC
# MAGIC The target was a SET table, so Teradata discarded exact duplicate rows on
# MAGIC insert. Applied here across all columns, not just the primary index, which
# MAGIC is what SET semantics actually mean.
# MAGIC
# MAGIC `PARTITION BY RANGE_N` on `CMPGN_MM` becomes liquid clustering on the same
# MAGIC column. Do **not** translate it to Hive-style `partitionBy` — one directory
# MAGIC per month on this volume produces small files and worse scans than
# MAGIC clustering does.

# COMMAND ----------

df = df.dropDuplicates()

(df.write
   .mode("overwrite")
   .option("overwriteSchema", "true")
   .clusterBy("CMPGN_MM")
   .saveAsTable(tgt_tbl))

print(f"rows written: {spark.table(tgt_tbl).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_*}` schema variables | widgets resolved into three-part names |
# MAGIC | `${MIN_YM}` / `${MAX_YM}` | widgets, validated as `YYYYMM` before use |
# MAGIC | `DROP` + `CREATE` + two `INSERT`s | one `UNION ALL` query, one overwrite |
# MAGIC | `CREATE SET TABLE` | `dropDuplicates()` across all columns |
# MAGIC | `PARTITION BY RANGE_N(... EACH 1, NO RANGE)` | `clusterBy("CMPGN_MM")`. The `NO RANGE` catch-all partition has no equivalent and needs none. |
# MAGIC | `PRIMARY INDEX` | dropped; no equivalent |
# MAGIC | `FALLBACK`, `NO BEFORE/AFTER JOURNAL`, `CHECKSUM = DEFAULT` | dropped — physical storage options with no Delta counterpart |
# MAGIC | `DATE` (bare keyword = current date) | `CURRENT_DATE()` |
# MAGIC | `DATE FORMAT 'YYYYMMDD'` on a column | dropped — a Teradata display format, not a storage type |
# MAGIC | `DECIMAL(7,0)` / `DECIMAL(6,0)` | `DECIMAL(7,0)` / `DECIMAL(6,0)` carry over; keep the precision rather than letting it infer to `BIGINT` |
# MAGIC | `NOT CASESPECIFIC` on the join keys | **semantic gap.** Three joins here are on `NOT CASESPECIFIC` columns. If the data holds mixed case, this conversion returns fewer rows than Teradata. Confirm before sign-off. |
# MAGIC | `.IF ERRORCODE` / `.GOTO` / `.LABEL` | removed; exceptions fail the job |
