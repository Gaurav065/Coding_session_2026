# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Validation Functions Library
# MAGIC
# MAGIC **Usage:** `%run ./03_validation_functions`
# MAGIC
# MAGIC ### Enhancements
# MAGIC - **NULL = 0 Fix** — for numeric columns, NULL/NaN is treated as 0 (eliminates false mismatches like `0` vs `NULL`)
# MAGIC - **Leading Zeros Fix** — strips leading zeros from numeric strings (`000000000001010255` = `1010255`)
# MAGIC - **SAP Blank Fix** — SAP zero-string blanks (`000000`) treated as NULL/empty
# MAGIC - **Column Order Fix** — target columns automatically reordered to match source before comparison
# MAGIC - **PK-Based Comparison** — CHECK 8/14/15 join on PK before comparing (not positional)
# MAGIC - **Normalized PK Matching** — CHECK 11/12/13 normalize PKs (leading zeros, SAP blanks, trim)
# MAGIC - **Numeric Precision Fix** — rounds all numeric columns to configurable decimal places
# MAGIC - **Exclude Column List** — user-defined + auto-detected columns excluded from MINUS comparisons
# MAGIC - **CHECK 17: MINUS Query** — SOURCE MINUS TARGET / TARGET MINUS SOURCE with excluded columns
# MAGIC
# MAGIC ### Normalization Rules
# MAGIC | Source | Target | Treatment |
# MAGIC |--------|--------|-----------|
# MAGIC | `0` | `NULL` | Both → `0` → **MATCH** |
# MAGIC | `NULL` | `0` | Both → `0` → **MATCH** |
# MAGIC | `NULL` | `NULL` | Both → `NULL` → **MATCH** |
# MAGIC | `1010255` | `000000000001010255` | Strip leading zeros → **MATCH** |
# MAGIC | `000000` (SAP blank) | `NULL` | Both → empty → **MATCH** |
# MAGIC | `0` | `5` | `0` vs `5` → **MISMATCH** (real diff) |
# MAGIC | `NULL` | `ABC` | `NULL` vs `ABC` → **MISMATCH** (non-numeric) |
# MAGIC
# MAGIC ### All Checks
# MAGIC - Checks 1-10: Structure, Schema, Data Quality, Data Accuracy
# MAGIC - Checks 11-13: Primary Key A−B, B−A, Drill-Down (normalized PK matching)
# MAGIC - Checks 14-16: Column Success %, Mismatch with PK, PK Issue Summary (PK-based)
# MAGIC - **Check 17:** MINUS Query with Exclude Column List

# COMMAND ----------

import pandas as pd
import numpy as np
from datetime import datetime
import uuid
import json

METADATA_DB = "metadata_db"
RESULTS_DB  = "results_db"

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  SAP BLANK PATTERNS & LEADING ZEROS HELPERS
#
#  SAP systems use zero-filled strings as blank indicators:
#    '000000', '0000000000', '00000000' etc. → treated as NULL/empty
#
#  SAP also pads numeric keys with leading zeros:
#    0MATERIAL: '000000000001010255' → '1010255'
#    0VENDOR:   '0000140113' → '140113'
#
#  These helpers normalize both patterns for consistent comparison.
# ══════════════════════════════════════════════════════════════════

# SAP blank patterns: strings made entirely of zeros (length >= 4)
# These represent "blank" in SAP, NOT the number zero.
SAP_BLANK_MIN_LENGTH = 4


def is_sap_blank(val):
    """
    Check if a value is a SAP blank indicator (all-zero string, length >= 4).
    '000000' → True, '0' → False, '0000140113' → False (has non-zero digits)
    """
    if val is None or (not isinstance(val, str)):
        return False
    s = val.strip()
    return len(s) >= SAP_BLANK_MIN_LENGTH and s == '0' * len(s)


def strip_leading_zeros(val):
    """
    Strip leading zeros from a numeric-looking string value.
    '000000000001010255' → '1010255'
    '0000140113' → '140113'
    '0' → '0'  (single zero stays)
    'DC01' → 'DC01' (not numeric, unchanged)
    '00000000' → '' (all zeros, becomes empty — SAP blank)
    """
    if val is None:
        return val
    s = str(val).strip()
    if not s:
        return s
    # Only strip leading zeros from fully numeric strings
    if s.isdigit():
        stripped = s.lstrip('0')
        return stripped if stripped else '0'
    # Also handle numeric strings with decimal point
    try:
        float(s)
        # It's a valid number; strip leading zeros before decimal
        if '.' in s:
            parts = s.split('.', 1)
            int_part = parts[0].lstrip('0') or '0'
            return f"{int_part}.{parts[1]}"
        else:
            stripped = s.lstrip('0')
            return stripped if stripped else '0'
    except (ValueError, TypeError):
        return s


def normalize_pk_value(val):
    """
    Comprehensive PK value normalization for matching:
    1. Handle NULL/NaN → '' (empty, for PK matching NULL = SAP blank = no value)
    2. Strip whitespace
    3. SAP blank detection ('000000' → '')
    4. Strip leading zeros from numeric strings
    5. Normalize datetime to string
    """
    if pd.isna(val):
        return ''
    
    s = str(val).strip()
    
    # SAP blank: all-zero string (len >= 4) → empty
    if is_sap_blank(s):
        return ''
    
    # Strip leading zeros for numeric strings
    s = strip_leading_zeros(s)
    
    # Normalize datetime-like strings
    # e.g. '2020-12-13 00:00:00' → '2020-12-13'
    if len(s) >= 19 and s[10:] == ' 00:00:00':
        s = s[:10]
    
    return s


def build_pk_keys(df, pk_cols):
    """
    Build a normalized composite primary key Series for DataFrame matching.
    Handles: leading zeros, SAP blanks, NULL, whitespace, datetime.
    
    Returns: pd.Series of normalized '|'-joined PK strings
    """
    pk_parts = []
    for col in pk_cols:
        pk_parts.append(df[col].apply(normalize_pk_value))
    
    return pd.concat(pk_parts, axis=1).apply(
        lambda r: '|'.join(r.values), axis=1
    )


print("  SAP blank / leading zeros / PK normalization helpers loaded.")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  NUMERIC PRECISION + NULL HANDLING HELPERS
#
#  1. NULL/NaN → 0 for numeric columns (eliminates false mismatches)
#  2. Rounds all numeric columns to N decimal places
#  3. Converts integer-valued floats (45000.0 → 45000)
#  4. Consistent string representation for comparison
#
#  Example: source=0, target=NULL → both become "0" → MATCH
# ══════════════════════════════════════════════════════════════════

def normalize_numeric_columns(df, precision=2):
    """
    Normalize all numeric columns in a DataFrame for consistent comparison.
    
    - **NULL/NaN → 0** for numeric columns (eliminates 0-vs-NULL false mismatches)
    - Rounds floats to `precision` decimal places
    - Converts integer-valued floats (e.g. 45000.0) to int representation
    
    Returns a COPY of the DataFrame with normalized values.
    """
    df_out = df.copy()
    for col in df_out.columns:
        if pd.api.types.is_numeric_dtype(df_out[col]):
            # Coerce to numeric first
            df_out[col] = pd.to_numeric(df_out[col], errors='coerce')
            # ★ KEY FIX: Fill NULL/NaN with 0 for numeric columns
            df_out[col] = df_out[col].fillna(0)
            # Round to configured precision
            df_out[col] = df_out[col].round(precision)
            
            # For columns where ALL values are whole numbers,
            # convert to Int64 to avoid ".0" suffix
            non_null = df_out[col].dropna()
            if len(non_null) > 0 and (non_null == non_null.astype(int)).all():
                df_out[col] = df_out[col].astype('Int64')
        else:
            # For non-numeric columns, also attempt conversion:
            # if a column LOOKS numeric (e.g. stored as object/string with 
            # numeric values and NaN), convert it so NULL→0 applies
            try:
                converted = pd.to_numeric(df_out[col], errors='coerce')
                # Only convert if >50% of non-null values are actually numeric
                non_null_orig = df_out[col].dropna()
                non_null_conv = converted.dropna()
                if len(non_null_orig) > 0 and len(non_null_conv) / len(non_null_orig) > 0.5:
                    df_out[col] = converted.fillna(0).round(precision)
                    non_null2 = df_out[col].dropna()
                    if len(non_null2) > 0 and (non_null2 == non_null2.astype(int)).all():
                        df_out[col] = df_out[col].astype('Int64')
            except Exception:
                pass
    return df_out


def normalize_value_for_compare(src_val, tgt_val, precision=2):
    """
    Normalize a pair of values for comparison.
    Handles: float precision, int/float mismatch, whitespace, None/NaN,
             leading zeros (SAP padded keys), SAP blank indicators.
    
    ★ NULL/NaN treated as 0 when the OTHER value is numeric.
    ★ Leading zeros stripped: '000000000001010255' matches '1010255'
    ★ SAP blanks ('000000') treated as NULL/empty.
    
    Returns (normalized_src, normalized_tgt) as strings.
    """
    # --- Pre-process: SAP blank detection ---
    # '000000' (all-zero string, len >= 4) is SAP "blank", treat as NULL
    src_is_sap_blank = isinstance(src_val, str) and is_sap_blank(src_val)
    tgt_is_sap_blank = isinstance(tgt_val, str) and is_sap_blank(tgt_val)
    if src_is_sap_blank:
        src_val = None
    if tgt_is_sap_blank:
        tgt_val = None
    
    # --- Null detection ---
    src_is_null = pd.isna(src_val) if not isinstance(src_val, str) else (src_val.strip().upper() in ('', 'NAN', 'NONE', 'NULL', '<NA>'))
    tgt_is_null = pd.isna(tgt_val) if not isinstance(tgt_val, str) else (tgt_val.strip().upper() in ('', 'NAN', 'NONE', 'NULL', '<NA>'))
    
    # Both NULL → match
    if src_is_null and tgt_is_null:
        return 'NULL', 'NULL'
    
    # One side NULL, other has a value
    if src_is_null:
        try:
            tgt_num = float(tgt_val)
            tgt_rounded = round(tgt_num, precision)
            if tgt_rounded == int(tgt_rounded):
                tgt_str = str(int(tgt_rounded))
            else:
                tgt_str = f"{tgt_rounded:.{precision}f}".rstrip('0').rstrip('.')
            return tgt_str if tgt_rounded == 0 else '0', tgt_str
        except (ValueError, TypeError):
            return 'NULL', str(tgt_val).strip()
    
    if tgt_is_null:
        try:
            src_num = float(src_val)
            src_rounded = round(src_num, precision)
            if src_rounded == int(src_rounded):
                src_str = str(int(src_rounded))
            else:
                src_str = f"{src_rounded:.{precision}f}".rstrip('0').rstrip('.')
            return src_str, src_str if src_rounded == 0 else '0'
        except (ValueError, TypeError):
            return str(src_val).strip(), 'NULL'
    
    # Both non-null — try numeric comparison first
    try:
        src_num = float(src_val)
        tgt_num = float(tgt_val)
        src_rounded = round(src_num, precision)
        tgt_rounded = round(tgt_num, precision)
        
        if src_rounded == int(src_rounded):
            src_str = str(int(src_rounded))
        else:
            src_str = f"{src_rounded:.{precision}f}".rstrip('0').rstrip('.')
        
        if tgt_rounded == int(tgt_rounded):
            tgt_str = str(int(tgt_rounded))
        else:
            tgt_str = f"{tgt_rounded:.{precision}f}".rstrip('0').rstrip('.')
        
        return src_str, tgt_str
    except (ValueError, TypeError):
        # Not numeric — string comparison
        # ★ Strip leading zeros for numeric-looking strings
        src_s = strip_leading_zeros(str(src_val).strip())
        tgt_s = strip_leading_zeros(str(tgt_val).strip())
        return src_s, tgt_s


print("  Numeric precision + NULL→0 + leading zeros + SAP blank helpers loaded.")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  EXCLUDE COLUMN LOGIC
#  Merges user-defined exclusions with auto-detected mismatches
# ══════════════════════════════════════════════════════════════════

def resolve_exclude_columns(src_df, tgt_df, mapping_df, user_exclude_list,
                             auto_detect=True, auto_threshold=0.0, precision=2):
    """
    Build the final exclude column list for MINUS comparisons.
    
    Args:
        src_df: Source DataFrame
        tgt_df: Target DataFrame
        mapping_df: Column mapping DataFrame (is_mapped = 'Y' rows)
        user_exclude_list: List of column names the user wants excluded
        auto_detect: If True, also auto-exclude columns where ALL values mismatch
        auto_threshold: Auto-exclude columns where match rate < this (0.0 = only 0% match)
        precision: Numeric precision for comparisons
    
    Returns:
        (final_exclude_set, audit_records)
        - final_exclude_set: set of source column names to exclude
        - audit_records: list of dicts for the audit log
    """
    final_exclude = set()
    audit = []
    
    # 1) User-defined exclusions
    for col in user_exclude_list:
        col = col.strip()
        if col:
            final_exclude.add(col)
            audit.append({
                'column_name': col,
                'exclusion_source': 'USER_DEFINED',
                'reason': 'Excluded by user configuration in widgets/setup'
            })
    
    # 2) Auto-detect columns with complete mismatches
    if auto_detect:
        mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
        compare_rows = min(len(src_df), len(tgt_df))
        if compare_rows > 0:
            src_sample = src_df.head(compare_rows).reset_index(drop=True)
            tgt_sample = tgt_df.head(compare_rows).reset_index(drop=True)
            
            for _, row in mapped.iterrows():
                src_col = row['source_column_name']
                tgt_col = row['target_column_name']
                
                if src_col in final_exclude:
                    continue  # already excluded by user
                if src_col not in src_sample.columns or tgt_col not in tgt_sample.columns:
                    continue
                
                # Compare with numeric precision
                match_count = 0
                for i in range(compare_rows):
                    s_norm, t_norm = normalize_value_for_compare(
                        src_sample[src_col].iloc[i],
                        tgt_sample[tgt_col].iloc[i],
                        precision
                    )
                    if s_norm == t_norm:
                        match_count += 1
                
                match_rate = match_count / compare_rows
                if match_rate <= auto_threshold:
                    final_exclude.add(src_col)
                    audit.append({
                        'column_name': src_col,
                        'exclusion_source': 'AUTO_DETECTED',
                        'reason': f'Match rate {match_rate*100:.1f}% <= threshold {auto_threshold*100:.1f}% '
                                  f'({match_count}/{compare_rows} rows match)'
                    })
    
    return final_exclude, audit


print("  Exclude column logic loaded.")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  Result Collector
# ══════════════════════════════════════════════════════════════════

class ValidationResult:
    """Collects all validation results for a run."""
    
    def __init__(self, run_id, stream_name, source_file, target_file):
        self.run_id = run_id
        self.stream_name = stream_name
        self.source_file = source_file
        self.target_file = target_file
        self.summary_rows = []
        self.column_rows = []
        self.mismatch_rows = []
        self.key_mismatch_rows = []
        self.column_success_pct_rows = []
        self.mismatch_with_pk_rows = []
        self.pk_issue_summary_rows = []
        self.excluded_column_rows = []    # NEW: exclude audit
        self.minus_result_rows = []       # NEW: MINUS query results
        self.ts = datetime.now()
    
    def add_summary(self, check_name, category, status, details,
                    src_val='', tgt_val=''):
        self.summary_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'source_file': self.source_file, 'target_file': self.target_file,
            'check_name': check_name, 'check_category': category,
            'status': status, 'details': str(details)[:2000],
            'source_value': str(src_val), 'target_value': str(tgt_val),
            'created_ts': self.ts,
        })

        ##
    
    def add_column_result(self, src_col, tgt_col, check_name, status,
                          src_val='', tgt_val='', diff=''):
        self.column_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'source_column': str(src_col), 'target_column': str(tgt_col),
            'check_name': check_name, 'status': status,
            'source_value': str(src_val), 'target_value': str(tgt_val),
            'difference': str(diff), 'created_ts': self.ts,
        })
    
    def add_mismatch(self, row_num, col_name, src_val, tgt_val, mtype):
        self.mismatch_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'row_number': int(row_num), 'column_name': str(col_name),
            'source_value': str(src_val)[:500], 'target_value': str(tgt_val)[:500],
            'mismatch_type': mtype, 'created_ts': self.ts,
        })
    
    def add_key_mismatch(self, check_type, pk_values, col_name,
                         src_val, tgt_val, details):
        self.key_mismatch_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'check_type': check_type, 'primary_key_values': str(pk_values)[:500],
            'column_name': str(col_name), 'source_value': str(src_val)[:500],
            'target_value': str(tgt_val)[:500], 'details': str(details)[:1000],
            'created_ts': self.ts,
        })

    def add_column_success_pct(self, src_col, tgt_col, total_rows,
                                matched_rows, mismatched_rows, success_pct, status):
        self.column_success_pct_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'source_column': str(src_col), 'target_column': str(tgt_col),
            'total_rows_compared': int(total_rows), 'matched_rows': int(matched_rows),
            'mismatched_rows': int(mismatched_rows),
            'success_pct': float(round(success_pct, 4)), 'status': status,
            'created_ts': self.ts,
        })

    def add_mismatch_with_pk(self, pk_values, col_name, src_col,
                              tgt_col, src_val, tgt_val, row_num):
        self.mismatch_with_pk_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'primary_key_values': str(pk_values)[:500],
            'column_name': str(col_name), 'source_column': str(src_col),
            'target_column': str(tgt_col), 'source_value': str(src_val)[:500],
            'target_value': str(tgt_val)[:500], 'row_number': int(row_num),
            'created_ts': self.ts,
        })

    def add_pk_issue_summary(self, issue_type, pk_values, mismatched_columns, details):
        self.pk_issue_summary_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'issue_type': issue_type, 'primary_key_values': str(pk_values)[:500],
            'mismatched_columns': str(mismatched_columns)[:1000],
            'details': str(details)[:2000], 'created_ts': self.ts,
        })

    def add_excluded_column(self, column_name, exclusion_source, reason):
        self.excluded_column_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'column_name': str(column_name), 'exclusion_source': str(exclusion_source),
            'reason': str(reason)[:500], 'created_ts': self.ts,
        })

    def add_minus_result(self, direction, row_data):
        self.minus_result_rows.append({
            'run_id': self.run_id, 'stream_name': self.stream_name,
            'direction': direction, 'row_data': str(row_data)[:4000],
            'created_ts': self.ts,
        })
    
    def get_overall_status(self):
        statuses = [r['status'] for r in self.summary_rows]
        if 'FAIL' in statuses:
            return 'FAILED'
        elif 'WARNING' in statuses:
            return 'PASSED_WITH_WARNINGS'
        return 'PASSED'

print("  ValidationResult class loaded.")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 1: Row Count Comparison
# ══════════════════════════════════════════════════════════════════

def check_row_count(src_df, tgt_df, result: ValidationResult):
    src_count = len(src_df)
    tgt_count = len(tgt_df)
    diff = abs(src_count - tgt_count)
    if src_count == tgt_count:
        status, detail = 'PASS', f'Row counts match: {src_count}'
    else:
        pct = (diff / max(src_count, 1)) * 100
        status = 'FAIL' if pct > 5 else 'WARNING'
        detail = f'Row count mismatch: source={src_count}, target={tgt_count}, diff={diff} ({pct:.2f}%)'
    result.add_summary('row_count', 'STRUCTURE', status, detail, str(src_count), str(tgt_count))

print("    check_row_count")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 2: Column Count & Name Comparison
# ══════════════════════════════════════════════════════════════════

def check_column_structure(src_df, tgt_df, mapping_df, result: ValidationResult):
    src_cols = set(src_df.columns)
    tgt_cols = set(tgt_df.columns)
    
    if len(src_cols) == len(tgt_cols):
        result.add_summary('column_count', 'STRUCTURE', 'PASS',
                           f'Column counts match: {len(src_cols)}',
                           str(len(src_cols)), str(len(tgt_cols)))
    else:
        result.add_summary('column_count', 'STRUCTURE', 'WARNING',
                           f'Column count: source={len(src_cols)}, target={len(tgt_cols)}',
                           str(len(src_cols)), str(len(tgt_cols)))
    
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    unmapped_src = mapping_df[mapping_df['mapping_method'] == 'UNMAPPED']
    tgt_only = mapping_df[mapping_df['mapping_method'] == 'TARGET_ONLY']
    
    result.add_summary('mapping_coverage', 'STRUCTURE',
                       'PASS' if len(unmapped_src) == 0 else 'WARNING',
                       f'Mapped: {len(mapped)}, Unmapped(src): {len(unmapped_src)}, Target-only: {len(tgt_only)}',
                       str(len(mapped)), str(len(unmapped_src)))

print("    check_column_structure")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 3: Data Type Comparison
# ══════════════════════════════════════════════════════════════════

def check_data_types(src_df, tgt_df, mapping_df, result: ValidationResult):
    """
    CHECK 3: Data type comparison.
    ★ int64 → float64 caused by NaN promotion in pandas is treated as PASS
      (when target has NULL values, pandas promotes int64 to float64 automatically).
    """
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y'].copy()
    mismatches = 0
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_df.columns or tgt_col not in tgt_df.columns:
            continue
        src_type = str(src_df[src_col].dtype)
        tgt_type = str(tgt_df[tgt_col].dtype)
        if src_type == tgt_type:
            status = 'PASS'
        else:
            # ★ int64 → float64 when target has NULLs = known pandas behavior → PASS
            is_nan_promotion = (
                'int' in src_type and 'float' in tgt_type and tgt_df[tgt_col].isna().any()
            )
            if is_nan_promotion:
                status = 'PASS'  # Not a real mismatch — pandas NaN promotes int→float
            else:
                compatible = (
                    ('int' in src_type and 'float' in tgt_type) or
                    ('float' in src_type and 'int' in tgt_type) or
                    ('int' in src_type and 'int' in tgt_type)
                )
                status = 'WARNING' if compatible else 'FAIL'
                mismatches += 1
        result.add_column_result(src_col, tgt_col, 'data_type_check', status,
                                 src_type, tgt_type)
    overall = 'PASS' if mismatches == 0 else ('WARNING' if mismatches < 3 else 'FAIL')
    result.add_summary('data_type_comparison', 'SCHEMA', overall,
                       f'{mismatches} type mismatches out of {len(mapped)} mapped columns')

print("    check_data_types (int→float NaN promotion = PASS)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 4: Null Count Comparison
# ══════════════════════════════════════════════════════════════════

def check_null_counts(src_df, tgt_df, mapping_df, result: ValidationResult):
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    issues = 0
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_df.columns or tgt_col not in tgt_df.columns:
            continue
        src_nulls = int(src_df[src_col].isna().sum())
        tgt_nulls = int(tgt_df[tgt_col].isna().sum())
        diff = abs(src_nulls - tgt_nulls)
        if diff == 0:
            status = 'PASS'
        elif diff <= 5:
            status = 'WARNING'; issues += 1
        else:
            status = 'FAIL'; issues += 1
        result.add_column_result(src_col, tgt_col, 'null_count', status,
                                 str(src_nulls), str(tgt_nulls), str(diff))
    result.add_summary('null_count_comparison', 'DATA_QUALITY',
                       'PASS' if issues == 0 else 'WARNING',
                       f'{issues} columns with null count differences')

print("    check_null_counts")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 5: Numeric Aggregates (SUM, MIN, MAX, MEAN)
#  ** FIXED: Uses precision-aware rounding + NULL→0 before aggregation **
# ══════════════════════════════════════════════════════════════════

def check_numeric_aggregates(src_df, tgt_df, mapping_df, result: ValidationResult,
                              tolerance=0.01, precision=2):
    """Compare aggregates with numeric precision normalization."""
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    issues = 0
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_df.columns or tgt_col not in tgt_df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(src_df[src_col]):
            continue
        if not pd.api.types.is_numeric_dtype(tgt_df[tgt_col]):
            result.add_column_result(src_col, tgt_col, 'numeric_aggregate', 'WARNING',
                                     'numeric', 'non-numeric', 'type mismatch')
            continue
        
        # Apply precision before aggregation
        # ★ KEY FIX: fillna(0) instead of dropna() — treats NULL as 0 for aggregation
        src_series = src_df[src_col].fillna(0).round(precision)
        tgt_series = tgt_df[tgt_col].fillna(0).round(precision)
        
        for agg_name in ['sum', 'min', 'max', 'mean']:
            src_val = round(float(getattr(src_series, agg_name)()), precision)
            tgt_val = round(float(getattr(tgt_series, agg_name)()), precision)
            if src_val == 0 and tgt_val == 0:
                diff_pct = 0.0
            elif src_val == 0:
                diff_pct = 100.0
            else:
                diff_pct = abs((src_val - tgt_val) / src_val) * 100
            
            if diff_pct <= tolerance * 100:
                status = 'PASS'
            elif diff_pct <= 1.0:
                status = 'WARNING'; issues += 1
            else:
                status = 'FAIL'; issues += 1
            result.add_column_result(src_col, tgt_col, f'aggregate_{agg_name}', status,
                                     f'{src_val}', f'{tgt_val}', f'{diff_pct:.4f}%')
    
    overall = 'PASS' if issues == 0 else ('WARNING' if issues < 5 else 'FAIL')
    result.add_summary('numeric_aggregates', 'DATA_ACCURACY', overall,
                       f'{issues} aggregate mismatches (tolerance: {tolerance*100}%, precision: {precision})')

print("    check_numeric_aggregates (precision-aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 6: Distinct Value Count Comparison
# ══════════════════════════════════════════════════════════════════

def check_distinct_counts(src_df, tgt_df, mapping_df, result: ValidationResult):
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    issues = 0
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_df.columns or tgt_col not in tgt_df.columns:
            continue
        src_d = int(src_df[src_col].nunique())
        tgt_d = int(tgt_df[tgt_col].nunique())
        diff = abs(src_d - tgt_d)
        if diff == 0:
            status = 'PASS'
        elif diff <= 3:
            status = 'WARNING'; issues += 1
        else:
            status = 'FAIL'; issues += 1
        result.add_column_result(src_col, tgt_col, 'distinct_count', status,
                                 str(src_d), str(tgt_d), str(diff))
    result.add_summary('distinct_count_comparison', 'DATA_QUALITY',
                       'PASS' if issues == 0 else 'WARNING',
                       f'{issues} columns with distinct count differences')

print("    check_distinct_counts")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 7: Duplicate Row Detection
# ══════════════════════════════════════════════════════════════════

def check_duplicates(src_df, tgt_df, result: ValidationResult):
    src_dups = int(src_df.duplicated().sum())
    tgt_dups = int(tgt_df.duplicated().sum())
    result.add_summary('source_duplicates', 'DATA_QUALITY',
                       'PASS' if src_dups == 0 else 'WARNING',
                       f'Source duplicate rows: {src_dups}', str(src_dups), '')
    result.add_summary('target_duplicates', 'DATA_QUALITY',
                       'PASS' if tgt_dups == 0 else 'WARNING',
                       f'Target duplicate rows: {tgt_dups}', '', str(tgt_dups))

print("    check_duplicates")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 8: Row-Level Data Comparison
#  ** FIXED: Uses normalize_value_for_compare (precision + NULL→0) **
# ══════════════════════════════════════════════════════════════════

def check_row_data(src_df, tgt_df, mapping_df, result: ValidationResult,
                   max_rows=50000, max_mismatches=1000, precision=2,
                   pk_columns=None):
    """
    Compare cell values with numeric precision normalization.
    
    ★ KEY FIX: When pk_columns is provided, rows are joined on PK first,
      then non-PK columns are compared. This avoids false mismatches caused
      by different row ordering between source and target.
      
    When pk_columns is None, falls back to positional comparison (legacy).
    """
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
    
    # ═══════ PK-based comparison (preferred) ═══════
    if pk_columns:
        src_pk = [p.strip() for p in pk_columns if p.strip() in src_df.columns]
        if src_pk:
            # Build normalized PK keys
            src_copy = src_df.copy()
            tgt_copy = tgt_df.copy()
            src_copy['__pk__'] = build_pk_keys(src_copy, src_pk)
            tgt_copy['__pk__'] = build_pk_keys(tgt_copy, src_pk)
            
            common_keys = set(src_copy['__pk__']) & set(tgt_copy['__pk__'])
            if common_keys:
                src_idx = src_copy[src_copy['__pk__'].isin(common_keys)] \
                    .drop_duplicates(subset='__pk__').set_index('__pk__').sort_index()
                tgt_idx = tgt_copy[tgt_copy['__pk__'].isin(common_keys)] \
                    .drop_duplicates(subset='__pk__').set_index('__pk__').sort_index()
                
                compare_rows = len(common_keys)
                total_cells = 0
                mismatch_count = 0
                mismatch_cols = set()
                
                for _, row in mapped.iterrows():
                    src_col, tgt_col = row['source_column_name'], row['target_column_name']
                    if src_col in src_pk:
                        continue  # skip PK columns
                    if src_col not in src_idx.columns or tgt_col not in tgt_idx.columns:
                        continue
                    
                    col_mismatches = 0
                    total_cells += compare_rows
                    
                    for pk_val in src_idx.index:
                        s_norm, t_norm = normalize_value_for_compare(
                            src_idx.at[pk_val, src_col],
                            tgt_idx.at[pk_val, tgt_col],
                            precision
                        )
                        if s_norm != t_norm:
                            col_mismatches += 1
                            mismatch_cols.add(src_col)
                            if len(result.mismatch_rows) < max_mismatches and col_mismatches <= 50:
                                pk_parts = pk_val.split('|')
                                pk_str = ", ".join(f"{c}={v}" for c, v in zip(src_pk, pk_parts))
                                result.add_mismatch(
                                    col_mismatches, f"{src_col} -> {tgt_col}",
                                    s_norm, t_norm,
                                    f'VALUE_MISMATCH [PK: {pk_str}]')
                    
                    mismatch_count += col_mismatches
                    match_pct = ((compare_rows - col_mismatches) / compare_rows) * 100
                    status = 'PASS' if col_mismatches == 0 else ('WARNING' if match_pct >= 95 else 'FAIL')
                    result.add_column_result(src_col, tgt_col, 'row_data_match', status,
                                             f'{compare_rows - col_mismatches}/{compare_rows}',
                                             f'{match_pct:.2f}%', str(col_mismatches))
                
                if total_cells > 0:
                    overall_pct = ((total_cells - mismatch_count) / total_cells) * 100
                else:
                    overall_pct = 100.0
                overall = 'PASS' if mismatch_count == 0 else ('WARNING' if overall_pct >= 95 else 'FAIL')
                result.add_summary('row_data_comparison', 'DATA_ACCURACY', overall,
                                   f'PK-based comparison on {compare_rows} matched rows. '
                                   f'Match: {overall_pct:.2f}%, Mismatches: {mismatch_count} '
                                   f'in {len(mismatch_cols)} columns (precision={precision})')
                return
    
    # ═══════ Positional fallback (legacy, when no PK) ═══════
    compare_rows = min(len(src_df), len(tgt_df), max_rows)
    src_sample = src_df.head(compare_rows).reset_index(drop=True)
    tgt_sample = tgt_df.head(compare_rows).reset_index(drop=True)
    total_cells = 0
    mismatch_count = 0
    mismatch_cols = set()
    
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_sample.columns or tgt_col not in tgt_sample.columns:
            continue
        
        col_mismatches = 0
        total_cells += compare_rows
        
        for i in range(compare_rows):
            s_norm, t_norm = normalize_value_for_compare(
                src_sample[src_col].iloc[i],
                tgt_sample[tgt_col].iloc[i],
                precision
            )
            if s_norm != t_norm:
                col_mismatches += 1
                mismatch_cols.add(src_col)
                if len(result.mismatch_rows) < max_mismatches and col_mismatches <= 50:
                    result.add_mismatch(i + 1, f"{src_col} -> {tgt_col}",
                                       s_norm, t_norm, 'VALUE_MISMATCH')
        
        mismatch_count += col_mismatches
        match_pct = ((compare_rows - col_mismatches) / compare_rows) * 100
        status = 'PASS' if col_mismatches == 0 else ('WARNING' if match_pct >= 95 else 'FAIL')
        result.add_column_result(src_col, tgt_col, 'row_data_match', status,
                                 f'{compare_rows - col_mismatches}/{compare_rows}',
                                 f'{match_pct:.2f}%', str(col_mismatches))
    
    if total_cells > 0:
        overall_pct = ((total_cells - mismatch_count) / total_cells) * 100
    else:
        overall_pct = 100.0
    overall = 'PASS' if mismatch_count == 0 else ('WARNING' if overall_pct >= 95 else 'FAIL')
    result.add_summary('row_data_comparison', 'DATA_ACCURACY', overall,
                       f'Positional comparison on {compare_rows} rows. '
                       f'Match: {overall_pct:.2f}%, Mismatches: {mismatch_count} '
                       f'in {len(mismatch_cols)} columns (precision={precision})')

print("    check_row_data (PK-based + precision-aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 9: Value Distribution
# ══════════════════════════════════════════════════════════════════

def check_value_distribution(src_df, tgt_df, mapping_df, result: ValidationResult,
                              top_n=10):
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    issues = 0
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_df.columns or tgt_col not in tgt_df.columns:
            continue
        if pd.api.types.is_numeric_dtype(src_df[src_col]) and src_df[src_col].nunique() > 100:
            continue
        src_top = set(src_df[src_col].value_counts().head(top_n).index.astype(str))
        tgt_top = set(tgt_df[tgt_col].value_counts().head(top_n).index.astype(str))
        overlap = src_top & tgt_top
        overlap_pct = (len(overlap) / max(len(src_top), 1)) * 100
        if overlap_pct >= 80:
            status = 'PASS'
        elif overlap_pct >= 50:
            status = 'WARNING'; issues += 1
        else:
            status = 'FAIL'; issues += 1
        result.add_column_result(src_col, tgt_col, 'value_distribution', status,
                                 f'top{top_n}: {len(src_top)} vals',
                                 f'top{top_n}: {len(tgt_top)} vals',
                                 f'{overlap_pct:.0f}% overlap')
    result.add_summary('value_distribution', 'DATA_QUALITY',
                       'PASS' if issues == 0 else 'WARNING',
                       f'{issues} columns with distribution differences')

print("    check_value_distribution")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 10: Hash-Based Full Row Comparison
# ══════════════════════════════════════════════════════════════════

def check_hash_comparison(src_df, tgt_df, mapping_df, result: ValidationResult,
                          precision=2, pk_columns=None):
    """
    Hash comparison using ONLY Primary Key columns.
    
    Purpose: Verify PK uniqueness and PK-level row matching between source
    and target by hashing normalized PK values.
    
    Steps:
      1. Extract PK columns from both DataFrames
      2. Normalize PK values (leading zeros, SAP blanks, NULL→0, dates)
      3. Hash the PK tuple for each row
      4. Compare hash sets: common, source-only, target-only
    """
    if not pk_columns:
        # Fallback to all mapped columns if no PK specified
        mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
        src_cols = [c for c in mapped['source_column_name'] if c in src_df.columns]
        tgt_cols = [c for c in mapped['target_column_name'] if c in tgt_df.columns]
    else:
        # ★ Use ONLY PK columns for hashing
        mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
        src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
        src_cols, tgt_cols = [], []
        for pk in pk_columns:
            pk = pk.strip()
            if pk in src_df.columns and pk in src_to_tgt and src_to_tgt[pk] in tgt_df.columns:
                src_cols.append(pk)
                tgt_cols.append(src_to_tgt[pk])
    
    if not src_cols or not tgt_cols:
        result.add_summary('hash_comparison', 'DATA_ACCURACY', 'SKIP',
                           'No columns available for hash comparison')
        return
    
    # ★ Use build_pk_keys() for normalized hashing (same normalization as CHECK 11/12/13)
    src_hashes = build_pk_keys(src_df, src_cols)
    tgt_hashes = build_pk_keys(tgt_df, tgt_cols)
    
    src_hash_set = set(src_hashes)
    tgt_hash_set = set(tgt_hashes)
    
    in_src_only = len(src_hash_set - tgt_hash_set)
    in_tgt_only = len(tgt_hash_set - src_hash_set)
    common = len(src_hash_set & tgt_hash_set)
    total = max(len(src_hash_set), 1)
    match_pct = (common / total) * 100
    
    status = 'PASS' if in_src_only == 0 and in_tgt_only == 0 else (
        'WARNING' if match_pct >= 95 else 'FAIL')
    
    pk_list = ', '.join(src_cols)
    result.add_summary('hash_comparison', 'DATA_ACCURACY', status,
                       f'PK Hash ({len(src_cols)} cols: {pk_list[:60]}): '
                       f'Common: {common}, Source-only: {in_src_only}, Target-only: {in_tgt_only}, '
                       f'Match: {match_pct:.2f}%', str(len(src_hash_set)), str(len(tgt_hash_set)))

print("    check_hash_comparison (PK-only hash + normalized)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 11: A-B (Source - Target) — Missing in Target
# ══════════════════════════════════════════════════════════════════

def check_source_minus_target(src_df, tgt_df, mapping_df, pk_columns,
                               result: ValidationResult, max_records=500):
    """
    CHECK 11: A-B — rows in source not found in target.
    ★ Uses build_pk_keys() for normalized matching (leading zeros, SAP blanks, trim).
    """
    if not pk_columns:
        result.add_summary('source_minus_target', 'KEY_VALIDATION', 'SKIP',
                           'No primary key columns configured.')
        return 0, pd.DataFrame()
    
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
    src_pk, tgt_pk = [], []
    for pk in pk_columns:
        pk = pk.strip()
        if pk in src_df.columns and pk in src_to_tgt and src_to_tgt[pk] in tgt_df.columns:
            src_pk.append(pk)
            tgt_pk.append(src_to_tgt[pk])
    
    if not src_pk:
        result.add_summary('source_minus_target', 'KEY_VALIDATION', 'SKIP',
                           f'PK columns {pk_columns} not found in both source and target.')
        return 0, pd.DataFrame()
    
    # ★ Normalized PK keys (handles leading zeros, SAP blanks, datetime)
    src_keys = set(build_pk_keys(src_df, src_pk))
    tgt_keys = set(build_pk_keys(tgt_df, tgt_pk))
    missing = src_keys - tgt_keys
    
    if len(missing) == 0:
        result.add_summary('source_minus_target', 'KEY_VALIDATION', 'PASS',
                           f'All {len(src_keys)} source keys found in target. PK: {src_pk}',
                           str(len(src_keys)), '0')
    else:
        pct = (len(missing) / max(len(src_keys), 1)) * 100
        status = 'FAIL' if pct > 5 else 'WARNING'
        result.add_summary('source_minus_target', 'KEY_VALIDATION', status,
                           f'{len(missing)} source records missing in target ({pct:.2f}%)',
                           str(len(src_keys)), str(len(missing)))
        for i, kt in enumerate(sorted(missing)):
            if i >= max_records: break
            result.add_key_mismatch('SOURCE_MINUS_TARGET', kt, '-',
                                    'EXISTS', 'MISSING', f'Missing in target: {kt}')
    
    # Return missing records for display
    src_key_series = build_pk_keys(src_df, src_pk)
    missing_df = src_df[src_key_series.isin(missing)].sort_values(src_pk).reset_index(drop=True)
    return len(missing), missing_df

print("    check_source_minus_target (normalized PK)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 12: B-A (Target - Source) — Orphan Records in Target
# ══════════════════════════════════════════════════════════════════

def check_target_minus_source(src_df, tgt_df, mapping_df, pk_columns,
                               result: ValidationResult, max_records=500):
    """
    CHECK 12: B-A — orphan rows in target not found in source.
    ★ Uses build_pk_keys() for normalized matching (leading zeros, SAP blanks, trim).
    """
    if not pk_columns:
        result.add_summary('target_minus_source', 'KEY_VALIDATION', 'SKIP',
                           'No primary key columns configured.')
        return 0, pd.DataFrame()
    
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
    src_pk, tgt_pk = [], []
    for pk in pk_columns:
        pk = pk.strip()
        if pk in src_df.columns and pk in src_to_tgt and src_to_tgt[pk] in tgt_df.columns:
            src_pk.append(pk)
            tgt_pk.append(src_to_tgt[pk])
    
    if not src_pk:
        result.add_summary('target_minus_source', 'KEY_VALIDATION', 'SKIP',
                           f'PK columns {pk_columns} not found in both source and target.')
        return 0, pd.DataFrame()
    
    # ★ Normalized PK keys
    src_keys = set(build_pk_keys(src_df, src_pk))
    tgt_keys = set(build_pk_keys(tgt_df, tgt_pk))
    orphans = tgt_keys - src_keys
    
    if len(orphans) == 0:
        result.add_summary('target_minus_source', 'KEY_VALIDATION', 'PASS',
                           f'No orphan records. All {len(tgt_keys)} target keys in source.',
                           '0', str(len(tgt_keys)))
    else:
        pct = (len(orphans) / max(len(tgt_keys), 1)) * 100
        status = 'FAIL' if pct > 5 else 'WARNING'
        result.add_summary('target_minus_source', 'KEY_VALIDATION', status,
                           f'{len(orphans)} orphan records in target ({pct:.2f}%)',
                           str(len(orphans)), str(len(tgt_keys)))
        for i, kt in enumerate(sorted(orphans)):
            if i >= max_records: break
            result.add_key_mismatch('TARGET_MINUS_SOURCE', kt, '-',
                                    'MISSING', 'EXISTS', f'Orphan in target: {kt}')
    
    tgt_key_series = build_pk_keys(tgt_df, tgt_pk)
    orphan_df = tgt_df[tgt_key_series.isin(orphans)].sort_values(tgt_pk).reset_index(drop=True)
    return len(orphans), orphan_df

print("    check_target_minus_source (normalized PK)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 13: Primary Key Drill-Down — Value Mismatches
#  ** FIXED: Uses normalize_value_for_compare for precision-safe matching **
# ══════════════════════════════════════════════════════════════════

def check_pk_value_drilldown(src_df, tgt_df, mapping_df, pk_columns,
                              result: ValidationResult, max_records=500, precision=2):
    if not pk_columns:
        result.add_summary('pk_value_drilldown', 'KEY_VALIDATION', 'SKIP',
                           'No primary key columns configured.')
        return 0
    
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
    src_pk, tgt_pk = [], []
    for pk in pk_columns:
        pk = pk.strip()
        if pk in src_df.columns and pk in src_to_tgt and src_to_tgt[pk] in tgt_df.columns:
            src_pk.append(pk)
            tgt_pk.append(src_to_tgt[pk])
    
    if not src_pk:
        result.add_summary('pk_value_drilldown', 'KEY_VALIDATION', 'SKIP',
                           f'PK columns {pk_columns} not found in both sides.')
        return 0
    
    nonkey_pairs = []
    for _, row in mapped.iterrows():
        sc, tc = row['source_column_name'], row['target_column_name']
        if sc in src_pk: continue
        if sc in src_df.columns and tc in tgt_df.columns:
            nonkey_pairs.append((sc, tc))
    
    if not nonkey_pairs:
        result.add_summary('pk_value_drilldown', 'KEY_VALIDATION', 'SKIP',
                           'No non-key mapped columns to compare.')
        return 0
    
    src_copy = src_df.copy()
    tgt_copy = tgt_df.copy()
    # ★ Use normalized PK keys (leading zeros, SAP blanks, trim)
    src_copy['__pk__'] = build_pk_keys(src_copy, src_pk)
    tgt_copy['__pk__'] = build_pk_keys(tgt_copy, tgt_pk)
    
    common_keys = set(src_copy['__pk__']) & set(tgt_copy['__pk__'])
    if not common_keys:
        result.add_summary('pk_value_drilldown', 'KEY_VALIDATION', 'FAIL',
                           'No matching keys found.', '0', '0')
        return 0
    
    src_idx = src_copy.drop_duplicates(subset='__pk__').set_index('__pk__')
    tgt_idx = tgt_copy.drop_duplicates(subset='__pk__').set_index('__pk__')
    
    mismatched_keys = 0
    total_mismatches = 0
    logged = 0
    
    for pk_val in sorted(common_keys):
        src_row = src_idx.loc[pk_val]
        tgt_row = tgt_idx.loc[pk_val]
        pk_parts = pk_val.split('|')
        pk_str = ", ".join(f"{c}={v}" for c, v in zip(src_pk, pk_parts) if v)
        key_has_mismatch = False
        
        for src_col, tgt_col in nonkey_pairs:
            s_norm, t_norm = normalize_value_for_compare(
                src_row[src_col], tgt_row[tgt_col], precision
            )
            if s_norm != t_norm:
                key_has_mismatch = True
                total_mismatches += 1
                if logged < max_records:
                    result.add_key_mismatch('PK_VALUE_MISMATCH', pk_str,
                                            f'{src_col} -> {tgt_col}',
                                            s_norm, t_norm,
                                            f'Mismatch [{pk_str}] {src_col}: "{s_norm}" vs "{t_norm}"')
                    logged += 1
        if key_has_mismatch:
            mismatched_keys += 1
    
    match_pct = ((len(common_keys) - mismatched_keys) / max(len(common_keys), 1)) * 100
    if mismatched_keys == 0:
        result.add_summary('pk_value_drilldown', 'KEY_VALIDATION', 'PASS',
                           f'All {len(common_keys)} common keys match across {len(nonkey_pairs)} columns.')
    else:
        status = 'FAIL' if match_pct < 95 else 'WARNING'
        result.add_summary('pk_value_drilldown', 'KEY_VALIDATION', status,
                           f'{mismatched_keys}/{len(common_keys)} keys have mismatches '
                           f'({total_mismatches} total diffs). Match: {match_pct:.2f}%')
    return mismatched_keys

print("    check_pk_value_drilldown (precision-aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 14: Column-Wise Success Percentage
#  ** FIXED: Uses normalize_value_for_compare **
# ══════════════════════════════════════════════════════════════════

def check_column_success_pct(src_df, tgt_df, mapping_df, result: ValidationResult,
                              max_rows=50000, precision=2, pk_columns=None):
    """
    CHECK 14: Column-wise success percentage.
    ★ When pk_columns is provided, joins on PK first (avoids positional mismatches).
    """
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    
    # ═══════ PK-based mode ═══════
    if pk_columns:
        src_pk = [p.strip() for p in pk_columns if p.strip() in src_df.columns]
        if src_pk:
            src_copy = src_df.copy()
            tgt_copy = tgt_df.copy()
            src_copy['__pk__'] = build_pk_keys(src_copy, src_pk)
            tgt_copy['__pk__'] = build_pk_keys(tgt_copy, src_pk)
            
            common_keys = set(src_copy['__pk__']) & set(tgt_copy['__pk__'])
            if common_keys:
                src_idx = src_copy[src_copy['__pk__'].isin(common_keys)] \
                    .drop_duplicates(subset='__pk__').set_index('__pk__').sort_index()
                tgt_idx = tgt_copy[tgt_copy['__pk__'].isin(common_keys)] \
                    .drop_duplicates(subset='__pk__').set_index('__pk__').sort_index()
                compare_rows = len(common_keys)
                col_results = []
                
                for _, row in mapped.iterrows():
                    src_col, tgt_col = row['source_column_name'], row['target_column_name']
                    if src_col not in src_idx.columns or tgt_col not in tgt_idx.columns:
                        continue
                    
                    matched = 0
                    for pk_val in src_idx.index:
                        s_norm, t_norm = normalize_value_for_compare(
                            src_idx.at[pk_val, src_col],
                            tgt_idx.at[pk_val, tgt_col], precision
                        )
                        if s_norm == t_norm:
                            matched += 1
                    
                    mismatched = compare_rows - matched
                    pct = (matched / compare_rows * 100) if compare_rows > 0 else 100.0
                    status = 'PASS' if pct >= 99.0 else ('WARNING' if pct >= 90.0 else 'FAIL')
                    result.add_column_success_pct(src_col, tgt_col, compare_rows, matched, mismatched, pct, status)
                    col_results.append((src_col, pct, status))
                
                if col_results:
                    avg_pct = sum(p for _, p, _ in col_results) / len(col_results)
                    fail_cols = [c for c, _, s in col_results if s == 'FAIL']
                    overall = 'PASS' if not fail_cols else 'FAIL'
                    detail = (f"PK-based: Avg success: {avg_pct:.2f}% across {len(col_results)} columns. "
                              f"FAIL: {len(fail_cols)}")
                else:
                    overall, detail = 'SKIP', 'No mapped columns.'
                result.add_summary('column_success_pct', 'DATA_ACCURACY', overall, detail)
                return
    
    # ═══════ Positional fallback ═══════
    compare_rows = min(len(src_df), len(tgt_df), max_rows)
    src_sample = src_df.head(compare_rows).reset_index(drop=True)
    tgt_sample = tgt_df.head(compare_rows).reset_index(drop=True)
    col_results = []
    
    for _, row in mapped.iterrows():
        src_col, tgt_col = row['source_column_name'], row['target_column_name']
        if src_col not in src_sample.columns or tgt_col not in tgt_sample.columns:
            continue
        
        matched = 0
        for i in range(compare_rows):
            s_norm, t_norm = normalize_value_for_compare(
                src_sample[src_col].iloc[i], tgt_sample[tgt_col].iloc[i], precision
            )
            if s_norm == t_norm:
                matched += 1
        
        mismatched = compare_rows - matched
        pct = (matched / compare_rows * 100) if compare_rows > 0 else 100.0
        status = 'PASS' if pct >= 99.0 else ('WARNING' if pct >= 90.0 else 'FAIL')
        result.add_column_success_pct(src_col, tgt_col, compare_rows, matched, mismatched, pct, status)
        col_results.append((src_col, pct, status))
    
    if col_results:
        avg_pct = sum(p for _, p, _ in col_results) / len(col_results)
        fail_cols = [c for c, _, s in col_results if s == 'FAIL']
        overall = 'PASS' if not fail_cols else 'FAIL'
        detail = f"Avg success: {avg_pct:.2f}% across {len(col_results)} columns. FAIL: {len(fail_cols)}"
    else:
        overall, detail = 'SKIP', 'No mapped columns.'
    result.add_summary('column_success_pct', 'DATA_ACCURACY', overall, detail)

print("    check_column_success_pct (PK-based + precision-aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 15: Mismatch Detail with Primary Key per Row
#  ** FIXED: Uses normalize_value_for_compare **
# ══════════════════════════════════════════════════════════════════

def check_mismatch_with_pk(src_df, tgt_df, mapping_df, pk_columns,
                            result: ValidationResult, max_rows=50000,
                            max_mismatch_records=2000, precision=2):
    """
    CHECK 15: Mismatch detail with PK context.
    ★ Uses build_pk_keys for normalized PK join (not positional).
    """
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
    
    # Resolve PK
    src_pk_cols = []
    if pk_columns:
        for pk in pk_columns:
            pk = pk.strip()
            if pk in src_df.columns and pk in src_to_tgt and src_to_tgt[pk] in tgt_df.columns:
                src_pk_cols.append(pk)
    
    nonkey_pairs = []
    for _, row in mapped.iterrows():
        sc, tc = row['source_column_name'], row['target_column_name']
        if sc in src_pk_cols: continue
        if sc in src_df.columns and tc in tgt_df.columns:
            nonkey_pairs.append((sc, tc))
    
    if not nonkey_pairs:
        result.add_summary('mismatch_with_pk', 'DATA_ACCURACY', 'SKIP', 'No non-key columns.')
        return
    
    # ═══════ PK-based join ═══════
    if src_pk_cols:
        src_copy = src_df.copy()
        tgt_copy = tgt_df.copy()
        src_copy['__pk__'] = build_pk_keys(src_copy, src_pk_cols)
        tgt_copy['__pk__'] = build_pk_keys(tgt_copy, src_pk_cols)
        
        common_keys = set(src_copy['__pk__']) & set(tgt_copy['__pk__'])
        if not common_keys:
            result.add_summary('mismatch_with_pk', 'DATA_ACCURACY', 'FAIL',
                               'No matching keys found.')
            return
        
        src_idx = src_copy[src_copy['__pk__'].isin(common_keys)] \
            .drop_duplicates(subset='__pk__').set_index('__pk__').sort_index()
        tgt_idx = tgt_copy[tgt_copy['__pk__'].isin(common_keys)] \
            .drop_duplicates(subset='__pk__').set_index('__pk__').sort_index()
        
        total_mismatches = 0
        logged = 0
        affected_pks = set()
        
        for src_col, tgt_col in nonkey_pairs:
            for pk_val in src_idx.index:
                s_norm, t_norm = normalize_value_for_compare(
                    src_idx.at[pk_val, src_col], tgt_idx.at[pk_val, tgt_col], precision
                )
                if s_norm != t_norm:
                    total_mismatches += 1
                    affected_pks.add(pk_val)
                    if logged < max_mismatch_records:
                        result.add_mismatch_with_pk(pk_val, f"{src_col} -> {tgt_col}",
                                                    src_col, tgt_col, s_norm, t_norm, logged + 1)
                        logged += 1
        
        compare_rows = len(common_keys)
    else:
        # ═══════ Positional fallback (no PK) ═══════
        compare_rows = min(len(src_df), len(tgt_df), max_rows)
        src_sample = src_df.head(compare_rows).reset_index(drop=True)
        tgt_sample = tgt_df.head(compare_rows).reset_index(drop=True)
        pk_series = pd.Series([f"row_index={i}" for i in range(compare_rows)])
        
        total_mismatches = 0
        logged = 0
        affected_pks = set()
        
        for src_col, tgt_col in nonkey_pairs:
            for i in range(compare_rows):
                s_norm, t_norm = normalize_value_for_compare(
                    src_sample[src_col].iloc[i], tgt_sample[tgt_col].iloc[i], precision
                )
                if s_norm != t_norm:
                    total_mismatches += 1
                    affected_pks.add(pk_series.iloc[i])
                    if logged < max_mismatch_records:
                        result.add_mismatch_with_pk(pk_series.iloc[i], f"{src_col} -> {tgt_col}",
                                                    src_col, tgt_col, s_norm, t_norm, i + 1)
                        logged += 1
    
    if total_mismatches == 0:
        result.add_summary('mismatch_with_pk', 'DATA_ACCURACY', 'PASS',
                           f'All {compare_rows} rows match across {len(nonkey_pairs)} non-key columns.')
    else:
        status = 'FAIL' if len(affected_pks) > compare_rows * 0.05 else 'WARNING'
        result.add_summary('mismatch_with_pk', 'DATA_ACCURACY', status,
                           f'{total_mismatches} cell mismatches across {len(affected_pks)} PKs (logged {logged})')

print("    check_mismatch_with_pk (PK-based + precision-aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 16: PK-Level Issue Summary
#  ** FIXED: Uses normalize_value_for_compare **
# ══════════════════════════════════════════════════════════════════

def check_pk_issue_summary(src_df, tgt_df, mapping_df, pk_columns,
                            result: ValidationResult, max_records=5000, precision=2):
    if not pk_columns:
        result.add_summary('pk_issue_summary', 'KEY_VALIDATION', 'SKIP',
                           'No primary key columns configured.')
        return
    
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    src_to_tgt = dict(zip(mapped['source_column_name'], mapped['target_column_name']))
    src_pk, tgt_pk = [], []
    for pk in pk_columns:
        pk = pk.strip()
        if pk in src_df.columns and pk in src_to_tgt and src_to_tgt[pk] in tgt_df.columns:
            src_pk.append(pk)
            tgt_pk.append(src_to_tgt[pk])
    
    if not src_pk:
        result.add_summary('pk_issue_summary', 'KEY_VALIDATION', 'SKIP',
                           f'PK columns {pk_columns} not found.')
        return
    
    # ★ Normalized PK keys (leading zeros, SAP blanks, trim)
    src_key_s = build_pk_keys(src_df, src_pk)
    tgt_key_s = build_pk_keys(tgt_df, tgt_pk)
    src_keys = set(src_key_s)
    tgt_keys = set(tgt_key_s)
    
    def pk_str(kt):
        """Format PK string for display — kt is already a '|'-joined normalized string."""
        parts = kt.split('|')
        return ", ".join(f"{c}={v}" for c, v in zip(src_pk, parts) if v)
    
    logged = 0
    
    # MISSING_IN_TARGET
    for kt in sorted(src_keys - tgt_keys):
        if logged >= max_records: break
        result.add_pk_issue_summary('MISSING_IN_TARGET', pk_str(kt), '-',
                                    'Record in SOURCE but not TARGET')
        logged += 1
    
    # MISSING_IN_SOURCE
    for kt in sorted(tgt_keys - src_keys):
        if logged >= max_records: break
        result.add_pk_issue_summary('MISSING_IN_SOURCE', pk_str(kt), '-',
                                    'Record in TARGET but not SOURCE')
        logged += 1
    
    # DATA_MISMATCH
    common = src_keys & tgt_keys
    nonkey_pairs = []
    for _, row in mapped.iterrows():
        sc, tc = row['source_column_name'], row['target_column_name']
        if sc in src_pk: continue
        if sc in src_df.columns and tc in tgt_df.columns:
            nonkey_pairs.append((sc, tc))
    
    src_c = src_df.copy()
    tgt_c = tgt_df.copy()
    src_c['__pk__'] = src_key_s
    tgt_c['__pk__'] = tgt_key_s
    src_i = src_c.drop_duplicates(subset='__pk__').set_index('__pk__')
    tgt_i = tgt_c.drop_duplicates(subset='__pk__').set_index('__pk__')
    
    mismatch_pk_count = 0
    for kt in sorted(common):
        if kt not in src_i.index or kt not in tgt_i.index: continue
        src_row, tgt_row = src_i.loc[kt], tgt_i.loc[kt]
        diff_cols = []
        for sc, tc in nonkey_pairs:
            s_n, t_n = normalize_value_for_compare(src_row[sc], tgt_row[tc], precision)
            if s_n != t_n:
                diff_cols.append(sc)
        if diff_cols:
            mismatch_pk_count += 1
            if logged < max_records:
                result.add_pk_issue_summary('DATA_MISMATCH', pk_str(kt),
                                            ', '.join(diff_cols),
                                            f'{len(diff_cols)} column(s) differ')
                logged += 1
    
    total = len(src_keys - tgt_keys) + len(tgt_keys - src_keys) + mismatch_pk_count
    if total == 0:
        result.add_summary('pk_issue_summary', 'KEY_VALIDATION', 'PASS',
                           f'All PKs clean. {len(common)} common keys match.')
    else:
        result.add_summary('pk_issue_summary', 'KEY_VALIDATION', 'FAIL',
                           f'{total} PKs with issues: {mismatch_pk_count} data mismatches, '
                           f'{len(src_keys - tgt_keys)} missing in target, '
                           f'{len(tgt_keys - src_keys)} missing in source')

print("    check_pk_issue_summary (precision-aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  CHECK 17 [NEW]: MINUS Query with Exclude Column List
#
#  Implements the SQL-equivalent of:
#    SELECT 'SOURCE' AS src, * EXCEPT(excluded_cols) FROM source_table
#    MINUS
#    SELECT 'SOURCE' AS src, * EXCEPT(excluded_cols) FROM target_table
#    UNION ALL
#    SELECT 'TARGET' AS src, * EXCEPT(excluded_cols) FROM target_table
#    MINUS
#    SELECT 'TARGET' AS src, * EXCEPT(excluded_cols) FROM source_table
#
#  Works in pandas (no Spark SQL needed) with full precision handling.
# ══════════════════════════════════════════════════════════════════

def check_minus_query(src_df, tgt_df, mapping_df, exclude_columns,
                       result: ValidationResult, max_records=1000, precision=2):
    """
    CHECK 17: MINUS query — SOURCE MINUS TARGET and TARGET MINUS SOURCE
    with excluded columns removed from the comparison.
    
    Args:
        src_df: Source DataFrame
        tgt_df: Target DataFrame
        mapping_df: Column mapping DataFrame
        exclude_columns: Set/list of source column names to exclude
        result: ValidationResult collector
        max_records: Max diff rows to store per direction
        precision: Numeric precision for comparison
    """
    mapped = mapping_df[mapping_df['is_mapped'] == 'Y']
    exclude_set = set(c.strip() for c in exclude_columns if c.strip())
    
    # Build column pairs excluding the excluded columns
    compare_pairs = []
    for _, row in mapped.iterrows():
        sc, tc = row['source_column_name'], row['target_column_name']
        if sc in exclude_set:
            continue
        if sc in src_df.columns and tc in tgt_df.columns:
            compare_pairs.append((sc, tc))
    
    if not compare_pairs:
        result.add_summary('minus_query', 'DATA_ACCURACY', 'SKIP',
                           f'No columns to compare after excluding {len(exclude_set)} columns.')
        return
    
    src_cols = [p[0] for p in compare_pairs]
    tgt_cols = [p[1] for p in compare_pairs]
    
    # Normalize both DataFrames with precision handling (includes NULL→0 for numeric)
    src_norm = normalize_numeric_columns(src_df[src_cols].copy(), precision)
    tgt_norm = normalize_numeric_columns(tgt_df[tgt_cols].copy(), precision)
    
    # Rename target columns to match source for set operations
    tgt_norm.columns = src_cols
    
    # Fill remaining NaN (non-numeric columns) with empty string
    src_norm = src_norm.fillna('')
    tgt_norm = tgt_norm.fillna('')
    
    # ★ Normalize leading zeros and SAP blanks in string columns
    for col in src_norm.columns:
        if src_norm[col].dtype == object:
            src_norm[col] = src_norm[col].apply(
                lambda v: '' if is_sap_blank(str(v)) else strip_leading_zeros(str(v).strip()))
            tgt_norm[col] = tgt_norm[col].apply(
                lambda v: '' if is_sap_blank(str(v)) else strip_leading_zeros(str(v).strip()))
    
    # Convert all to string for consistent comparison
    src_str = src_norm.astype(str).apply(lambda r: r.str.strip())
    tgt_str = tgt_norm.astype(str).apply(lambda r: r.str.strip())
    
    # SOURCE MINUS TARGET: rows in source not found in target
    src_tuples = set(src_str.apply(lambda r: tuple(r.values), axis=1))
    tgt_tuples = set(tgt_str.apply(lambda r: tuple(r.values), axis=1))
    
    src_minus_tgt = src_tuples - tgt_tuples
    tgt_minus_src = tgt_tuples - src_tuples
    
    # Log results
    logged_src = 0
    for row_tuple in sorted(src_minus_tgt):
        if logged_src >= max_records: break
        row_dict = dict(zip(src_cols, row_tuple))
        result.add_minus_result('SOURCE_MINUS_TARGET', json.dumps(row_dict, default=str))
        logged_src += 1
    
    logged_tgt = 0
    for row_tuple in sorted(tgt_minus_src):
        if logged_tgt >= max_records: break
        row_dict = dict(zip(src_cols, row_tuple))
        result.add_minus_result('TARGET_MINUS_SOURCE', json.dumps(row_dict, default=str))
        logged_tgt += 1
    
    # Summary
    total_diffs = len(src_minus_tgt) + len(tgt_minus_src)
    if total_diffs == 0:
        status = 'PASS'
        detail = (f'MINUS query PASS: 0 differences found. '
                  f'Compared {len(src_cols)} columns (excluded {len(exclude_set)}). '
                  f'Source rows: {len(src_df)}, Target rows: {len(tgt_df)}')
    else:
        pct_match = (1 - total_diffs / max(len(src_tuples) + len(tgt_tuples), 1)) * 100
        status = 'FAIL' if pct_match < 95 else 'WARNING'
        detail = (f'MINUS query found {total_diffs} differences: '
                  f'SOURCE-TARGET={len(src_minus_tgt)}, TARGET-SOURCE={len(tgt_minus_src)}. '
                  f'Compared {len(src_cols)} columns (excluded {len(exclude_set)}). '
                  f'Excluded: {sorted(exclude_set)[:10]}')
    
    result.add_summary('minus_query', 'DATA_ACCURACY', status, detail,
                       str(len(src_minus_tgt)), str(len(tgt_minus_src)))
    
    # Print summary
    print(f"\n      MINUS Query Results:")
    print(f"        Columns compared : {len(src_cols)}")
    print(f"        Columns excluded : {len(exclude_set)}: {sorted(exclude_set)[:15]}")
    print(f"        SOURCE - TARGET  : {len(src_minus_tgt)} rows")
    print(f"        TARGET - SOURCE  : {len(tgt_minus_src)} rows")

print("    check_minus_query (leading zeros + SAP blanks aware)")

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  SAVE RESULTS — Persist to Delta Tables
# ══════════════════════════════════════════════════════════════════

def save_results(result: ValidationResult):
    """Persist all validation results to Delta tables."""
    
    tables = [
        (result.summary_rows,            f"{RESULTS_DB}.src_tgt_validation_summary"),
        (result.column_rows,             f"{RESULTS_DB}.src_tgt_column_validation"),
        (result.mismatch_rows,           f"{RESULTS_DB}.src_tgt_row_mismatches"),
        (result.key_mismatch_rows,       f"{RESULTS_DB}.src_tgt_key_mismatches"),
        (result.column_success_pct_rows, f"{RESULTS_DB}.src_tgt_column_success_pct"),
        (result.mismatch_with_pk_rows,   f"{RESULTS_DB}.src_tgt_mismatch_with_pk"),
        (result.pk_issue_summary_rows,   f"{RESULTS_DB}.src_tgt_pk_issue_summary"),
        (result.excluded_column_rows,    f"{RESULTS_DB}.src_tgt_excluded_columns"),
        (result.minus_result_rows,       f"{RESULTS_DB}.src_tgt_minus_results"),
    ]
    
    for rows, table_name in tables:
        if rows:
            spark.createDataFrame(rows) \
                .write.format("delta").mode("append") \
                .saveAsTable(table_name)
            print(f"    Saved {len(rows)} rows to {table_name}")

print("    save_results")
print("\n  All validation functions loaded (Checks 1-17, PK-based + leading zeros + SAP blanks)")