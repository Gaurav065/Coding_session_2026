"""
runtime_context.py
──────────────────
Extracts Databricks cluster and job runtime metadata at execution time.
Used to populate the run manifest JSON with real infrastructure context.

Works in:
  - Interactive notebook attached to a cluster
  - Databricks Workflow job task
  - Library (.so) code called from either of the above

Fails gracefully (returns empty strings) in:
  - Local unit tests
  - Databricks Connect sessions
"""

from typing import Any


def get_run_context(spark) -> dict[str, str]:
    """
    Return a dict of runtime context values from the active Spark session
    and Databricks notebook context.

    Uses two sources:
      1. spark.conf.get("spark.databricks.clusterUsageTags.*")
         → Always available on DBR 10.4 LTS and above in all compute modes.
      2. JVM notebook context (clusterId, notebookPath, jobId, etc.)
         → Available in interactive notebooks and Workflow job tasks.
         → Fails gracefully if not in a notebook context (e.g. local tests).
    """
    ctx: dict[str, str] = {}

    # ── Source 1: Spark config tags (always available on cluster) ────────────
    _conf_keys = {
        "spark_version"  : "spark.databricks.clusterUsageTags.effectiveSparkVersion",
        "dbr_version"    : "spark.databricks.clusterUsageTags.sparkVersion",
        "node_type"      : "spark.databricks.clusterUsageTags.clusterNodeType",
        "num_workers"    : "spark.databricks.clusterUsageTags.clusterTargetWorkers",
        "cluster_name"   : "spark.databricks.clusterUsageTags.clusterName",
        "cloud_provider" : "spark.databricks.clusterUsageTags.cloudProvider",
    }
    for key, conf_path in _conf_keys.items():
        try:
            ctx[key] = spark.conf.get(conf_path, "")
        except Exception:
            ctx[key] = ""

    # ── Source 2: JVM notebook/job context ───────────────────────────────────
    try:
        java_ctx = (
            spark.sparkContext
            ._jvm
            .com.databricks.backend.daemon.dbutils
            .DBUtilsHolder.dbutils0().get()
            .notebook().getContext()
        )
        ctx["cluster_id"]    = _safe_opt(java_ctx.clusterId())
        ctx["notebook_path"] = _safe_opt(java_ctx.notebookPath())
        ctx["workspace_url"] = _safe_opt(java_ctx.tags().get("browserHostName"))
        ctx["user"]          = _safe_opt(java_ctx.tags().get("user"))
        ctx["job_id"]        = _safe_opt(java_ctx.tags().get("jobId"))
        ctx["run_id_dbx"]    = _safe_opt(java_ctx.tags().get("runId"))
        ctx["task_key"]      = _safe_opt(java_ctx.tags().get("taskKey"))
    except Exception:
        # Running outside Databricks (local tests, Databricks Connect)
        for k in ("cluster_id", "notebook_path", "workspace_url",
                  "user", "job_id", "run_id_dbx", "task_key"):
            ctx.setdefault(k, "")

    return ctx


def _safe_opt(scala_option: Any) -> str:
    """Safely unwrap a Scala Option[String] to a Python str."""
    try:
        return scala_option.get() if scala_option.isDefined() else ""
    except Exception:
        return ""