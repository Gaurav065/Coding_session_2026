# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 02e — Landing: CUSTOMER Domain
# Files:
#   CustomerMgmt.xml  — B1 only, nested XML, flattened to wide schema
#   Customer.txt      — B2/B3 only, 33-field pipe-delimited CDC
#   Prospect.json     — all batches, deeply-nested JSON (22 fields) + CSV fallback
#   WatchHistory.txt  — all batches, 4 cols B1 / 6 cols B2-B3 (normalized)
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
# Evict any stale 'modules' cached from other repos on this shared cluster
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'):
        del sys.modules[_k]
sys.path.insert(0, _root)

from modules.config_loader import load_config, raw_batch_path, landing_volume_path, apply_spark_conf
from modules.audit_utils import add_landing_audit
from modules.delta_utils import write_landing, landing_already_exists
from modules.operations import log_row_count
import modules.schema_registry as SR
from pyspark.sql import functions as F

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "1")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("prospect_format", "json")   # "json" or "csv"

BATCH_ID = dbutils.widgets.get("batch_id")
RUN_ID = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]
PROSPECT_FMT = dbutils.widgets.get("prospect_format")

BATCH_PATH = raw_batch_path(cfg, BATCH_ID)
OPS_AUDIT = f"{cfg['catalog']['name']}.operations.audit_log"

if landing_already_exists(spark, landing_volume_path(cfg, BATCH_ID, "watchhistory")):
    print(f"⏭  Batch {BATCH_ID} already landed — skipping.")
    dbutils.notebook.exit("SKIPPED")

print(f"Batch={BATCH_ID}  RunID={RUN_ID}  ProspectFmt={PROSPECT_FMT}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CustomerMgmt.xml — B1 only
# Parsed with Python's built-in xml.etree.ElementTree (no library install needed).
# Spark reads the file from ADLS (handles auth), collects to driver, then
# ElementTree parses it and we rebuild a Spark DataFrame from a list of dicts.
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID == "1":
    import xml.etree.ElementTree as ET
    from pyspark.sql.types import StringType, StructField, StructType

    SOURCE_FILE = "CustomerMgmt.xml"
    raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"

    def _txt(elem, path):
        node = elem.find(path)
        return node.text if node is not None else None

    def _attr(elem, attr):
        return elem.get(attr)

    # binaryFile reads the whole file as a single bytes row — uses Spark/ADLS
    # credentials so no permission issues, and avoids the collect()+join OOM.
    xml_bytes = spark.read.format("binaryFile").load(raw_path).collect()[0].content
    root = ET.fromstring(bytes(xml_bytes))

    # Strip namespace prefixes so we can use plain tag names regardless of
    # whether the file declares xmlns:TPCDI="..." and uses qualified tags.
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

    print(f"Root tag: {root.tag}  |  First child: {root[0].tag if len(root) else 'none'}")

    CM_SCHEMA = StructType([StructField(c, StringType(), True) for c in [
        "ActionType","ActionTS","C_ID","C_TAX_ID","C_GNDR","C_TIER","C_DOB",
        "C_L_NAME","C_F_NAME","C_M_NAME","C_ADLINE1","C_ADLINE2","C_ZIPCODE",
        "C_CITY","C_STATE_PROV","C_CTRY","C_PRIM_EMAIL","C_ALT_EMAIL",
        "C_CTRY_1","C_AREA_1","C_LOCAL_1","C_EXT_1",
        "C_CTRY_2","C_AREA_2","C_LOCAL_2","C_EXT_2",
        "C_CTRY_3","C_AREA_3","C_LOCAL_3","C_EXT_3",
        "C_LCL_TX_ID","C_NAT_TX_ID","CA_ID","CA_TAX_ST","CA_B_ID","CA_NAME",
    ]])

    rows = []
    for action in root.findall("Action"):
        cust  = action.find("Customer")
        p1    = (cust.find("ContactInfo/C_PHONE_1") if cust is not None else None) or ET.Element("_")
        p2    = (cust.find("ContactInfo/C_PHONE_2") if cust is not None else None) or ET.Element("_")
        p3    = (cust.find("ContactInfo/C_PHONE_3") if cust is not None else None) or ET.Element("_")
        acct  = (cust.find("Account")               if cust is not None else None) or ET.Element("_")
        rows.append({
            "ActionType":   _attr(action, "ActionType"),
            "ActionTS":     _attr(action, "ActionTS"),
            "C_ID":         _attr(cust, "C_ID")       if cust is not None else None,
            "C_TAX_ID":     _attr(cust, "C_TAX_ID")   if cust is not None else None,
            "C_GNDR":       _attr(cust, "C_GNDR")     if cust is not None else None,
            "C_TIER":       _attr(cust, "C_TIER")     if cust is not None else None,
            "C_DOB":        _attr(cust, "C_DOB")      if cust is not None else None,
            "C_L_NAME":     _txt(cust, "Name/C_L_NAME")        if cust is not None else None,
            "C_F_NAME":     _txt(cust, "Name/C_F_NAME")        if cust is not None else None,
            "C_M_NAME":     _txt(cust, "Name/C_M_NAME")        if cust is not None else None,
            "C_ADLINE1":    _txt(cust, "Address/C_ADLINE1")    if cust is not None else None,
            "C_ADLINE2":    _txt(cust, "Address/C_ADLINE2")    if cust is not None else None,
            "C_ZIPCODE":    _txt(cust, "Address/C_ZIPCODE")    if cust is not None else None,
            "C_CITY":       _txt(cust, "Address/C_CITY")       if cust is not None else None,
            "C_STATE_PROV": _txt(cust, "Address/C_STATE_PROV") if cust is not None else None,
            "C_CTRY":       _txt(cust, "Address/C_CTRY")       if cust is not None else None,
            "C_PRIM_EMAIL": _txt(cust, "ContactInfo/C_PRIM_EMAIL") if cust is not None else None,
            "C_ALT_EMAIL":  _txt(cust, "ContactInfo/C_ALT_EMAIL")  if cust is not None else None,
            "C_CTRY_1":     _txt(p1, "C_CTRY_CODE"),
            "C_AREA_1":     _txt(p1, "C_AREA_CODE"),
            "C_LOCAL_1":    _txt(p1, "C_LOCAL"),
            "C_EXT_1":      _txt(p1, "C_EXT"),
            "C_CTRY_2":     _txt(p2, "C_CTRY_CODE"),
            "C_AREA_2":     _txt(p2, "C_AREA_CODE"),
            "C_LOCAL_2":    _txt(p2, "C_LOCAL"),
            "C_EXT_2":      _txt(p2, "C_EXT"),
            "C_CTRY_3":     _txt(p3, "C_CTRY_CODE"),
            "C_AREA_3":     _txt(p3, "C_AREA_CODE"),
            "C_LOCAL_3":    _txt(p3, "C_LOCAL"),
            "C_EXT_3":      _txt(p3, "C_EXT"),
            "C_LCL_TX_ID":  _txt(cust, "TaxInfo/C_LCL_TX_ID") if cust is not None else None,
            "C_NAT_TX_ID":  _txt(cust, "TaxInfo/C_NAT_TX_ID") if cust is not None else None,
            "CA_ID":        _attr(acct, "CA_ID"),
            "CA_TAX_ST":    _attr(acct, "CA_TAX_ST"),
            "CA_B_ID":      _txt(acct, "CA_B_ID"),
            "CA_NAME":      _txt(acct, "CA_NAME"),
        })

    df_cm = spark.createDataFrame(rows, schema=CM_SCHEMA)

    lvol_cm = landing_volume_path(cfg, BATCH_ID, "customermgmt")
    df_cm = add_landing_audit(df_cm, BATCH_ID, SOURCE_FILE, RUN_ID)
    count = write_landing(df_cm, lvol_cm)
    log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
                  target_table=lvol_cm, operation="OVERWRITE", rows_affected=count,
                  batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"CustomerMgmt.xml: {count:,} rows")
else:
    print("CustomerMgmt.xml: Batch 1 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Customer.txt — B2/B3 only, 33 fields
# ═══════════════════════════════════════════════════════════════════════════════
if BATCH_ID in ("2", "3"):
    SOURCE_FILE = "Customer.txt"
    raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
    lvol_cust = landing_volume_path(cfg, BATCH_ID, "customer")

    df_cust = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .option("nullValue", "")
        .schema(SR.CUSTOMER)
        .csv(raw_path)
    )
    df_cust = add_landing_audit(df_cust, BATCH_ID, SOURCE_FILE, RUN_ID)
    count = write_landing(df_cust, lvol_cust)
    log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
                  target_table=lvol_cust, operation="OVERWRITE", rows_affected=count,
                  batch_id=BATCH_ID, run_id=RUN_ID)
    print(f"Customer.txt (B{BATCH_ID}): {count:,} rows")
else:
    print("Customer.txt: B2/B3 only — skipping.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# Prospect.json — all batches, 22 flat fields from deeply-nested JSON
# Falls back to Prospect.csv if JSON is unavailable
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_FILE = "prospect.json"            # lowercase on ADLS
raw_json_path = f"{BATCH_PATH}/prospect.json"
raw_csv_path = f"{BATCH_PATH}/Prospect.csv"
lvol_prosp = landing_volume_path(cfg, BATCH_ID, "prospect")

use_csv = PROSPECT_FMT == "csv"
# Auto-detect if JSON doesn't exist
if not use_csv:
    try:
        dbutils.fs.ls(raw_json_path)
    except Exception:
        print("prospect.json not found — falling back to Prospect.csv")
        use_csv = True

if not use_csv:
    # Deep nested JSON: {"prospect_batch": {"prospects": [...]}}
    # Use multiLine=true to read the entire file as one JSON object
    df_raw_json = (
        spark.read
        .option("multiLine", "true")
        .json(raw_json_path)
    )

    # Navigate: prospect_batch.prospects is an array of prospect objects
    df_prosp = df_raw_json.select(
        F.explode("prospect_batch.prospects").alias("p")
    ).select(
        F.col("p.agency_id").alias("agencyid"),
        F.col("p.personal.name.last_name").alias("lastname"),
        F.col("p.personal.name.first_name").alias("firstname"),
        F.col("p.personal.name.middle_initial").alias("middleinitial"),
        F.col("p.personal.demographics.gender").alias("gender"),
        F.col("p.contact.address.line1").alias("addressline1"),
        F.col("p.contact.address.line2").alias("addressline2"),
        F.col("p.contact.address.postal_code").alias("postalcode"),
        F.col("p.contact.address.city").alias("city"),
        F.col("p.contact.address.state").alias("state"),
        F.col("p.contact.address.country").alias("country"),
        F.col("p.contact.phone.full_number").alias("phone"),
        F.col("p.financial.income.annual_income").cast("string").alias("income"),
        F.col("p.lifestyle.assets.number_cars").cast("string").alias("numbercars"),
        F.col("p.lifestyle.family.number_children").cast("string").alias("numberchildren"),
        F.col("p.personal.demographics.marital_status").alias("maritalstatus"),
        F.col("p.personal.demographics.age").cast("string").alias("age"),
        F.col("p.financial.credit.credit_rating").cast("string").alias("creditrating"),
        F.col("p.lifestyle.housing.own_or_rent").alias("ownorrentflag"),
        F.col("p.employment.employer_name").alias("employer"),
        F.col("p.financial.credit.number_credit_cards").cast("string").alias("numbercreditcards"),
        F.col("p.financial.wealth.net_worth").cast("string").alias("networth"),
    )
else:
    # CSV fallback — flat 22 columns, comma-delimited, NO header
    df_prosp = (
        spark.read
        .option("delimiter", ",")
        .option("header", "false")
        .option("nullValue", "")
        .schema(SR.PROSPECT)
        .csv(raw_csv_path)
    )

df_prosp = add_landing_audit(df_prosp, BATCH_ID, SOURCE_FILE, RUN_ID)
count = write_landing(df_prosp, lvol_prosp)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol_prosp, operation="OVERWRITE", rows_affected=count,
              batch_id=BATCH_ID, run_id=RUN_ID)
print(f"Prospect (B{BATCH_ID}): {count:,} rows ({'CSV' if use_csv else 'JSON'})")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# WatchHistory.txt — all batches
# B1: 4 cols → normalize by adding CDC_FLAG='I', CDC_DSN=NULL
# B2/B3: 6 cols (CDC prefix already present)
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_FILE = "WatchHistory.txt"
raw_path = f"{BATCH_PATH}/{SOURCE_FILE}"
lvol_wh = landing_volume_path(cfg, BATCH_ID, "watchhistory")

if BATCH_ID == "1":
    df_wh = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.WATCHHISTORY_B1)
        .csv(raw_path)
    )
    # Normalize to 6-column schema
    df_wh = (
        df_wh
        .withColumn("CDC_FLAG", F.lit("I"))
        .withColumn("CDC_DSN", F.lit(None).cast("string"))
        .select("W_C_ID", "W_S_SYMB", "W_DTS", "W_ACTION", "CDC_FLAG", "CDC_DSN")
    )
else:
    df_wh = (
        spark.read
        .option("delimiter", "|")
        .option("header", "false")
        .schema(SR.WATCHHISTORY_B2B3)
        .csv(raw_path)
        .select("W_C_ID", "W_S_SYMB", "W_DTS", "W_ACTION", "CDC_FLAG", "CDC_DSN")
    )

df_wh = add_landing_audit(df_wh, BATCH_ID, SOURCE_FILE, RUN_ID)
count = write_landing(df_wh, lvol_wh)
log_row_count(spark, OPS_AUDIT, layer="landing", source_table=SOURCE_FILE,
              target_table=lvol_wh, operation="OVERWRITE", rows_affected=count,
              batch_id=BATCH_ID, run_id=RUN_ID)
print(f"WatchHistory (B{BATCH_ID}): {count:,} rows")

print("\n✅ Customer domain landing complete.")
