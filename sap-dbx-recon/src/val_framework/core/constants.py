import os

# ==============================================================================
# ENVIRONMENT CONFIGURATION
# ==============================================================================
UC_CATALOG = "workspace"
DATA_SCHEMA = "default"
BASE_PATH = f"/Volumes/{UC_CATALOG}/{DATA_SCHEMA}/sap_recon"

# ==============================================================================
# DERIVED PATHS
# ==============================================================================
VOLUME_CONFIG_PATH = os.path.join(BASE_PATH, "config", "streams")
VOLUME_MAPPINGS_PATH = os.path.join(BASE_PATH, "config", "mappings")
RAW_FILES_DIR = os.path.join(BASE_PATH, "validation_inputs", "raw_files")
VOLUME_REPORTS_PATH = os.path.join(BASE_PATH, "reports", "run_outputs")

# Ensure subdirectories exist inside the Volume
try:
    for directory_path in [VOLUME_CONFIG_PATH, VOLUME_MAPPINGS_PATH, RAW_FILES_DIR, VOLUME_REPORTS_PATH]:
        os.makedirs(directory_path, exist_ok=True)
except Exception as e:
    print(f"Directory initialization warning: {e}")

# ==============================================================================
# CONSTANTS & METADATA
# ==============================================================================
CATEGORY_SCHEMA = "Schema Validation"
CATEGORY_QUALITY = "Data Quality"
CATEGORY_KEY = "Key Validation"
CATEGORY_STRUCTURAL = "Structural Integrity"
CATEGORY_ACCURACY = "Data Accuracy"

META_COLUMNS = ["__stream_name__", "__source_label__", "__load_ts__", "__source_file__", "__source_sheet__"]

# --- Framework Settings ---
DEFAULT_NUMERIC_PRECISION = 2 
DEFAULT_TOLERANCE_PCT = 0.01      
FUZZY_MATCH_THRESHOLD = 0.85      

# --- Limits & Thresholds for Exporters & Checks ---
COLUMN_MISMATCH_MAX_ROWS_PER_COL = 100    
COLUMN_MISMATCH_MAX_TOTAL = 10000         
PK_ISSUE_MAX_RECORDS = 500                

# --- Delta Table Properties ---
DELTA_TBLPROPERTIES = {
    "delta.columnMapping.mode": "name",
    "delta.minReaderVersion": "2",
    "delta.minWriterVersion": "5"
}
tblproperties_sql = ", ".join(f"'{k}' = '{v}'" for k, v in DELTA_TBLPROPERTIES.items())

# --- Registry & Audit Tables ---
RUN_LOG_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.validation_run_logs"
REGISTRY_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.stream_registry"
AUDIT_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.audit_logs"
COLUMN_MAP_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.column_mappings"

# --- Result Output Tables ---
SUMMARY_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.validation_summary"
COLUMN_VAL_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.column_validation"
PK_ISSUES_TABLE = f"{UC_CATALOG}.{DATA_SCHEMA}.pk_issues"