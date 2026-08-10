import streamlit as st
import os
import sys
import json
import io
import pandas as pd
import uuid
from datetime import datetime
import plotly.express as px
from pyspark.sql import SparkSession
from databricks.connect import DatabricksSession
from databricks.sdk import WorkspaceClient

#ye le 

# ==============================================================================
# 0. PAGE CONFIG & CUSTOM ENTERPRISE UI STYLING
# ==============================================================================
st.set_page_config(page_title="SAP-DBX Recon Engine", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; }
    h1, h2, h3 { color: #004578 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stButton>button { background-color: #0078D4; color: white; border-radius: 6px; font-weight: 600; padding: 0.5rem 1rem; border: none; transition: 0.3s; }
    .stButton>button:hover { background-color: #005A9E; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); }
    div[data-testid="stMetricValue"] { font-size: 2.2rem !important; color: #004578 !important; font-weight: 700 !important; }
    div[data-testid="stMetricLabel"] { font-size: 1.1rem !important; color: #555555 !important; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] { background-color: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #E0E0E0 !important; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E0E0; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. INITIALIZATION & RESILIENT SPARK SESSION
# ==============================================================================
REPO_SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
if REPO_SRC_PATH not in sys.path: sys.path.insert(0, REPO_SRC_PATH)

def get_active_spark_session():
    try:
        spark = DatabricksSession.builder.serverless().getOrCreate()
        spark.range(1).collect() 
        return spark
    except Exception as e:
        if "INACTIVITY_TIMEOUT" in str(e) or "session_id is no longer usable" in str(e):
            SparkSession.clearActiveSession()
            SparkSession.clearDefaultSession()
            return DatabricksSession.builder.serverless().getOrCreate()
        else:
            st.error(f"Spark Connection Error: {e}")
            st.stop()

spark = get_active_spark_session()

try:
    from val_framework.core.constants import VOLUME_CONFIG_PATH, RAW_FILES_DIR, VOLUME_REPORTS_PATH, UC_CATALOG, DATA_SCHEMA, META_COLUMNS
except ImportError as e:
    st.error(f"Framework Import Error: {e}")
    st.stop()

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
def get_latest_run(stream_name):
    try:
        w = WorkspaceClient()
        response = w.files.download(f"{VOLUME_REPORTS_PATH.rstrip('/')}/{stream_name}/run_index.json")
        runs = json.loads(response.contents.read().decode('utf-8'))
        return runs[0] if runs else None
    except Exception: return None

# ==============================================================================
# 3. PIPELINE EXECUTION ENGINE 
# ==============================================================================
def execute_reconciliation_pipeline(stream_name):
    from val_framework.mapping.column_mapper import build_column_mapping
    from val_framework.core.result import ValidationResult
    from val_framework.core.logger import ValidationLogger
    from val_framework.core.runtime_context import get_run_context
    from val_framework.report.manifest import build_manifest
    from val_framework.checks.structural import check_row_count, check_column_structure
    from val_framework.checks.schema import check_data_types
    from val_framework.checks.data_accuracy import check_numeric_aggregates, check_hash_comparison
    from val_framework.checks.data_quality import check_distinct_counts, check_duplicates
    from val_framework.checks.key_validation import check_sap_minus_dbx, check_dbx_minus_sap, check_pk_issue_summary

    w = WorkspaceClient()
    st.write("⏳ **Step 1:** Loading Configuration...")
    cfg = json.loads(w.files.download(f"{VOLUME_CONFIG_PATH.rstrip('/')}/{stream_name}.json").contents.read().decode('utf-8'))
    run_id = f"{stream_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    log = ValidationLogger(run_id=run_id, stream_name=stream_name, spark=spark)
    result = ValidationResult(run_id=run_id, stream_name=stream_name, source_file=cfg['sap_file_path'], target_file=cfg['dbx_source_delta_table'])
    sap_tbl = f"{UC_CATALOG}.{DATA_SCHEMA}.sap_{''.join(c if c.isalnum() else '_' for c in stream_name).lower()}"

    st.write("⏳ **Step 2:** Safely Loading SAP Data to Delta Staging...")
    excel_bytes = io.BytesIO(w.files.download(cfg["sap_file_path"]).contents.read())
    
    full_sap_pdf = pd.read_excel(excel_bytes, sheet_name=cfg.get("sap_sheet_name", "Sheet1"))
    full_sap_pdf.columns = [str(c).strip().replace(" ", "_").replace("(", "").replace(")", "") for c in full_sap_pdf.columns]
    
    full_sap_pdf["__stream_name__"]  = stream_name
    full_sap_pdf["__source_label__"] = "SAP"
    full_sap_pdf["__load_ts__"]      = datetime.now()
    full_sap_pdf["__source_file__"]  = cfg["sap_file_path"]
    full_sap_pdf["__source_sheet__"] = cfg.get("sap_sheet_name", "Sheet1")
    
    for c in full_sap_pdf.columns:
        if full_sap_pdf[c].dtype == object:
            full_sap_pdf[c] = full_sap_pdf[c].astype(str)
            
    spark.createDataFrame(full_sap_pdf).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(sap_tbl)

    excel_bytes.seek(0)
    
    try: dbx_columns = spark.read.format("delta").load(cfg["dbx_source_delta_table"]).columns
    except Exception: dbx_columns = []
        
    mapping_df = build_column_mapping(
        pd.read_excel(excel_bytes, sheet_name=cfg.get("sap_sheet_name", "Sheet1"), nrows=5), 
        pd.DataFrame(columns=[c for c in dbx_columns if not c.startswith("__")]), stream_name
    )

    sap_sdf = spark.table(sap_tbl).drop(*META_COLUMNS)
    dbx_sdf = spark.read.format("delta").load(cfg["dbx_source_delta_table"])
    
    pk_columns, skip_cols = cfg.get("primary_key_columns", []), cfg.get("exclude_columns", [])

    # ==============================================================================
    # ---> NEW FIX: Translate DBX Keys from UI into SAP Source Keys <---
    # ==============================================================================
    if isinstance(mapping_df, pd.DataFrame):
        target_to_source = {}
        for _, row in mapping_df.iterrows():
            if row.get("is_mapped", "Y") == "Y":
                target_to_source[row["target_column_name"]] = row["source_column_name"]
        
        sap_cols = sap_sdf.columns
        translated_pks = []
        for pk in pk_columns:
            # 1. Try exact mapping
            if pk in target_to_source:
                translated_pks.append(target_to_source[pk])
            # 2. Try exact SAP match
            elif pk in sap_cols:
                translated_pks.append(pk)
            # 3. Try fuzzy SAP match (e.g. user selected CALWEEK, but SAP has 0CALWEEK)
            elif "0" + pk in sap_cols:
                translated_pks.append("0" + pk)
            # 4. Try reverse fuzzy match
            elif pk.startswith("0") and pk[1:] in sap_cols:
                translated_pks.append(pk[1:])
            else:
                translated_pks.append(pk)
        
        pk_columns = translated_pks
        
        translated_skips = []
        for sk in skip_cols:
            if sk in target_to_source: translated_skips.append(target_to_source[sk])
            elif sk in sap_cols: translated_skips.append(sk)
            elif "0" + sk in sap_cols: translated_skips.append("0" + sk)
            elif sk.startswith("0") and sk[1:] in sap_cols: translated_skips.append(sk[1:])
            else: translated_skips.append(sk)
            
        skip_cols = translated_skips
    # ==============================================================================

    st.write("⏳ **Step 3:** Executing Validation Checks...")
    progress_bar = st.progress(0)
    
    check_row_count(sap_sdf, dbx_sdf, result, log); progress_bar.progress(10)
    check_column_structure(sap_sdf, dbx_sdf, mapping_df, result, log); progress_bar.progress(20)
    check_data_types(sap_sdf, dbx_sdf, mapping_df, result, log); progress_bar.progress(40)
    check_numeric_aggregates(sap_sdf, dbx_sdf, mapping_df, result, log, skip_columns=skip_cols); progress_bar.progress(60)
    
    # These checks rely on pk_columns exactly matching the SAP columns
    check_hash_comparison(sap_sdf, dbx_sdf, mapping_df, pk_columns, result, log); progress_bar.progress(70)
    check_distinct_counts(sap_sdf, dbx_sdf, mapping_df, result, log); progress_bar.progress(80)
    check_duplicates(sap_sdf, dbx_sdf, result, log); progress_bar.progress(85)
    
    _, missing_sdf = check_sap_minus_dbx(sap_sdf, dbx_sdf, mapping_df, pk_columns, result, log, skip_columns=skip_cols)
    _, orphan_sdf = check_dbx_minus_sap(sap_sdf, dbx_sdf, mapping_df, pk_columns, result, log, skip_columns=skip_cols)
    check_pk_issue_summary(sap_sdf, dbx_sdf, mapping_df, pk_columns, result, log, skip_columns=skip_cols)
    progress_bar.progress(95)

    st.write("⏳ **Step 4:** Generating Run Reports...")
    stream_reg_dict = {
        "source_file_path": cfg.get("sap_file_path", ""),
        "target_file_path": cfg.get("dbx_source_delta_table", ""),
        "sap_delta_table": sap_tbl,
        "dbx_delta_table": cfg.get("dbx_source_delta_table", ""),
        "primary_key_columns": pk_columns, # Saves the translated SAP keys to manifest
        "exclude_columns": skip_cols
    }
    
    manifest = build_manifest(result=result, run_context=get_run_context(spark), stream_reg=stream_reg_dict, duration_seconds=10.0)
    run_dir = f"{VOLUME_REPORTS_PATH.rstrip('/')}/{stream_name}/{run_id}"
    
    w.files.upload(f"{run_dir}/manifest.json", io.BytesIO(json.dumps(manifest, indent=4, default=str).encode("utf-8")))
    if isinstance(mapping_df, pd.DataFrame):
        w.files.upload(f"{run_dir}/column_mapping.json", io.BytesIO(json.dumps({"rows": mapping_df.to_dict(orient="records")}, indent=4).encode("utf-8")))
    
    res_dict = result.to_dict() if hasattr(result, "to_dict") else vars(result)
    checks_list, pk_list = [], []
    
    for key, val in res_dict.items():
        if isinstance(val, list) and len(val) > 0:
            sample = val[0]
            sample_dict = sample.to_dict() if hasattr(sample, "to_dict") else (vars(sample) if hasattr(sample, "__dict__") else sample)
            if isinstance(sample_dict, dict):
                if "status" in sample_dict or "check_name" in sample_dict: checks_list = val
                if "issue_type" in sample_dict or "primary_key_values" in sample_dict: pk_list = val

    checks_data = []
    total_c, pass_c, fail_c, warn_c, skip_c, err_c = 0, 0, 0, 0, 0, 0
    for c in checks_list:
        c_dict = c if isinstance(c, dict) else (c.to_dict() if hasattr(c, "to_dict") else vars(c))
        checks_data.append(c_dict)
        status = str(c_dict.get("status", "")).upper()
        
        if status in ("PASSED", "PASS"): pass_c += 1
        elif status in ("FAILED", "FAIL"): fail_c += 1
        elif status == "WARNING": warn_c += 1
        elif status == "SKIP": skip_c += 1
        elif status == "ERROR": err_c += 1
        
    total_c = len(checks_list)

    pk_data = []
    for p in pk_list:
        p_dict = p if isinstance(p, dict) else (p.to_dict() if hasattr(p, "to_dict") else vars(p))
        pk_data.append(p_dict)

    w.files.upload(f"{run_dir}/checks.json", io.BytesIO(json.dumps(checks_data, indent=4, default=str).encode("utf-8")))
    w.files.upload(f"{run_dir}/pk_issues.json", io.BytesIO(json.dumps(pk_data, indent=4, default=str).encode("utf-8")))

    index_path = f"{VOLUME_REPORTS_PATH.rstrip('/')}/{stream_name}/run_index.json"
    new_run_info = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "check_counts": { "total": total_c, "pass": pass_c, "fail": fail_c, "warning": warn_c, "skip": skip_c, "error": err_c }
    }
    
    try:
        existing_index = w.files.download(index_path)
        run_index = json.loads(existing_index.contents.read().decode('utf-8'))
    except Exception: 
        run_index = [] 

    run_index.insert(0, new_run_info)
    w.files.upload(index_path, io.BytesIO(json.dumps(run_index, indent=4, default=str).encode("utf-8")))

    try: log.flush_to_delta()
    except Exception: pass
    
    progress_bar.progress(100)
    return run_id

# ==============================================================================
# 4. SIDEBAR NAVIGATION 
# ==============================================================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/SAP_2011_logo.svg/200px-SAP_2011_logo.svg.png", width=60)
    st.markdown("### Reconciliation Engine")
    st.markdown("---")
    if st.button("➕ Create New Stream", use_container_width=True, type="primary"):
        st.session_state['page'] = 'setup'
        st.rerun()

if 'page' not in st.session_state: st.session_state['page'] = 'setup'

# ==============================================================================
# PAGE 1: SETUP 
# ==============================================================================
if st.session_state['page'] == 'setup':
    st.title("Configure New Validation Stream")
    st.markdown("Define the source SAP file and map it directly to your Databricks Delta table below.")
    
    with st.container(border=True):
        st.subheader("Step 1: Source Definition")
        col_s1, col_s2 = st.columns(2)
        with col_s1: stream_name = st.text_input("Stream Name (Unique Identifier)", placeholder="e.g., lakme_sales_q1")
        with col_s2: uploaded_file = st.file_uploader("Upload SAP Data (.xlsx, .csv)", type=["xlsx", "xls", "csv"])

    with st.container(border=True):
        st.subheader("Step 2: Target Mapping (Volume Path)")
        col_t1, col_t2 = st.columns(2)
        with col_t1: full_table_path = st.text_input("Target DBX Path", value="", placeholder=f"e.g., /Volumes/{UC_CATALOG}/{DATA_SCHEMA}/path/table")
        with col_t2:
            try: available_columns = spark.read.format("delta").load(full_table_path).columns if full_table_path else []
            except Exception: available_columns = []
                
            if available_columns:
                select_all_pks = st.checkbox("☑️ Select All Columns as Primary Keys")
                if select_all_pks: pk_cols = st.multiselect("Select Primary Keys (Required)", available_columns, default=available_columns)
                else: pk_cols = st.multiselect("Select Primary Keys (Required)", available_columns)
                skip_cols = st.multiselect("Columns to Skip in Diff (Optional)", available_columns)
            else:
                st.warning("⚠️ Path not found or empty. Please type columns manually.")
                pk_cols_text = st.text_input("Primary Keys (comma separated)")
                pk_cols = [x.strip() for x in pk_cols_text.split(",")] if pk_cols_text else []
                skip_cols_text = st.text_input("Columns to Skip (comma separated)")
                skip_cols = [x.strip() for x in skip_cols_text.split(",")] if skip_cols_text else []
    
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2, col_btn3 = st.columns([1,2,1])
    with col_btn2:
        if st.button("🚀 Save Configuration & Execute Engine", type="primary", use_container_width=True):
            missing_fields = []
            if not stream_name: missing_fields.append("Stream Name")
            if not uploaded_file: missing_fields.append("Upload SAP Data File")
            if not pk_cols: missing_fields.append("Primary Keys")
            
            if missing_fields: st.error(f"⚠️ Cannot proceed. You are missing: **{', '.join(missing_fields)}**")
            else:
                from val_framework.config_loader import build_stream_config
                w = WorkspaceClient()
                file_path = f"{RAW_FILES_DIR.rstrip('/')}/{stream_name}_{uploaded_file.name}"
                uploaded_file.seek(0)
                w.files.upload(file_path, uploaded_file)
                
                config = build_stream_config(stream_name=stream_name, sap_file_path=file_path, dbx_source_delta_table=full_table_path, primary_key_columns=pk_cols, exclude_columns=skip_cols)
                w.files.upload(f"{VOLUME_CONFIG_PATH.rstrip('/')}/{stream_name}.json", io.BytesIO(json.dumps(config, indent=4).encode("utf-8")))
                st.session_state['current_stream'] = stream_name
                st.session_state['page'] = 'run_progress'
                st.rerun()

# ==============================================================================
# PAGE 2: PIPELINE PROGRESS
# ==============================================================================
elif st.session_state['page'] == 'run_progress':
    stream_name = st.session_state['current_stream']
    st.title(f"Executing: `{stream_name}`")
    with st.status("Engine Running...", expanded=True) as status:
        try:
            run_id = execute_reconciliation_pipeline(stream_name)
            status.update(label=f"✅ Pipeline Complete! Run ID: {run_id}", state="complete", expanded=False)
            st.session_state['page'] = 'dashboard'
            st.rerun()
        except Exception as e:
            status.update(label="❌ Pipeline Failed", state="error", expanded=True)
            st.error(f"Execution Error: {e}")

# ==============================================================================
# PAGE 3: ENTERPRISE DASHBOARD WITH HYBRID FALLBACK
# ==============================================================================
elif st.session_state['page'] == 'dashboard':
    stream_name = st.session_state.get('current_stream', 'Unknown Stream')
    with st.container():
        col_h1, col_h2 = st.columns([0.85, 0.15])
        col_h1.title(f"Dashboard: {stream_name}")
        if col_h2.button("🔄 Rerun Pipeline", type="primary", use_container_width=True):
            st.session_state['page'] = 'run_progress'
            st.rerun()
    
    latest_run = get_latest_run(stream_name)
    if not latest_run:
        st.warning("No run results found. Please run the pipeline first.")
    else:
        run_id = latest_run['run_id']
        run_dir = f"{VOLUME_REPORTS_PATH.rstrip('/')}/{stream_name}/{run_id}"
        
        w = WorkspaceClient()
        
        try: val_summary_df = spark.sql(f"SELECT * FROM {UC_CATALOG}.results.src_tgt_validation_summary WHERE run_id = '{run_id}'").toPandas()
        except Exception: val_summary_df = pd.DataFrame()

        if val_summary_df.empty: 
            try:
                checks_resp = w.files.download(f"{run_dir}/checks.json")
                val_summary_df = pd.DataFrame(json.loads(checks_resp.contents.read().decode('utf-8')))
            except Exception: pass

        try: pk_issue_summary_df = spark.sql(f"SELECT * FROM {UC_CATALOG}.results.src_tgt_pk_issue_summary WHERE run_id = '{run_id}'").toPandas()
        except Exception: pk_issue_summary_df = pd.DataFrame()

        if pk_issue_summary_df.empty: 
            try:
                pk_resp = w.files.download(f"{run_dir}/pk_issues.json")
                pk_issue_summary_df = pd.DataFrame(json.loads(pk_resp.contents.read().decode('utf-8')))
            except Exception: pass

        if not val_summary_df.empty:
            status_col = 'status' if 'status' in val_summary_df.columns else val_summary_df.columns[2]
            c_series = val_summary_df[status_col].str.upper()
            counts = {
                "total": len(val_summary_df),
                "pass": int(c_series.isin(["PASS", "PASSED"]).sum()),
                "fail": int(c_series.isin(["FAIL", "FAILED"]).sum()),
                "warning": int((c_series == "WARNING").sum()),
                "skip": int((c_series == "SKIP").sum()),
                "error": int((c_series == "ERROR").sum())
            }
        else:
            counts = latest_run.get('check_counts', {})

        with st.container(border=True):
            metric_keys = [k for k in ["total", "pass", "fail", "warning", "skip", "error"] if k in counts and (counts[k] > 0 or k in ["total", "pass", "fail", "warning"])]
            if metric_keys:
                kpi_cols = st.columns(len(metric_keys))
                icon_map = {"total": "📋", "pass": "✅", "warning": "⚠️", "fail": "❌", "skip": "⏭️", "error": "🚨"}
                for idx, key in enumerate(metric_keys): 
                    kpi_cols[idx].metric(f"{icon_map.get(key.lower(), '📊')} {key.upper()}", counts[key])

        st.markdown("<br>", unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["📊 Visual Overview", "🔍 Raw Check Data", "⚖️ Data Mismatch Drill-Down"])
        
        with tab1:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                with st.container(border=True):
                    st.markdown("#### Health Distribution")
                    if not val_summary_df.empty:
                        status_col = 'status' if 'status' in val_summary_df.columns else val_summary_df.columns[2]
                        status_counts = val_summary_df[status_col].value_counts().reset_index()
                        status_counts.columns = ['Status', 'Count']
                        fig_status = px.pie(status_counts, values='Count', names='Status', hole=0.5, color='Status', color_discrete_map={'PASSED': '#004578', 'PASS': '#004578', 'FAILED': '#0078D4', 'FAIL': '#0078D4', 'WARNING': '#C7E0F4', 'SKIP': '#A0A0A0', 'ERROR': '#FF0000'}, template="plotly_white")
                        fig_status.update_layout(margin=dict(t=20, b=20, l=20, r=20))
                        st.plotly_chart(fig_status, use_container_width=True)
                    else: st.info("No validation summary data found.")
            with col_c2:
                with st.container(border=True):
                    st.markdown("#### Row-Level Discrepancies")
                    if not pk_issue_summary_df.empty:
                        issue_col = 'issue_type' if 'issue_type' in pk_issue_summary_df.columns else pk_issue_summary_df.columns[1]
                        issue_counts = pk_issue_summary_df[issue_col].value_counts().reset_index()
                        issue_counts.columns = ['Issue Type', 'Count']
                        fig_issues = px.bar(issue_counts, x='Issue Type', y='Count', template="plotly_white", color_discrete_sequence=['#0078D4'])
                        fig_issues.update_layout(margin=dict(t=20, b=20, l=20, r=20))
                        st.plotly_chart(fig_issues, use_container_width=True)
                    else: st.success("🎉 No row-level discrepancies found!")

        with tab2:
            with st.container(border=True):
                st.markdown("#### Validation Checks Log")
                if not val_summary_df.empty: st.dataframe(val_summary_df, use_container_width=True, height=250)
                else: st.info("Validation logs empty.")
            with st.container(border=True):
                st.markdown("#### Primary Key Mismatches")
                if not pk_issue_summary_df.empty:
                    issue_col = 'issue_type' if 'issue_type' in pk_issue_summary_df.columns else pk_issue_summary_df.columns[1]
                    issue_filter = st.selectbox("Filter Issue Type", ["All"] + list(pk_issue_summary_df[issue_col].unique()))
                    st.dataframe(pk_issue_summary_df if issue_filter == "All" else pk_issue_summary_df[pk_issue_summary_df[issue_col] == issue_filter], use_container_width=True, height=250)
                else: st.info("No PK issues recorded.")

        with tab3:
            with st.container(border=True):
                st.markdown("#### Interleaved Row Comparison (SAP vs DBX)")
                
                if st.button("⚡ Load Mismatch Data", type="primary"):
                    with st.spinner("Fetching mismatches..."):
                        diff_df = pd.DataFrame()
                        try:
                            diff_df = spark.sql(f"SELECT * FROM {UC_CATALOG}.results.src_tgt_minus_results WHERE run_id = '{run_id}'").limit(2000).toPandas()
                        except Exception: pass
                        
                        if diff_df.empty:
                            try:
                                from pyspark.sql import functions as F
                                manifest_resp = w.files.download(f"{run_dir}/manifest.json")
                                manifest = json.loads(manifest_resp.contents.read().decode('utf-8'))
                                mapping_resp = w.files.download(f"{run_dir}/column_mapping.json")
                                mapping_data = json.loads(mapping_resp.contents.read().decode('utf-8'))
                                
                                sap_tbl = manifest.get("data_paths", {}).get("sap_delta_table", "")
                                dbx_tbl = manifest.get("data_paths", {}).get("dbx_delta_table", "")
                                pk_cols = manifest.get("data_paths", {}).get("primary_keys", [])

                                if not sap_tbl:
                                    safe_name = "".join(c if c.isalnum() else "_" for c in stream_name).lower()
                                    sap_tbl = f"{UC_CATALOG}.{DATA_SCHEMA}.sap_{safe_name}"
                                if not dbx_tbl:
                                    dbx_tbl = manifest.get("data_paths", {}).get("dbx_target", "")

                                if sap_tbl and dbx_tbl and pk_cols:
                                    sap_sdf = spark.table(sap_tbl).drop(*META_COLUMNS)
                                    
                                    try: dbx_sdf = spark.read.format("delta").load(dbx_tbl).drop(*META_COLUMNS)
                                    except Exception: dbx_sdf = spark.table(dbx_tbl).drop(*META_COLUMNS)

                                    for row in mapping_data.get("rows", []):
                                        if row.get("is_mapped") == "Y":
                                            src_col, tgt_col = row["source_column_name"], row["target_column_name"]
                                            if tgt_col in dbx_sdf.columns and src_col != tgt_col:
                                                dbx_sdf = dbx_sdf.withColumnRenamed(tgt_col, src_col)

                                    common_cols = [c for c in sap_sdf.columns if c in dbx_sdf.columns]
                                    valid_pk_cols = [c for c in pk_cols if c in common_cols]

                                    if not valid_pk_cols:
                                        st.warning(f"⚠️ Safe Mode: The configured Primary Keys ({pk_cols}) were not found exactly as spelled in the mapping. Please ensure columns exist.")
                                    else:
                                        sap_sdf = sap_sdf.dropDuplicates(subset=valid_pk_cols)
                                        dbx_sdf = dbx_sdf.dropDuplicates(subset=valid_pk_cols)
                                        
                                        sap_diff = sap_sdf.select(*common_cols).exceptAll(dbx_sdf.select(*common_cols))
                                        dbx_diff = dbx_sdf.select(*common_cols).exceptAll(sap_sdf.select(*common_cols))

                                        mismatch_pks = sap_diff.select(*valid_pk_cols).intersect(dbx_diff.select(*valid_pk_cols))
                                        sap_mismatch = sap_diff.join(mismatch_pks, on=valid_pk_cols, how="inner").withColumn("SOURCE", F.lit("SAP"))
                                        dbx_mismatch = dbx_diff.join(mismatch_pks, on=valid_pk_cols, how="inner").withColumn("SOURCE", F.lit("DBX"))

                                        diff_df = sap_mismatch.unionByName(dbx_mismatch).select(["SOURCE"] + valid_pk_cols + [c for c in common_cols if c not in valid_pk_cols]).orderBy(*valid_pk_cols, F.col("SOURCE").desc()).limit(2000).toPandas()
                            except Exception as e: st.error(f"Fallback Calculation Error: {e}")

                        if not diff_df.empty:
                            if 'SOURCE' in diff_df.columns:
                                st.dataframe(diff_df.style.apply(lambda r: [f"background-color: {'#E6F2FA' if r['SOURCE'] == 'SAP' else '#FFFFFF'}"] * len(r), axis=1), use_container_width=True, height=500)
                            else: st.dataframe(diff_df, use_container_width=True, height=500)
                        elif diff_df is not None: 
                            st.success("No data mismatches found!")