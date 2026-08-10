# Databricks notebook source
# MAGIC %pip install openpyxl

# COMMAND ----------

# MAGIC %md
# MAGIC # 04 — Run Source <-> Target Validation (Production)
# MAGIC
# MAGIC Runs all **17 validation checks** using PK-based comparison.
# MAGIC
# MAGIC ### Architecture
# MAGIC | Feature | Details |
# MAGIC |---------|---------|
# MAGIC | PK-Based Matching | CHECK 8, 10, 14, 15 join on normalized PK |
# MAGIC | Column Order Alignment | Target columns auto-reordered to match source |
# MAGIC | SAP Normalization | Leading zeros, SAP blank `000000`, NULL->0, date formats |
# MAGIC | No Pre-Sorting | Raw data passed directly; PK join handles alignment |
# MAGIC | NaN Promotion | `int64->float64` from NaN treated as PASS in CHECK 3 |
# MAGIC | PK Hash (CHECK 10) | Hashes only PK columns, not all columns |
# MAGIC
# MAGIC ### 17 Checks
# MAGIC | # | Check | PK? | # | Check | PK? |
# MAGIC |---|-------|-----|---|-------|-----|
# MAGIC | 1 | Row Count | — | 10 | PK Hash Comparison | Yes |
# MAGIC | 2 | Column Structure | — | 11 | Source - Target (A-B) | Yes |
# MAGIC | 3 | Data Types | — | 12 | Target - Source (B-A) | Yes |
# MAGIC | 4 | Null Counts | — | 13 | PK Value Drill-Down | Yes |
# MAGIC | 5 | Numeric Aggregates | — | 14 | Column Success % | Yes |
# MAGIC | 6 | Distinct Counts | — | 15 | Mismatch Detail+PK | Yes |
# MAGIC | 7 | Duplicates | — | 16 | PK Issue Summary | Yes |
# MAGIC | 8 | Row Data (PK) | Yes | 17 | MINUS Query | — |
# MAGIC | 9 | Value Distribution | — |  |  |  |
# MAGIC
# MAGIC ### Prerequisites
# MAGIC 1. `00_setup_metadata` — creates tables, registers file pair
# MAGIC 2. `02_dynamic_column_mapper` — builds column mapping
# MAGIC 3. `03_validation_functions` — loaded via `%run` below

# COMMAND ----------

# MAGIC %run ./03_validation_functions

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════

dbutils.widgets.text("metadata_db", "metadata_db",       "1. Metadata Database")
dbutils.widgets.text("results_db",  "results_db",        "2. Results Database")
dbutils.widgets.text("stream_name", "yrforecastn_dc02",  "3. Stream Name (blank=all active)")

# COMMAND ----------

import pandas as pd
import uuid
from datetime import datetime

METADATA_DB   = dbutils.widgets.get("metadata_db").strip()
RESULTS_DB    = dbutils.widgets.get("results_db").strip()
stream_filter = dbutils.widgets.get("stream_name").strip()

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  LOAD REGISTRY & MAPPING
# ══════════════════════════════════════════════════════════════════

if stream_filter:
    registry = spark.table(f"{METADATA_DB}.validation_file_registry") \
        .filter(f"is_active = 'Y' AND stream_name = '{stream_filter}'").toPandas()
else:
    registry = spark.table(f"{METADATA_DB}.validation_file_registry") \
        .filter("is_active = 'Y'").toPandas()

if registry.empty:
    raise ValueError(f"No active file pairs found. Run 00_setup_metadata first.")

all_mappings = spark.table(f"{METADATA_DB}.dynamic_column_mapping") \
    .filter("is_active = 'Y'").toPandas()

print(f"  File pairs to validate : {len(registry)}")
print(f"  Column mappings loaded : {len(all_mappings)}")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  RUN ALL 17 CHECKS (per stream)
# ══════════════════════════════════════════════════════════════════

overall_results = []

for _, reg in registry.iterrows():
    stream = reg['stream_name']
    run_id = f"{stream}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

    # ── Parse config from registry ────────────────────────────
    pk_str = reg.get('primary_key_columns', '')
    pk_columns = [c.strip() for c in str(pk_str).split(',') if c.strip()] \
        if pd.notna(pk_str) and str(pk_str).strip() else []

    excl_str = reg.get('exclude_columns', '')
    user_exclude_list = [c.strip() for c in str(excl_str).split(',') if c.strip()] \
        if pd.notna(excl_str) and str(excl_str).strip() else []

    precision = int(reg.get('numeric_precision', 2)) \
        if pd.notna(reg.get('numeric_precision', None)) else 2

    print(f"\n{'='*70}")
    print(f"  VALIDATING: {stream}")
    print(f"{'='*70}")
    print(f"  Run ID          : {run_id}")
    print(f"  Source           : {reg['source_file_path']} [{reg['source_sheet']}]")
    print(f"  Target           : {reg['target_file_path']} [{reg['target_sheet']}]")
    print(f"  PK Columns ({len(pk_columns):>2d})  : {pk_columns}")
    print(f"  Exclude Columns  : {user_exclude_list if user_exclude_list else '(none)'}")
    print(f"  Numeric Precision: {precision}")

    # ══════════════════════════════════════════════════════════
    #  STEP 1: READ EXCEL FILES (raw — no mutation)
    # ══════════════════════════════════════════════════════════
    try:
        print(f"\n  [1/8] Reading files...")
        src_df = pd.read_excel(reg['source_file_path'], sheet_name=reg['source_sheet'])
        tgt_df = pd.read_excel(reg['target_file_path'], sheet_name=reg['target_sheet'])
        print(f"    Source : {src_df.shape[0]:,} rows x {src_df.shape[1]} cols")
        print(f"    Target : {tgt_df.shape[0]:,} rows x {tgt_df.shape[1]} cols")
    except Exception as e:
        print(f"    Error reading files: {e}")
        continue

    # ══════════════════════════════════════════════════════════
    #  STEP 2: COLUMN ORDER ALIGNMENT
    #  SAP and Databricks may store columns in different order.
    #  Reorder target to match source so positional checks
    #  (hash, row data) compare the correct columns.
    # ══════════════════════════════════════════════════════════
    print(f"\n  [2/8] Column order alignment...")

    src_col_set = set(src_df.columns)
    tgt_col_set = set(tgt_df.columns)
    common_cols = src_col_set & tgt_col_set
    src_only_cols = src_col_set - tgt_col_set
    tgt_only_cols = tgt_col_set - src_col_set
    before_match = sum(1 for s, t in zip(src_df.columns, tgt_df.columns) if s == t)

    if common_cols and not src_only_cols and not tgt_only_cols:
        tgt_df = tgt_df[list(src_df.columns)]
        print(f"    Aligned: {before_match}/{len(src_df.columns)} -> {len(src_df.columns)}/{len(src_df.columns)}")
    elif common_cols:
        reordered = [c for c in src_df.columns if c in tgt_col_set] + sorted(tgt_only_cols)
        tgt_df = tgt_df[reordered]
        after_match = sum(1 for s, t in zip(src_df.columns, reordered) if s == t)
        print(f"    Partial: {before_match} -> {after_match}")
        if src_only_cols: print(f"    Source-only: {sorted(src_only_cols)}")
        if tgt_only_cols: print(f"    Target-only: {sorted(tgt_only_cols)}")
    else:
        print(f"    No common columns — skipping reorder")

    # ══════════════════════════════════════════════════════════
    #  STEP 3: LOAD/BUILD COLUMN MAPPING
    # ══════════════════════════════════════════════════════════
    print(f"\n  [3/8] Column mapping...")

    stream_mapping = all_mappings[all_mappings['stream_name'] == stream].copy()

    if stream_mapping.empty:
        print(f"    No saved mapping — auto-mapping by name...")
        import re
        from difflib import SequenceMatcher

        def _norm(name): return re.sub(r'[^a-z0-9]', '', str(name).lower().strip())
        def _dtype(s):
            d = str(s.dtype)
            if 'int' in d: return 'int64'
            if 'float' in d: return 'float64'
            if 'datetime' in d: return 'datetime64'
            return 'str'

        tgt_norm_map = {}
        for i, tc in enumerate(tgt_df.columns):
            k = _norm(tc)
            if k not in tgt_norm_map: tgt_norm_map[k] = (i, tc)

        matched = set()
        rows = []
        for si, sc in enumerate(src_df.columns):
            r = {'stream_name': stream, 'source_column_name': sc,
                 'source_column_index': si, 'source_dtype': _dtype(src_df[sc]),
                 'target_column_name': '', 'target_column_index': -1,
                 'target_dtype': '', 'mapping_method': 'UNMAPPED',
                 'is_mapped': 'N', 'is_active': 'Y'}

            if sc in tgt_df.columns and sc not in matched:
                r.update({'target_column_name': sc,
                          'target_column_index': list(tgt_df.columns).index(sc),
                          'target_dtype': _dtype(tgt_df[sc]),
                          'mapping_method': 'EXACT', 'is_mapped': 'Y'})
                matched.add(sc)
            elif _norm(sc) in tgt_norm_map and tgt_norm_map[_norm(sc)][1] not in matched:
                ti, tc = tgt_norm_map[_norm(sc)]
                r.update({'target_column_name': tc, 'target_column_index': ti,
                          'target_dtype': _dtype(tgt_df[tc]),
                          'mapping_method': 'NORMALIZED', 'is_mapped': 'Y'})
                matched.add(tc)
            else:
                best, best_tc = 0, None
                for tc in tgt_df.columns:
                    if tc in matched: continue
                    s = SequenceMatcher(None, _norm(sc), _norm(tc)).ratio()
                    if s > best: best, best_tc = s, tc
                if best >= 0.75 and best_tc:
                    r.update({'target_column_name': best_tc,
                              'target_column_index': list(tgt_df.columns).index(best_tc),
                              'target_dtype': _dtype(tgt_df[best_tc]),
                              'mapping_method': f'FUZZY({best:.2f})', 'is_mapped': 'Y'})
                    matched.add(best_tc)
            rows.append(r)

        stream_mapping = pd.DataFrame(rows)

    mapped_n = len(stream_mapping[stream_mapping['is_mapped'] == 'Y'])
    print(f"    Mapped: {mapped_n}/{len(stream_mapping)} columns")

    # ══════════════════════════════════════════════════════════
    #  STEP 4: INITIALIZE RESULT COLLECTOR
    # ══════════════════════════════════════════════════════════
    result = ValidationResult(
        run_id=run_id, stream_name=stream,
        source_file=reg['source_file_path'],
        target_file=reg['target_file_path']
    )

    # ══════════════════════════════════════════════════════════
    #  STEP 5: RESOLVE EXCLUDE COLUMNS
    # ══════════════════════════════════════════════════════════
    print(f"\n  [4/8] Exclude columns...")

    exclude_set, exclude_audit = resolve_exclude_columns(
        src_df, tgt_df, stream_mapping,
        user_exclude_list,
        auto_detect=True,
        auto_threshold=0.0,
        precision=precision
    )

    for a in exclude_audit:
        result.add_excluded_column(a['column_name'], a['exclusion_source'], a['reason'])

    user_excl = [a['column_name'] for a in exclude_audit if a['exclusion_source'] == 'USER_DEFINED']
    auto_excl = [a['column_name'] for a in exclude_audit if a['exclusion_source'] == 'AUTO_DETECTED']
    print(f"    Total excluded: {len(exclude_set)}")
    if user_excl: print(f"    User-defined  ({len(user_excl)}): {user_excl}")
    if auto_excl: print(f"    Auto-detected ({len(auto_excl)}): {auto_excl}")

    # ══════════════════════════════════════════════════════════
    #  STEP 6: RUN ALL 17 CHECKS
    # ══════════════════════════════════════════════════════════
    print(f"\n  [5/8] Running 17 checks...")
    print(f"  {'─'*55}")

    # ── Checks 1-3: Structure & Schema ──────────────────────
    print("    CHECK  1  Row Count .....................", end=" ")
    check_row_count(src_df, tgt_df, result)
    print("done")

    print("    CHECK  2  Column Structure ...............", end=" ")
    check_column_structure(src_df, tgt_df, stream_mapping, result)
    print("done")

    print("    CHECK  3  Data Types .....................", end=" ")
    check_data_types(src_df, tgt_df, stream_mapping, result)
    print("done")

    # ── Checks 4-7: Data Quality ────────────────────────────
    print("    CHECK  4  Null Counts ....................", end=" ")
    check_null_counts(src_df, tgt_df, stream_mapping, result)
    print("done")

    print("    CHECK  5  Numeric Aggregates .............", end=" ")
    check_numeric_aggregates(src_df, tgt_df, stream_mapping, result,
                              precision=precision)
    print("done")

    print("    CHECK  6  Distinct Counts ................", end=" ")
    check_distinct_counts(src_df, tgt_df, stream_mapping, result)
    print("done")

    print("    CHECK  7  Duplicates .....................", end=" ")
    check_duplicates(src_df, tgt_df, result)
    print("done")

    # ── Checks 8-10: Data Accuracy (PK-based) ───────────────
    print("    CHECK  8  Row Data (PK-based) ............", end=" ")
    check_row_data(src_df, tgt_df, stream_mapping, result,
                   precision=precision, pk_columns=pk_columns)
    print("done")

    print("    CHECK  9  Value Distribution ..............", end=" ")
    check_value_distribution(src_df, tgt_df, stream_mapping, result)
    print("done")

    print("    CHECK 10  PK Hash Comparison ..............", end=" ")
    check_hash_comparison(src_df, tgt_df, stream_mapping, result,
                          precision=precision, pk_columns=pk_columns)
    print("done")

    # ── Checks 11-13: Key Validation ────────────────────────
    print("    CHECK 11  Source - Target (A-B) ...........", end=" ")
    check_source_minus_target(src_df, tgt_df, stream_mapping,
                               pk_columns, result)
    print("done")

    print("    CHECK 12  Target - Source (B-A) ...........", end=" ")
    check_target_minus_source(src_df, tgt_df, stream_mapping,
                               pk_columns, result)
    print("done")

    print("    CHECK 13  PK Value Drill-Down ..............", end=" ")
    check_pk_value_drilldown(src_df, tgt_df, stream_mapping,
                              pk_columns, result, precision=precision)
    print("done")

    # ── Checks 14-16: Column Success & PK Detail ────────────
    print("    CHECK 14  Column Success % (PK-based) .....", end=" ")
    check_column_success_pct(src_df, tgt_df, stream_mapping, result,
                              precision=precision, pk_columns=pk_columns)
    print("done")

    print("    CHECK 15  Mismatch Detail with PK .........", end=" ")
    check_mismatch_with_pk(src_df, tgt_df, stream_mapping,
                            pk_columns, result, precision=precision)
    print("done")

    print("    CHECK 16  PK Issue Summary ................", end=" ")
    check_pk_issue_summary(src_df, tgt_df, stream_mapping,
                            pk_columns, result, precision=precision)
    print("done")

    # ── Check 17: MINUS Query ───────────────────────────────
    print("    CHECK 17  MINUS Query (with excludes) .....", end=" ")
    check_minus_query(src_df, tgt_df, stream_mapping,
                       exclude_set, result, precision=precision)
    print("done")

    print(f"  {'─'*55}")
    print(f"    All 17 checks completed")

    # ══════════════════════════════════════════════════════════
    #  STEP 7: SAVE RESULTS TO DELTA TABLES
    # ══════════════════════════════════════════════════════════
    print(f"\n  [6/8] Saving results...")
    save_results(result)
    print(f"    Saved run_id: {run_id}")

    # ══════════════════════════════════════════════════════════
    #  STEP 8: PRINT SUMMARY
    # ══════════════════════════════════════════════════════════
    overall_status = result.get_overall_status()
    overall_results.append({'stream': stream, 'run_id': run_id, 'status': overall_status})

    pass_ct = sum(1 for r in result.summary_rows if r['status'] == 'PASS')
    warn_ct = sum(1 for r in result.summary_rows if r['status'] == 'WARNING')
    fail_ct = sum(1 for r in result.summary_rows if r['status'] == 'FAIL')

    print(f"\n  {'='*55}")
    print(f"    OVERALL : {overall_status}")
    print(f"    PASS: {pass_ct}  |  WARNING: {warn_ct}  |  FAIL: {fail_ct}")
    print(f"  {'='*55}")

    for row in result.summary_rows:
        if row['status'] == 'PASS':      icon = 'PASS'
        elif row['status'] == 'WARNING': icon = 'WARN'
        else:                            icon = 'FAIL'
        print(f"    [{icon:4s}] {row['check_name']:<35s} {row['details'][:50]}")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════

print(f"\n\n{'='*70}")
print(f"  VALIDATION COMPLETE — {len(overall_results)} stream(s)")
print(f"{'='*70}")
for r in overall_results:
    icon = 'PASS' if r['status'] == 'PASSED' else 'FAIL'
    print(f"  [{icon}] {r['stream']:30s} -> {r['status']}  ({r['run_id']})")
print(f"{'='*70}")
print(f"\n  NEXT -> Run 05_validation_report to view results")