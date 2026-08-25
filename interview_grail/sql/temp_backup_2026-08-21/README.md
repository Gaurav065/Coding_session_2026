# SQL Deep Dive — Master Interview Dossier (2026-08-21) ⚔️

Welcome to the **SQL Wilderness Dossier**. This repository bypasses generic entry-level questions (like *"what is a left join?"*) and dives directly into database internals, engine mechanics, three-valued logic subtleties, advanced analytical window mechanics, optimizer execution strategies, concurrency anomalies, and battle-tested "Boss-Level" algorithmic SQL problems.

---

## 🗺️ Master Curriculum Breakdown

| Module | Core Domain | Key Deep-Dive Topics |
| :--- | :--- | :--- |
| **[01_engine_execution_and_3vl.md](file:///C:/Coding/interview_grail/sql/2026-08-21/01_engine_execution_and_3vl.md)** | **Logical Query Processing & 3VL** | Logical execution phases, short-circuit non-guarantees, 3VL truth tables, the `NOT IN` vs `NOT EXISTS` NULL trap, ANSI `IS NOT DISTINCT FROM`, SARGability pitfalls. |
| **[02_window_functions_and_framing.md](file:///C:/Coding/interview_grail/sql/2026-08-21/02_window_functions_and_framing.md)** | **Window Engine & Framing Internals** | Execution pipeline, `ROWS` vs `RANGE` vs `GROUPS`, the default frame hazard, ties & non-determinism, `LAST_VALUE()` frame trap, memory spillage in window sorts. |
| **[03_optimizer_indexing_joins.md](file:///C:/Coding/interview_grail/sql/2026-08-21/03_optimizer_indexing_joins.md)** | **Optimizer Internals & Joins** | Nested Loops vs Hash Join (Grace Hash spill) vs Sort-Merge, Correlated Subquery Decorrelation, B+Tree anatomy, Covering indexes, Index Skip Scans, Cardinality estimation. |
| **[04_concurrency_mvcc_anomalies.md](file:///C:/Coding/interview_grail/sql/2026-08-21/04_concurrency_mvcc_anomalies.md)** | **Transactions & Anomalies** | ACID, Isolation matrix, MVCC internals, **Write Skew**, Lost Updates, Snapshot Isolation vs Serializable Snapshot Isolation (SSI), Lock escalation & Deadlocks. |
| **[05_boss_level_problems.md](file:///C:/Coding/interview_grail/sql/2026-08-21/05_boss_level_problems.md)** | **Wilderness Boss Interview Problems** | Gaps & Islands (3 methods), Delta-Sweep Peak Concurrency, Dynamic Sessionization, FIFO Inventory Lot Matching, Graph Cycle Detection with Recursive CTEs. |

---

## 🛠️ How to Use This Day's Module
1. Use these documents as your comprehensive reference manuals.
2. Every topic includes:
   - **The Core Mechanic / Engine Blueprint**
   - **The Hidden Trap / Why candidates fail**
   - **The Boss-Level Interview Question & Rigorous Solution**
   - **Engine-specific nuances (Postgres, Snowflake, BigQuery, SQL Server, Spark SQL)**
