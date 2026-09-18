# Databricks notebook source
# MAGIC %md
# MAGIC # JOB_07 — Parse consignment records and assign surrogate keys
# MAGIC
# MAGIC **Source:** `JOB_07.btq`
# MAGIC
# MAGIC Parses the raw records loaded by JOB_06, resolves the point-of-sale
# MAGIC country, and assigns lane surrogate keys to routes not already keyed.

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("CATALOG", "", "Catalog")
dbutils.widgets.text("USR_LAND", "", "Trans-imports schema")
dbutils.widgets.text("USR_CORE", "", "ODS schema")
dbutils.widgets.text("USR_REF", "", "Reference schema")
dbutils.widgets.text("USR_SCHED", "", "Inventory schema")
dbutils.widgets.text("USR_CTRL", "", "Stream-data schema")

catalog = dbutils.widgets.get("CATALOG").strip()
schema_imp = dbutils.widgets.get("USR_LAND").strip()
schema_ods = dbutils.widgets.get("USR_CORE").strip()
schema_ref = dbutils.widgets.get("USR_REF").strip()
schema_inv = dbutils.widgets.get("USR_SCHED").strip()
schema_strm = dbutils.widgets.get("USR_CTRL").strip()

if not all([catalog, schema_imp, schema_ods, schema_ref, schema_inv, schema_strm]):
    raise ValueError("all widgets are required")

raw_tbl       = f"{catalog}.{schema_imp}.CONSGN_RAW"
pre_trans_tbl = f"{catalog}.{schema_imp}.CONSGN_PRE_STG"
trans_tbl     = f"{catalog}.{schema_imp}.CONSGN_STG"
lane_tbl      = f"{catalog}.{schema_imp}.CONSGN_LANE_NEW"
key_tbl       = f"{catalog}.{schema_ods}.LANE_KEY"
site_tbl      = f"{catalog}.{schema_ref}.MT_TERMINAL"
seg_tbl       = f"{catalog}.{schema_inv}.FT_LEG_SCHED"
ctrl_tbl      = f"{catalog}.{schema_strm}.CTRL_MAX_LANE_ID"

# CURRENT_TIMESTAMP(0) — second precision, as in the original
UPD_TMS = "DATE_TRUNC('SECOND', CURRENT_TIMESTAMP())"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Parse raw records
# MAGIC
# MAGIC The two INSERTs differ only in which byte positions they read and where
# MAGIC the marker sits, so they become one `UNION ALL` and a single overwrite.
# MAGIC
# MAGIC `SUBSTRING(x FROM p FOR n)` → `SUBSTRING(x, p, n)`, and `INDEX(x, s)` →
# MAGIC `INSTR(x, s)`. Both are 1-based in Teradata and in Spark, so the
# MAGIC positions carry over unchanged.
# MAGIC
# MAGIC The second-leg date is where this gets interesting: Teradata lets you
# MAGIC add an integer to a DATE. Spark does not — `DATE_ADD` is required.

# COMMAND ----------

pre_trans = spark.sql(f"""
    SELECT DISTINCT
           SUBSTRING(REC_TXT, 7, 3)                          AS ORIG_TERM_CD,
           SUBSTRING(REC_TXT, 10, 3)                         AS DEST_TERM_CD,
           CAST(NULL AS STRING)                              AS VIA_TERM_CD,
           SUBSTRING(REC_TXT, 6, 1)                          AS BKG_ORIG_IND,
           SUBSTRING(REC_TXT, 21, 2)                         AS CARR_1_CD,
           SUBSTRING(REC_TXT, 23, 4)                         AS SRVC_1_NUM,
           TO_DATE(SUBSTRING(REC_TXT, 13, 8), 'yyyyMMdd')    AS DEPT_1_DT,
           CAST(NULL AS STRING)                              AS CARR_2_CD,
           CAST(NULL AS STRING)                              AS SRVC_2_NUM,
           CAST(NULL AS DATE)                                AS DEPT_2_DT,
           REC_TXT,
           CASE WHEN INSTR(REC_TXT, ' REJ') = 27 THEN '1' ELSE '0' END AS ERR_IND,
           {UPD_TMS}                                         AS UPD_TMS
    FROM   {raw_tbl}
    WHERE  INSTR(REC_TXT, ' RDY') = 27
       OR  INSTR(REC_TXT, ' REJ') = 27

    UNION ALL

    SELECT DISTINCT
           SUBSTRING(REC_TXT, 7, 3)                          AS ORIG_TERM_CD,
           SUBSTRING(REC_TXT, 10, 3)                         AS DEST_TERM_CD,
           SUBSTRING(REC_TXT, 27, 3)                         AS VIA_TERM_CD,
           SUBSTRING(REC_TXT, 6, 1)                          AS BKG_ORIG_IND,
           SUBSTRING(REC_TXT, 21, 2)                         AS CARR_1_CD,
           SUBSTRING(REC_TXT, 23, 4)                         AS SRVC_1_NUM,
           TO_DATE(SUBSTRING(REC_TXT, 13, 8), 'yyyyMMdd')    AS DEPT_1_DT,
           SUBSTRING(REC_TXT, 32, 2)                         AS CARR_2_CD,
           SUBSTRING(REC_TXT, 34, 4)                         AS SRVC_2_NUM,
           DATE_ADD(
               TO_DATE(SUBSTRING(REC_TXT, 13, 8), 'yyyyMMdd'),
               CASE WHEN SUBSTRING(REC_TXT, 30, 2) = '99'
                         THEN -1
                         ELSE CAST(SUBSTRING(REC_TXT, 30, 2) AS INT)
                    END
           )                                                 AS DEPT_2_DT,
           REC_TXT,
           CASE WHEN INSTR(REC_TXT, ' REJ') = 38 THEN '1' ELSE '0' END AS ERR_IND,
           {UPD_TMS}                                         AS UPD_TMS
    FROM   {raw_tbl}
    WHERE  INSTR(REC_TXT, ' RDY') = 38
       OR  INSTR(REC_TXT, ' REJ') = 38
""")

(pre_trans.write
    .mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(pre_trans_tbl))

print(f"parsed records: {spark.table(pre_trans_tbl).count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Resolve booking origin
# MAGIC
# MAGIC Two left joins to the same site table, one on origin and one on
# MAGIC destination.
# MAGIC
# MAGIC The `WHERE` clause drops domestic inbound rows using
# MAGIC `SIO.CNTRY_CD <> SID.CNTRY_CD`. Either side can be NULL when a terminal is
# MAGIC missing from the site table, and `NULL <> NULL` is unknown in both
# MAGIC engines — so those rows are dropped in Teradata too. Preserved as written
# MAGIC rather than "fixed" with a null-safe comparison, which would change the
# MAGIC result.

# COMMAND ----------

trans = spark.sql(f"""
    SELECT
           TRA.ORIG_TERM_CD,
           TRA.DEST_TERM_CD,
           TRA.VIA_TERM_CD,
           CASE TRA.BKG_ORIG_IND
                WHEN 'O' THEN SIO.CNTRY_CD
                WHEN 'I' THEN SID.CNTRY_CD
                ELSE 'XX'
           END                                               AS BKG_CNTRY_CD,
           CASE TRA.BKG_ORIG_IND
                WHEN 'O' THEN 1
                WHEN 'I' THEN 2
                ELSE 3
           END                                               AS BKG_ORIG_ID,
           TRA.CARR_1_CD,
           TRA.SRVC_1_NUM,
           TRA.DEPT_1_DT,
           TRA.CARR_2_CD,
           TRA.SRVC_2_NUM,
           TRA.DEPT_2_DT,
           TRA.REC_TXT,
           TRA.ERR_IND,
           {UPD_TMS}                                         AS UPD_TMS
    FROM   {pre_trans_tbl} TRA
    LEFT OUTER JOIN {site_tbl} SIO ON TRA.ORIG_TERM_CD = SIO.TERM_CD
    LEFT OUTER JOIN {site_tbl} SID ON TRA.DEST_TERM_CD = SID.TERM_CD
    WHERE  TRA.BKG_ORIG_IND = 'O'
       OR (TRA.BKG_ORIG_IND = 'I' AND SIO.CNTRY_CD <> SID.CNTRY_CD)
""")

(trans.write
    .mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(trans_tbl))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Drop routes that are already keyed
# MAGIC
# MAGIC The original ran `DELETE ... WHERE EXISTS` against the table it had just
# MAGIC written. A left anti join expresses the same thing without a second pass,
# MAGIC and folds naturally into the next step.

# COMMAND ----------

new_routes = spark.sql(f"""
    SELECT TRA.*
    FROM   {trans_tbl} TRA
    LEFT ANTI JOIN {key_tbl} K
      ON  K.BKG_ORIG_ID        = TRA.BKG_ORIG_ID
      AND K.ORIG_TERM_CD = TRA.ORIG_TERM_CD
      AND K.DEST_TERM_CD = TRA.DEST_TERM_CD
      AND K.LEG_1_DEPT_DT  = TRA.DEPT_1_DT
      AND K.LEG_1_CARR_CD = TRA.CARR_1_CD
      AND K.LEG_1_SRVC_NUM = TRA.SRVC_1_NUM
""")

new_routes.createOrReplaceTempView("new_routes")
print(f"routes needing a new key: {new_routes.count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Assign surrogate keys
# MAGIC
# MAGIC `MAX_LANE_ID + ROW_NUMBER() OVER (ORDER BY ...)` with a `CROSS JOIN` to a
# MAGIC single-row control table carries over directly. The `ORDER BY` has no
# MAGIC business meaning — it exists to make the numbering deterministic, which
# MAGIC matters more here than it did on Teradata because Spark's row order is
# MAGIC not stable across runs.
# MAGIC
# MAGIC The control table must hold exactly one row. If it is empty the cross
# MAGIC join yields nothing and the step silently writes zero rows, so it is
# MAGIC checked rather than assumed.

# COMMAND ----------

ctrl_rows = spark.table(ctrl_tbl).collect()
if len(ctrl_rows) != 1:
    raise ValueError(f"{ctrl_tbl} must hold exactly one row, found {len(ctrl_rows)}")

ond = spark.sql(f"""
    SELECT DISTINCT
           CTL.MAX_LANE_ID + ROW_NUMBER() OVER (ORDER BY TRA.ORIG_TERM_CD,
                                                        TRA.DEST_TERM_CD,
                                                        TRA.DEPT_1_DT,
                                                        TRA.BKG_ORIG_ID,
                                                        TRA.CARR_1_CD,
                                                        TRA.SRVC_1_NUM) AS LANE_ID,
           TRA.BKG_ORIG_ID,
           TRA.BKG_CNTRY_CD,
           TRA.ORIG_TERM_CD,
           TRA.DEST_TERM_CD,
           TRA.VIA_TERM_CD,
           TRA.DEPT_1_DT  AS LEG_1_DEPT_DT,
           TRA.CARR_1_CD     AS LEG_1_CARR_CD,
           TRA.SRVC_1_NUM     AS LEG_1_SRVC_NUM,
           TRA.DEPT_2_DT  AS LEG_2_DEPT_DT,
           TRA.CARR_2_CD     AS LEG_2_CARR_CD,
           TRA.SRVC_2_NUM     AS LEG_2_SRVC_NUM,
           {UPD_TMS}         AS UPD_TMS
    FROM   new_routes TRA
    CROSS JOIN {ctrl_tbl} CTL
""")

(ond.write
    .mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(lane_tbl))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Append to the key table

# COMMAND ----------

spark.sql(f"""
    INSERT INTO {key_tbl}
    ( LANE_ID, BKG_ORIG_ID, BKG_CNTRY_CD, ORIG_TERM_CD, DEST_TERM_CD, VIA_TERM_CD,
      LEG_1_DEPT_DT, LEG_1_CARR_CD, LEG_1_SRVC_NUM,
      LEG_2_DEPT_DT, LEG_2_CARR_CD, LEG_2_SRVC_NUM, UPD_TMS )
    SELECT LANE_ID, BKG_ORIG_ID, BKG_CNTRY_CD, ORIG_TERM_CD, DEST_TERM_CD, VIA_TERM_CD,
           LEG_1_DEPT_DT, LEG_1_CARR_CD, LEG_1_SRVC_NUM,
           LEG_2_DEPT_DT, LEG_2_CARR_CD, LEG_2_SRVC_NUM,
           {UPD_TMS}
    FROM   {lane_tbl}
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Attach the first-leg inventory id
# MAGIC
# MAGIC `MERGE` and `QUALIFY` both exist in Databricks SQL, so this carries over
# MAGIC almost verbatim. Only the alias moves: `KEY` is a reserved word in Spark
# MAGIC SQL and has to be renamed or quoted.

# COMMAND ----------

spark.sql(f"""
    MERGE INTO {key_tbl} AS K
    USING (
        SELECT LEG_ID, CARR_CD, SRVC_NUM, SCHED_DEPT_DT,
               ORIG_TERM_CD, DEST_TERM_CD
        FROM   {seg_tbl}
        QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY CARR_CD, SRVC_NUM, SCHED_DEPT_DT,
                                 ORIG_TERM_CD, DEST_TERM_CD
                    ORDER BY SNAP_TMS DESC) = 1
    ) AS SEG
       ON  K.LEG_1_CARR_CD = SEG.CARR_CD
       AND K.LEG_1_SRVC_NUM = SEG.SRVC_NUM
       AND K.LEG_1_DEPT_DT  = SEG.SCHED_DEPT_DT
       AND K.ORIG_TERM_CD = SEG.ORIG_TERM_CD
       AND COALESCE(K.VIA_TERM_CD, K.DEST_TERM_CD) = SEG.DEST_TERM_CD
    WHEN MATCHED AND K.LEG_1_ID IS NULL THEN
        UPDATE SET K.LEG_1_ID = SEG.LEG_ID
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Refresh the high-water mark

# COMMAND ----------

max_ond = spark.sql(f"""
    SELECT MAX(LANE_ID) AS MAX_LANE_ID,
           {UPD_TMS}   AS UPD_TMS
    FROM   {key_tbl}
""")

(max_ond.write
    .mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(ctrl_tbl))

print(f"new high-water mark: {spark.table(ctrl_tbl).collect()[0]['MAX_LANE_ID']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migration notes
# MAGIC
# MAGIC | Teradata | Databricks |
# MAGIC |---|---|
# MAGIC | `${USR_*}` (five schemas) | widgets resolved into three-part names |
# MAGIC | `DELETE FROM ... ALL` + `INSERT` | `write.mode("overwrite")` |
# MAGIC | two parse `INSERT`s | one `UNION ALL`, one write |
# MAGIC | `SUBSTRING(x FROM p FOR n)` | `SUBSTRING(x, p, n)` — both 1-based |
# MAGIC | `INDEX(x, s)` | `INSTR(x, s)` |
# MAGIC | `CAST(x AS DATE FORMAT 'YYYYMMDD')` | `TO_DATE(x, 'yyyyMMdd')` — note the lowercase pattern |
# MAGIC | `DATE + INTEGER` | `DATE_ADD(date, n)`. Spark rejects the arithmetic form. |
# MAGIC | `CURRENT_TIMESTAMP(0)` | `DATE_TRUNC('SECOND', CURRENT_TIMESTAMP())` |
# MAGIC | `DELETE ... WHERE EXISTS` | `LEFT ANTI JOIN` |
# MAGIC | `MAX_LANE_ID + ROW_NUMBER() OVER (...)` + `CROSS JOIN` | unchanged, plus a guard that the control table holds one row |
# MAGIC | `MERGE` / `QUALIFY` | both supported; only the reserved-word alias changes |
# MAGIC | `COLLECT STATISTICS` | dropped — collected on write, maintained by predictive optimization |
# MAGIC | `.IF ERRORCODE` / `.GOTO` / `.LABEL` | removed; exceptions fail the job |
# MAGIC
# MAGIC **Watch for:**
# MAGIC - `TO_DATE` with `'YYYYMMDD'` instead of `'yyyyMMdd'`. Spark's pattern
# MAGIC   letters are case-sensitive and `Y` is week-based year — it gives the
# MAGIC   wrong answer near a year boundary rather than an error.
# MAGIC - Writing `DEPT_1_DT + offset`. It fails outright in Spark, so it gets
# MAGIC   caught — but only if the notebook is actually run.
# MAGIC - "Fixing" `SIO.CNTRY_CD <> SID.CNTRY_CD` with `<=>` or a `COALESCE`.
# MAGIC   That changes which rows survive.
# MAGIC - Dropping the `ORDER BY` inside `ROW_NUMBER()`, or replacing it with
# MAGIC   `monotonically_increasing_id()`. Key assignment stops being reproducible.
# MAGIC - Running steps 4–7 twice. The key table gets a second copy of every
# MAGIC   route at higher ids. The original had the same flaw; a candidate who
# MAGIC   notices it and says so is doing better than one who silently mirrors it.
