# Databricks notebook source
# MAGIC %md
# MAGIC # Run the complete Teradata conversion exercise
# MAGIC
# MAGIC This orchestrator runs setup, then JOB_01 through JOB_10 in dependency
# MAGIC order, and checks the final row counts documented in this folder's README.
# MAGIC Upload `SETUP.py`, this folder, and the source input files to the same
# MAGIC Databricks workspace folder before running.

# COMMAND ----------

dbutils.widgets.text("NOTEBOOK_ROOT", "", "Workspace folder containing the notebooks")
dbutils.widgets.text("CATALOG", "", "Writable Unity Catalog catalog")
dbutils.widgets.text("MIN_YM", "202501", "JOB_03 first month")
dbutils.widgets.text("MAX_YM", "202503", "JOB_03 last month")
dbutils.widgets.text("DATADATE", "", "JOB_02 date override (optional)")
dbutils.widgets.text("YYYYMM", "202601", "JOB_10 processing month")
dbutils.widgets.text("SEG_CD", "RN", "JOB_10 segment")
dbutils.widgets.text("RANK_CD", "A", "JOB_10 rank")
dbutils.widgets.text("LVL", "1", "JOB_10 level")
dbutils.widgets.text("LOOKBACK_M", "-12", "JOB_10 service window")
dbutils.widgets.text("MIN_SRVC_CNT", "3", "JOB_10 minimum visits")

from pathlib import PurePosixPath
from datetime import datetime, timezone
import json

root = dbutils.widgets.get("NOTEBOOK_ROOT").strip().rstrip("/")
catalog = dbutils.widgets.get("CATALOG").strip()
if not root or not catalog:
    raise ValueError("NOTEBOOK_ROOT and CATALOG are required")

def notebook(name):
    return str(PurePosixPath(root) / name)

schemas = {
    "USR_MST": "usr_mst",
    "USR_CUST": "usr_cust",
    "USR_TMPBAT": "usr_tmpbat",
    "USR_CTL": "usr_ctl",
    "USR_LAND": "usr_land",
    "USR_CORE": "usr_core",
    "USR_REF": "usr_ref",
    "USR_SCHED": "usr_sched",
    "USR_CTRL": "usr_ctrl",
}
volume = f"/Volumes/{catalog}/usr_land/landing"

def run(name, args):
    print(f"\n===== {name} =====")
    result = dbutils.notebook.run(notebook(name), 0, args)
    print(result or f"{name} completed")

# SETUP creates schemas, tables, volumes, and all three input files.
run("SETUP", {"CATALOG": catalog})

run("JOB_01", {"CATALOG": catalog, "USR_MST": schemas["USR_MST"],
               "USR_TMPBAT": schemas["USR_TMPBAT"]})
run("JOB_02", {"CATALOG": catalog, "USR_CTL": schemas["USR_CTL"],
               "DATADATE": dbutils.widgets.get("DATADATE").strip()})
run("JOB_03", {"CATALOG": catalog, "USR_MST": schemas["USR_MST"],
               "USR_CUST": schemas["USR_CUST"], "USR_TMPBAT": schemas["USR_TMPBAT"],
               "MIN_YM": dbutils.widgets.get("MIN_YM"),
               "MAX_YM": dbutils.widgets.get("MAX_YM")})
run("JOB_04", {"CATALOG": catalog, "USR_TMPBAT": schemas["USR_TMPBAT"]})
run("JOB_05", {"CATALOG": catalog, "USR_TMPBAT": schemas["USR_TMPBAT"],
               "DATAFILE": f"{volume}/profit_centre.dat"})
run("JOB_06", {"CATALOG": catalog, "USR_LAND": schemas["USR_LAND"],
               "DATAFILE": f"{volume}/consgn_feed.txt"})
run("JOB_07", {"CATALOG": catalog, "USR_LAND": schemas["USR_LAND"],
               "USR_CORE": schemas["USR_CORE"], "USR_REF": schemas["USR_REF"],
               "USR_SCHED": schemas["USR_SCHED"], "USR_CTRL": schemas["USR_CTRL"]})
run("JOB_08", {"CATALOG": catalog, "USR_LAND": schemas["USR_LAND"],
               "DATAFILE": f"{volume}/vehicle_reg.txt"})
run("JOB_09", {"CATALOG": catalog, "USR_CUST": schemas["USR_CUST"],
               "USR_TMPBAT": schemas["USR_TMPBAT"]})
run("JOB_10", {"CATALOG": catalog, "USR_CUST": schemas["USR_CUST"],
               "USR_CTL": schemas["USR_CTL"], "USR_TMPBAT": schemas["USR_TMPBAT"],
               "YYYYMM": dbutils.widgets.get("YYYYMM"),
               "SEG_CD": dbutils.widgets.get("SEG_CD"),
               "RANK_CD": dbutils.widgets.get("RANK_CD"),
               "LVL": dbutils.widgets.get("LVL"),
               "LOOKBACK_M": dbutils.widgets.get("LOOKBACK_M"),
               "MIN_SRVC_CNT": dbutils.widgets.get("MIN_SRVC_CNT")})

# Final acceptance checks. Detailed content checks remain in README.md.
expected = {
    "WT_LOGICALDEL": (schemas["USR_TMPBAT"], 11),
    "MT_CALENDAR": (schemas["USR_CTL"], 31),
    "WD_CMPGN_MON_SUM": (schemas["USR_TMPBAT"], 18),
    "WT_DELKEY_EXP": (schemas["USR_TMPBAT"], 8),
    "WT_PROFITCTR": (schemas["USR_TMPBAT"], 12),
    "CONSGN_RAW": (schemas["USR_LAND"], 9),
    "LANE_KEY": (schemas["USR_CORE"], 8),
    "VEHICLE_REG_RAW": (schemas["USR_LAND"], 10),
    "FT_TXN_DETAIL": (schemas["USR_CUST"], 15),
    "WD_RENEWAL_PROSPECT": (schemas["USR_TMPBAT"], 3),
}
verification = []
for table, (schema, expected_count) in expected.items():
    qualified = f"{catalog}.{schema}.{table}"
    actual = spark.table(qualified).count()
    verification.append({
        "check": f"{qualified} row count",
        "status": "PASS" if actual == expected_count else "FAIL",
        "expected": expected_count,
        "actual": actual,
    })
    if actual != expected_count:
        raise AssertionError(f"{qualified}: expected {expected_count} rows, found {actual}")
    print(f"PASS {qualified}: {actual} rows")

calendar = spark.sql(
    f"SELECT REL_YMD FROM {catalog}.{schemas['USR_CTL']}.MT_CALENDAR "
    "WHERE DATA_YMD = DATE '2026-03-16'"
).collect()
if len(calendar) != 1 or calendar[0]["REL_YMD"] != 0:
    raise AssertionError("MT_CALENDAR: 2026-03-16 must have REL_YMD = 0")
verification.append({
    "check": f"{catalog}.{schemas['USR_CTL']}.MT_CALENDAR 2026-03-16 REL_YMD",
    "status": "PASS",
    "expected": 0,
    "actual": calendar[0]["REL_YMD"],
})

run_timestamp = datetime.now(timezone.utc).isoformat()
report = [{
    "run_timestamp_utc": run_timestamp,
    "catalog": catalog,
    "check": item["check"],
    "status": item["status"],
    "expected": str(item["expected"]),
    "actual": str(item["actual"]),
} for item in verification]
report_df = spark.createDataFrame(report)
report_table = f"{catalog}.{schemas['USR_TMPBAT']}.CONVERSION_VERIFICATION_RESULTS"
report_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(report_table)
report_path = f"{volume}/conversion_verification_results.json"
dbutils.fs.put(report_path, json.dumps(report, indent=2), True)
print(f"Verification table: {report_table}")
print(f"Verification JSON: {report_path}")

print("\nALL CONVERSION JOBS AND FINAL ROW-COUNT CHECKS PASSED")
