# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_10 — Contract renewal prospect list
# MAGIC
# MAGIC **Source:** `JOB_10.btq`
# MAGIC
# MAGIC Selects contracts whose next renewal falls in a future month, where the
# MAGIC customer has used the service often enough recently, and writes them to the
# MAGIC prospect table with the approach month set a year ahead of renewal.

# COMMAND ----------

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_CUST", "", "Customer schema")
dbutils.widgets.text("USR_CTL", "", "Control schema")
dbutils.widgets.text("USR_TMPBAT", "", "Temp/batch schema")
dbutils.widgets.text("YYYYMM", "", "Processing month (YYYYMM)")
dbutils.widgets.text("SEG_CD", "", "Segment code")
dbutils.widgets.text("RANK_CD", "", "Rank code")
dbutils.widgets.text("LVL", "", "Level")
dbutils.widgets.text("LOOKBACK_M", "", "Service window in months (negative)")
dbutils.widgets.text("MIN_SRVC_CNT", "", "Minimum service visits")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_cust = dbutils.widgets.get("USR_CUST").strip()
schema_ctl = dbutils.widgets.get("USR_CTL").strip()
schema_tmpbat = dbutils.widgets.get("USR_TMPBAT").strip()
yyyymm = dbutils.widgets.get("YYYYMM").strip()
seg_cd = dbutils.widgets.get("SEG_CD").strip()
rank_cd = dbutils.widgets.get("RANK_CD").strip()
lvl = dbutils.widgets.get("LVL").strip()
lookback_m = dbutils.widgets.get("LOOKBACK_M").strip()
min_srvc_cnt = dbutils.widgets.get("MIN_SRVC_CNT").strip()

if not all([catalog, schema_cust, schema_ctl, schema_tmpbat, yyyymm,
            seg_cd, rank_cd, lvl, lookback_m, min_srvc_cnt]):
    raise ValueError("all widgets are required")

if not (yyyymm.isdigit() and len(yyyymm) == 6):
    raise ValueError("YYYYMM must be six digits")

lvl = int(lvl)
lookback_m = int(lookback_m)
min_srvc_cnt = int(min_srvc_cnt)

contract_tbl = f"{catalog}.{schema_cust}.MT_CONTRACT"
customer_tbl = f"{catalog}.{schema_cust}.MT_CUSTOMER"
service_tbl  = f"{catalog}.{schema_cust}.FT_SERVICE_HIST"
period_tbl   = f"{catalog}.{schema_ctl}.MT_PERIOD"
tgt_tbl      = f"{catalog}.{schema_tmpbat}.WD_RENEWAL_PROSPECT"

print(f"target: {tgt_tbl}   month: {yyyymm}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Select prospects
# MAGIC
# MAGIC Four things in the original need rewriting rather than translating:
# MAGIC
# MAGIC 1. `) AS T5 (YM)` names the derived table's columns after the fact. Spark
# MAGIC    has no such syntax — the alias moves inside the subquery's `SELECT`.
# MAGIC    Same for `) AS HSI1 (CUST_NO, CONTR_SEQ, SRVC_CNT)`.
# MAGIC 2. `CAST((YM(FORMAT '9(6)')) AS CHAR(6))` renders a number as a six-digit
# MAGIC    zero-padded string. Here it is joined to a six-character substring, so
# MAGIC    the padding matters — this `FORMAT` is doing conversion work, unlike the
# MAGIC    display-only `FORMAT` clauses on column definitions elsewhere.
# MAGIC 3. `AND PROSPECT > ${YYYYMM}` refers to a `SELECT` alias from the same
# MAGIC    query. Teradata allows it; Spark does not, so the expression is
# MAGIC    repeated in the `WHERE`.
# MAGIC 4. `GROUP BY 1` in the period subquery is positional. It works in Spark,
# MAGIC    but the column is named here for clarity.

# COMMAND ----------

df = spark.sql(f"""
    WITH T5 AS (
        SELECT LPAD(CAST(YM AS STRING), 6, '0') AS YM
        FROM {period_tbl}
        GROUP BY YM
    ),
    HSI1 AS (
        SELECT
             CUST_NO
            ,CONTR_SEQ
            ,COUNT(*) AS SRVC_CNT
        FROM {service_tbl}
        WHERE SRVC_YMD >= ADD_MONTHS(TO_DATE(CONCAT('{yyyymm}', '01'), 'yyyyMMdd'), {lookback_m})
          AND SRVC_TYPE_CD = 8
        GROUP BY CUST_NO, CONTR_SEQ
        HAVING COUNT(*) >= {min_srvc_cnt}
    )
    SELECT
         CAST(CAST(SUBSTRING(T2.NEXT_RENEW_YMD, 1, 6) AS DECIMAL(6,0)) - 100
              AS DECIMAL(6,0))            AS PROSPECT_YM
        ,T3.HOME_STORE_CD                 AS APPR_STORE_CD
        ,'{seg_cd}'                       AS SEG_CD
        ,'{rank_cd}'                      AS RANK_CD
        ,CAST({lvl} AS DECIMAL(1,0))      AS LVL
        ,T2.CUST_NO
        ,T2.CONTR_SEQ
        ,CAST(2 AS DECIMAL(1,0))          AS APPR_TYPE
        ,CURRENT_DATE()                   AS REG_YMD
        ,CAST('' AS STRING)               AS REG_USR_ID
        ,CURRENT_DATE()                   AS UPD_YMD
        ,CAST('' AS STRING)               AS UPD_USR_ID
    FROM {contract_tbl} T2
    INNER JOIN T5
        ON SUBSTRING(T2.NEXT_RENEW_YMD, 1, 6) = T5.YM
    INNER JOIN {customer_tbl} T3
        ON T2.CUST_NO = T3.CUST_NO
    INNER JOIN HSI1
        ON  T2.CUST_NO   = HSI1.CUST_NO
        AND T2.CONTR_SEQ = HSI1.CONTR_SEQ
    WHERE T2.CLOSED_FLG = '0'
      AND CAST(SUBSTRING(T2.NEXT_RENEW_YMD, 1, 6) AS DECIMAL(6,0)) - 100 > {yyyymm}
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Append
# MAGIC
# MAGIC The original was a plain `INSERT` into a table it did not clear first, so
# MAGIC this appends. It is therefore **not** safe to rerun — a second run adds the
# MAGIC same rows again. The original had the same property and relied on the
# MAGIC scheduler running it once. Worth flagging rather than silently changing to
# MAGIC an overwrite, which would discard rows written by any earlier job.

# COMMAND ----------

df.write.mode("append").saveAsTable(tgt_tbl)

print(f"rows appended: {df.count()}")
print(f"table now holds: {spark.table(tgt_tbl).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_*}` schema variables | widgets resolved into three-part names |
# MAGIC | `${YYYYMM}`, `${SEG_CD}`, `${RANK_CD}`, `${LVL}`, `${LOOKBACK_M}`, `${MIN_SRVC_CNT}` | widgets, validated before use |
# MAGIC | `) AS T5 (YM)` and `) AS HSI1 (...)` derived-table column lists | aliases moved inside the subquery; expressed as CTEs |
# MAGIC | `CAST((YM(FORMAT '9(6)')) AS CHAR(6))` | `LPAD(CAST(YM AS STRING), 6, '0')` — conversion, not display |
# MAGIC | `SUBSTRING(x FROM 1 FOR 6)` | `SUBSTRING(x, 1, 6)` |
# MAGIC | `CAST('...01' AS DATE FORMAT 'YYYYMMDD')` | `TO_DATE(..., 'yyyyMMdd')` — lowercase pattern |
# MAGIC | `ADD_MONTHS(date, n)` | `ADD_MONTHS(date, n)` — same in both |
# MAGIC | `GROUP BY 1` (positional) | named column |
# MAGIC | `HAVING COUNT(*) >= n` | unchanged |
# MAGIC | `AND PROSPECT > ${YYYYMM}` (SELECT alias in WHERE) | expression repeated in the `WHERE` |
# MAGIC | bare `DATE` keyword | `CURRENT_DATE()` |
# MAGIC | `''` literal | `CAST('' AS STRING)` |
# MAGIC | plain `INSERT` into an uncleared table | `write.mode("append")` |
# MAGIC | `.IF ERRORCODE` / `.GOTO` / `.LABEL` | removed; exceptions fail the job |
# MAGIC
# MAGIC **Watch for:**
# MAGIC - Leaving `PROSPECT` in the `WHERE`. Spark raises an unresolved-column
# MAGIC   error, so this is caught — but only by running it.
# MAGIC - Writing `) AS T5 (YM)` through unchanged. Also a parse error.
# MAGIC - `'YYYYMMDD'` instead of `'yyyyMMdd'` in `TO_DATE`. Silently wrong near a
# MAGIC   year boundary; the service window shifts by a year.
# MAGIC - Changing the append to an overwrite to make it rerunnable. That is a
# MAGIC   behaviour change, not a translation — flag it, don't apply it.
