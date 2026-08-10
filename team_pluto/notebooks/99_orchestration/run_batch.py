# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 99 — Pipeline Orchestrator (Optimized & Thread-Safe)
# Features:
#   - Multithreaded execution for parallel domain processing
#   - Resume capability to skip already-completed stages
#   - Thread Locking to prevent Delta Lake concurrent append crashes
#
# Stage order:
#   0   Integrity check      (sequential)
#   1   Landing              (parallel, 7 domains)
#   2   Bronze               (parallel, 7 domains)
#   3   Validate Bronze      (sequential)
#   3b  Staging              (parallel, 4 notebooks — SCD-2 + CDC prep from bronze)
#   4   Silver               (parallel, 7 domains — reads from bronze)
#   4b  Validate Silver      (sequential — row counts, uniqueness, nulls, domain, RI)
#   5   Gold Group A         (parallel — reference dims + dim_date/time)
#   6   Gold Group B         (parallel — dim_company/security + dim_broker/customer/account)
#   7   Gold DimTrade        (sequential — needs Group B dims)
#   8   Gold Facts           (parallel — all fact tables)
#   8b  Gold Missing         (sequential — dim_prospect, financial, fact_cash_transactions, fact_trade_history)
#   9   Validate Gold        (sequential)
# ═══════════════════════════════════════════════════════════════════════════════

import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'):
        del sys.modules[_k]
sys.path.insert(0, _root)

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.operations import upsert_run_state, log_event

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("batch_id", "2")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("skip_integrity", "false")
dbutils.widgets.text("prospect_format", "json")
dbutils.widgets.dropdown("resume_run", "false", ["true", "false"], "Resume from Failure")

BATCH_ID = dbutils.widgets.get("batch_id")
RUN_ID = dbutils.widgets.get("run_id") or spark.sql(
    "SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')"
).collect()[0][0]
SKIP_INTEGRITY = dbutils.widgets.get("skip_integrity").lower() == "true"
PROSPECT_FMT   = dbutils.widgets.get("prospect_format")
RESUME_RUN     = dbutils.widgets.get("resume_run").lower() == "true"

PIPELINE_LOG   = tbl(cfg, "operations", "pipeline_logs")
RUN_STATE      = tbl(cfg, "operations", "pipeline_run_state")

BASE_NB = "/Workspace/Users/gaurav.patel@celebaltech.com/Team_pluto/team_pluto/notebooks"
TIMEOUT = 3600
MAX_WORKERS = 4

params = {"batch_id": BATCH_ID, "run_id": RUN_ID, "prospect_format": PROSPECT_FMT}
log_lock = Lock()

print(f"{'='*60}")
print(f"Pipeline Run ID : {RUN_ID}")
print(f"Batch           : {BATCH_ID}")
print(f"{'='*60}")

# COMMAND ----------

def is_stage_completed(stage_name: str) -> bool:
    if not RESUME_RUN:
        return False
    try:
        count = spark.sql(f"""
            SELECT COUNT(1) FROM {RUN_STATE}
            WHERE batch = '{BATCH_ID}'
              AND current_stage = '{stage_name}'
              AND status = 'COMPLETED'
        """).collect()[0][0]
        return count > 0
    except Exception:
        return False

def run_stage(stage_name: str, nb_path: str, extra_params: dict = None) -> str:
    if is_stage_completed(stage_name):
        print(f"  >> {stage_name:<35} [SKIPPED - PREVIOUSLY COMPLETED]")
        return "COMPLETED"

    p = {**params, **(extra_params or {})}

    with log_lock:
        upsert_run_state(spark, RUN_STATE, RUN_ID, BATCH_ID, stage_name, "RUNNING")
        log_event(spark, PIPELINE_LOG, event_type="STAGE_START", message=f"{stage_name} started",
                  layer=stage_name, batch_id=BATCH_ID, run_id=RUN_ID)

    t0 = time.time()
    try:
        result = dbutils.notebook.run(nb_path, TIMEOUT, p)
        elapsed = time.time() - t0
        status = "SKIPPED" if result == "SKIPPED" else "COMPLETED"
        icon   = ">>" if status == "SKIPPED" else "OK"
        print(f"  {icon} {stage_name:<35} {elapsed:>6.1f}s  [{status}]")

        with log_lock:
            upsert_run_state(spark, RUN_STATE, RUN_ID, BATCH_ID, stage_name, status)
            log_event(spark, PIPELINE_LOG, event_type="STAGE_END", message=f"{stage_name} {status}",
                      layer=stage_name, batch_id=BATCH_ID, run_id=RUN_ID, status=status)
        return status
    except Exception as e:
        elapsed = time.time() - t0
        msg = str(e)[:200]
        print(f"  FAILED {stage_name:<35} after {elapsed:.1f}s")
        print(f"     Error: {msg}")

        with log_lock:
            upsert_run_state(spark, RUN_STATE, RUN_ID, BATCH_ID, stage_name, "FAILED")
            log_event(spark, PIPELINE_LOG, event_type="STAGE_FAILED", message=msg,
                      layer=stage_name, batch_id=BATCH_ID, run_id=RUN_ID, status="ERROR")
        raise

def run_parallel_stages(stage_list, layer_name):
    print(f"\n{'-'*60}")
    print(f"STAGE: {layer_name} (Executing up to {MAX_WORKERS} in parallel)")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_stage = {
            executor.submit(run_stage, stage_name, nb_path, ext_params): stage_name
            for stage_name, nb_path, ext_params in stage_list
        }

        for future in as_completed(future_to_stage):
            stage_name = future_to_stage[future]
            try:
                future.result()
            except Exception as exc:
                print(f"\nFATAL: Parallel execution halted due to failure in {stage_name}.")
                raise exc

# COMMAND ----------

pipeline_start = time.time()

if not SKIP_INTEGRITY:
    run_stage("00_integrity", f"{BASE_NB}/01_integrity/01_integrity_check")
else:
    print("  >>  00_integrity -- SKIPPED")

landing_stages = [
    ("01_landing_control",         f"{BASE_NB}/02_landing/02a_landing_control",         None),
    ("01_landing_cross_reference", f"{BASE_NB}/02_landing/02b_landing_cross_reference", None),
    ("01_landing_market",          f"{BASE_NB}/02_landing/02c_landing_market",           None),
    ("01_landing_hr",              f"{BASE_NB}/02_landing/02d_landing_hr",               None),
    ("01_landing_customer",        f"{BASE_NB}/02_landing/02e_landing_customer",         None),
    ("01_landing_account",         f"{BASE_NB}/02_landing/02f_landing_account",          None),
    ("01_landing_trade",           f"{BASE_NB}/02_landing/02g_landing_trade",            None),
]
run_parallel_stages(landing_stages, "Landing")

bronze_stages = [
    ("02_bronze_control",         f"{BASE_NB}/03_bronze/03a_bronze_control",         None),
    ("02_bronze_cross_reference", f"{BASE_NB}/03_bronze/03b_bronze_cross_reference", None),
    ("02_bronze_market",          f"{BASE_NB}/03_bronze/03c_bronze_market",           None),
    ("02_bronze_hr",              f"{BASE_NB}/03_bronze/03d_bronze_hr",               None),
    ("02_bronze_customer",        f"{BASE_NB}/03_bronze/03e_bronze_customer",         None),
    ("02_bronze_account",         f"{BASE_NB}/03_bronze/03f_bronze_account",          None),
    ("02_bronze_trade",           f"{BASE_NB}/03_bronze/03g_bronze_trade",            None),
]
run_parallel_stages(bronze_stages, "Bronze")

print(f"\n{'-'*60}")
print("STAGE 3: Validate Bronze")
run_stage("03_validate_bronze", f"{BASE_NB}/07_validation/07a_validate_bronze", extra_params={"after_batch": BATCH_ID})

staging_stages = [
    ("03b_staging_finwire",   f"{BASE_NB}/05_staging/05a_staging_finwire",   None),
    ("03b_staging_market",    f"{BASE_NB}/05_staging/05b_staging_market",    None),
    ("03b_staging_prospect",  f"{BASE_NB}/05_staging/05c_staging_prospect",  None),
    ("03b_staging_customer",  f"{BASE_NB}/05_staging/05d_staging_customer",  None),
]
run_parallel_stages(staging_stages, "Staging [3b]")

silver_stages = [
    ("04_silver_reference",  f"{BASE_NB}/04_silver/04a_silver_reference",  None),
    ("04_silver_date_time",  f"{BASE_NB}/04_silver/04b_silver_date_time",  None),
    ("04_silver_market",     f"{BASE_NB}/04_silver/04c_silver_market",     None),
    ("04_silver_hr",         f"{BASE_NB}/04_silver/04d_silver_hr",         None),
    ("04_silver_customer",   f"{BASE_NB}/04_silver/04e_silver_customer",   None),
    ("04_silver_account",    f"{BASE_NB}/04_silver/04f_silver_account",    None),
    ("04_silver_trade",      f"{BASE_NB}/04_silver/04g_silver_trade",      None),
]
run_parallel_stages(silver_stages, "Silver")

print(f"\n{'-'*60}")
print("STAGE 4b: Validate Silver")
run_stage("04b_validate_silver", f"{BASE_NB}/07_validation/07b_validate_silver", extra_params={"after_batch": BATCH_ID})

gold_a_stages = [
    ("05_gold_reference",  f"{BASE_NB}/06_gold/05a_gold_reference",     None),
    ("05_gold_date_time",  f"{BASE_NB}/06_gold/05b_gold_dim_date_time", None),
]
run_parallel_stages(gold_a_stages, "Gold Group A")

gold_b_stages = [
    ("05_gold_company_security",        f"{BASE_NB}/06_gold/05c_gold_dim_company_security",        None),
    ("05_gold_broker_customer_account", f"{BASE_NB}/06_gold/05d_gold_dim_broker_customer_account", None),
]
run_parallel_stages(gold_b_stages, "Gold Group B")

print(f"\n{'-'*60}")
print("STAGE 7: Gold DimTrade")
run_stage("05_gold_dim_trade", f"{BASE_NB}/06_gold/05e_gold_dim_trade")

print(f"\n{'-'*60}")
print("STAGE 8: Gold Facts")
run_stage("05_gold_facts", f"{BASE_NB}/06_gold/05f_gold_facts")

print(f"\n{'-'*60}")
print("STAGE 8b: Gold Missing Tables")
run_stage("05g_gold_missing_tables", f"{BASE_NB}/06_gold/05g_gold_missing_tables")

print(f"\n{'-'*60}")
print("STAGE 9: Validate Gold")
run_stage("09_validate_gold", f"{BASE_NB}/07_validation/07c_validate_gold", extra_params={"after_batch": BATCH_ID})

total_elapsed = time.time() - pipeline_start
print(f"\n{'='*60}")
print(f"OK Full pipeline complete -- Batch {BATCH_ID}")
print(f"   Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
print(f"{'='*60}")

with log_lock:
    upsert_run_state(spark, RUN_STATE, RUN_ID, BATCH_ID, "COMPLETE", "COMPLETED")