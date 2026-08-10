# Databricks notebook source
# MAGIC %pip install openpyxl

# COMMAND ----------

# MAGIC %md
# MAGIC # 02 — Dynamic Column Mapper
# MAGIC
# MAGIC Auto-maps source columns to target columns using:
# MAGIC 1. **EXACT** — identical column names
# MAGIC 2. **NORMALIZED** — case/whitespace/special char insensitive
# MAGIC 3. **FUZZY** — SequenceMatcher ratio >= 0.75
# MAGIC
# MAGIC Run **once per file pair** (or when columns change).

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════

dbutils.widgets.text("metadata_db", "metadata_db",       "1. Metadata Database")
dbutils.widgets.text("stream_name", "yrforecastn_dc02",  "2. Stream Name")

# COMMAND ----------

import pandas as pd
import re
from difflib import SequenceMatcher
from pyspark.sql.functions import current_timestamp

METADATA_DB = dbutils.widgets.get("metadata_db").strip()
stream_name = dbutils.widgets.get("stream_name").strip()

print(f"  Metadata DB : {METADATA_DB}")
print(f"  Stream      : {stream_name}")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  LOAD REGISTRY
# ══════════════════════════════════════════════════════════════════

reg_df = spark.table(f"{METADATA_DB}.validation_file_registry") \
    .filter(f"stream_name = '{stream_name}' AND is_active = 'Y'") \
    .toPandas()

if reg_df.empty:
    raise ValueError(
        f"No active registration for stream '{stream_name}'.\n"
        f"Run 00_setup_metadata first."
    )

reg = reg_df.iloc[0]
print(f"  Source : {reg['source_file_path']} [{reg['source_sheet']}]")
print(f"  Target : {reg['target_file_path']} [{reg['target_sheet']}]")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  READ EXCEL HEADERS & MAP COLUMNS
# ══════════════════════════════════════════════════════════════════

src_df = pd.read_excel(reg['source_file_path'], sheet_name=reg['source_sheet'], nrows=5)
tgt_df = pd.read_excel(reg['target_file_path'], sheet_name=reg['target_sheet'], nrows=5)

print(f"\n  Source columns ({len(src_df.columns)}): {list(src_df.columns)}")
print(f"  Target columns ({len(tgt_df.columns)}): {list(tgt_df.columns)}")

def _normalize(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower().strip())

def _infer_type(series):
    d = str(series.dtype)
    if 'int' in d:      return 'BIGINT'
    if 'float' in d:    return 'DOUBLE'
    if 'datetime' in d: return 'TIMESTAMP'
    return 'STRING'

# ── Build normalized target lookup ───────────────────────────
tgt_norm = {}
for i, tc in enumerate(tgt_df.columns):
    key = _normalize(tc)
    if key not in tgt_norm:
        tgt_norm[key] = (i, tc)

# ── Try loading SAP schema for enrichment ────────────────────
try:
    sap_schema = spark.table(f"{METADATA_DB}.sap_source_schemas").toPandas()
    sap_fields = dict(zip(sap_schema['field_name'], sap_schema['data_type']))
except Exception:
    sap_fields = {}

# ── Map columns ──────────────────────────────────────────────
matched_targets = set()
mapping_rows = []

for si, sc in enumerate(src_df.columns):
    sap_field = sc if sc in sap_fields else None
    sap_dtype = sap_fields.get(sc, None)

    row = {
        'stream_name': stream_name,
        'source_column_name': sc,
        'source_column_index': si,
        'source_dtype': _infer_type(src_df[sc]),
        'target_column_name': '',
        'target_column_index': -1,
        'target_dtype': '',
        'mapping_method': 'UNMAPPED',
        'sap_field_name': sap_field or '',
        'sap_datatype': sap_dtype or '',
        'is_mapped': 'N',
        'is_active': 'Y'
    }

    # Strategy 1: EXACT match
    if sc in tgt_df.columns and sc not in matched_targets:
        row.update({
            'target_column_name': sc,
            'target_column_index': list(tgt_df.columns).index(sc),
            'target_dtype': _infer_type(tgt_df[sc]),
            'mapping_method': 'EXACT',
            'is_mapped': 'Y'
        })
        matched_targets.add(sc)

    # Strategy 2: NORMALIZED match
    elif _normalize(sc) in tgt_norm and tgt_norm[_normalize(sc)][1] not in matched_targets:
        ti, tc = tgt_norm[_normalize(sc)]
        row.update({
            'target_column_name': tc,
            'target_column_index': ti,
            'target_dtype': _infer_type(tgt_df[tc]),
            'mapping_method': 'NORMALIZED',
            'is_mapped': 'Y'
        })
        matched_targets.add(tc)

    # Strategy 3: FUZZY match (>= 0.75)
    else:
        best_score, best_tc = 0, None
        for tc in tgt_df.columns:
            if tc in matched_targets:
                continue
            score = SequenceMatcher(None, _normalize(sc), _normalize(tc)).ratio()
            if score > best_score:
                best_score, best_tc = score, tc
        if best_score >= 0.75 and best_tc:
            row.update({
                'target_column_name': best_tc,
                'target_column_index': list(tgt_df.columns).index(best_tc),
                'target_dtype': _infer_type(tgt_df[best_tc]),
                'mapping_method': f'FUZZY({best_score:.2f})',
                'is_mapped': 'Y'
            })
            matched_targets.add(best_tc)

    mapping_rows.append(row)

mapping_df = pd.DataFrame(mapping_rows)

# COMMAND ----------

from pyspark.sql.functions import col

# Delete old records
spark.sql(f"""
DELETE FROM {METADATA_DB}.dynamic_column_mapping
WHERE stream_name = '{stream_name}'
""")

# Convert pandas → spark
spark_mapping = spark.createDataFrame(mapping_df)

# Fix datatype mismatch
spark_mapping = spark_mapping \
    .withColumn("source_column_index", col("source_column_index").cast("int")) \
    .withColumn("target_column_index", col("target_column_index").cast("int"))

# Write to Delta
spark_mapping.write \
    .format("delta") \
    .mode("append") \
    .saveAsTable(f"{METADATA_DB}.dynamic_column_mapping")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════════

mapped   = len(mapping_df[mapping_df['is_mapped'] == 'Y'])
unmapped = len(mapping_df[mapping_df['is_mapped'] == 'N'])
exact    = len(mapping_df[mapping_df['mapping_method'] == 'EXACT'])
norm     = len(mapping_df[mapping_df['mapping_method'] == 'NORMALIZED'])
fuzzy    = len(mapping_df[mapping_df['mapping_method'].str.startswith('FUZZY')])

print("\n" + "=" * 60)
print(f"  COLUMN MAPPING — {stream_name}")
print("=" * 60)
print(f"  Total source columns : {len(mapping_df)}")
print(f"  Mapped               : {mapped} ({exact} EXACT + {norm} NORMALIZED + {fuzzy} FUZZY)")
print(f"  Unmapped             : {unmapped}")
if unmapped > 0:
    print(f"  Unmapped columns     : {mapping_df[mapping_df['is_mapped'] == 'N']['source_column_name'].tolist()}")
print("=" * 60)

display(
    spark.table(f"{METADATA_DB}.dynamic_column_mapping")
    .filter(f"stream_name = '{stream_name}'")
    .orderBy("source_column_index")
)
print(f"\n  NEXT -> Run 04_run_validation (stream_name={stream_name})")