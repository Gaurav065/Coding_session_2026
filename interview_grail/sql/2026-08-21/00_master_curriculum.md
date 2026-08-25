# 🏛️ Complete SQL Master Curriculum: From Foundations to Engine Internals & Wilderness Bosses

This curriculum is structured systematically across **7 progressive stages**, covering every fundamental, intermediate, advanced, and internal topic in modern SQL and Data Engineering.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE 7 STAGES OF SQL MASTERY                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
  Stage 1: Relational Model, Set Theory & Core Language Taxonomy (DDL, DML, DCL, TCL, Types)
  Stage 2: Core Query Processing, Logical Execution Order & Three-Valued Logic (3VL)
  Stage 3: Joins (Inner, Outer, Cross, Lateral/Apply, Anti/Semi) & Subquery Decorrelation
  Stage 4: Aggregations, Grouping Extensions, Recursive CTEs & Window Framing Mechanics
  Stage 5: Data Modeling, Normalization (1NF-BCNF) & OLAP Dimensional Modeling (Star/SCD)
  Stage 6: Storage Engines, Indexing Architectures, Physical Join Operators & Optimizer CBO
  Stage 7: Concurrency (MVCC, Anomalies, Write Skew), Distributed SQL & Wilderness Bosses
```

---

## 📑 Stage Breakdown

### 🔹 Stage 1: Foundations & Relational Calculus
- Relational Model: Relations, Tuples, Attributes, Domains, Degree vs. Cardinality.
- Set Theory vs. Multiset (Bag) Theory in SQL.
- Language Taxonomy: DDL (`CREATE`, `ALTER`, `DROP`, `TRUNCATE` vs `DELETE` internals), DML, DCL, TCL (`SAVEPOINT`, `SET TRANSACTION`).
- Data Types: Fixed vs. Floating-Point (`DECIMAL` vs `FLOAT`), Char/Varchar/Text/Unicode collations, Date/Time/Timestamp/TZ normalization, `JSON` vs `JSONB` (binary AST).
- Constraints: `PRIMARY KEY`, `FOREIGN KEY` (Referential Actions: `CASCADE`, `RESTRICT`, `SET NULL`, deferrable checks), `UNIQUE` (NULL handling variants across engines), `CHECK`, `DEFAULT`, `NOT NULL`.

### 🔹 Stage 2: Logical Processing & Filtering Mechanics
- The 11-Step Logical Execution Order.
- Non-guarantee of short-circuit evaluation in SQL `WHERE` clauses.
- Three-Valued Logic (3VL): `TRUE`, `FALSE`, `UNKNOWN` truth tables.
- Predicates: `BETWEEN`, `IN`, `NOT IN` (The NULL trap mathematical proof), `LIKE`, `ILIKE`, Regex, `IS DISTINCT FROM` / `IS NOT DISTINCT FROM`.
- SARGability principles and query rewriting for index utilization.

### 🔹 Stage 3: Joins, Subqueries & Set Operators
- Join Mechanics: `INNER`, `LEFT`, `RIGHT`, `FULL OUTER`, `CROSS`, `NATURAL` (why banned).
- `ON` vs `WHERE` predicate filtering rules in outer joins.
- `CROSS APPLY` (SQL Server) / `LATERAL JOIN` (Postgres/Snowflake) - Correlated table-valued functions.
- Semi-Joins & Anti-Joins: `EXISTS` vs `IN`, `NOT EXISTS` vs Left Anti-Join.
- Subquery Classification: Scalar, Multi-row, Correlated vs. Uncorrelated.
- Set Operators: `UNION` vs `UNION ALL`, `INTERSECT`, `EXCEPT / MINUS` (Bags vs Sets, NULL handling).

### 🔹 Stage 4: Aggregations, Recursive CTEs & Window Framing
- Aggregates: `COUNT(*)`, `COUNT(col)`, `COUNT(DISTINCT)`, `SUM`, `AVG`, `STRING_AGG`, `ARRAY_AGG`.
- Multi-dimensional Grouping: `GROUPING SETS`, `ROLLUP`, `CUBE`, `GROUPING()`.
- Common Table Expressions (CTEs): Non-recursive vs Materialized vs Temp Tables.
- Recursive CTEs: Anchor member, Recursive member, termination, graph traversal, cycle detection.
- Window Functions: Ranking (`ROW_NUMBER`, `RANK`, `DENSE_RANK`, `NTILE`), Value (`LEAD`, `LAG`, `FIRST_VALUE`, `LAST_VALUE`), Aggregate Windows.
- Window Framing: `ROWS` vs `RANGE` vs `GROUPS`, frame sliding, memory spooling.

### 🔹 Stage 5: Data Modeling, Normalization & Dimensional Design
- Normal Forms: 1NF, 2NF, 3NF, BCNF (Functional Dependencies, Lossless Decomposition).
- OLTP (Normalized 3NF) vs OLAP (Dimensional Kimball).
- Fact & Dimension Tables: Additive, Semi-additive, Non-additive facts; Conformed, Degenerate, Role-playing dimensions.
- Slowly Changing Dimensions (SCD Types 1, 2, 3, 4, 6) SQL implementation.

### 🔹 Stage 6: Storage Engines, Indexing & Query Optimization
- Storage: Row-store (Pages, Heaps, Clustered) vs Column-store (Parquet, ORC, Micro-partitions, Dictionary & RLE compression).
- Index Structures: B+Trees, Hash, Bitmap, GIN/GiST, BRIN.
- Composite Index Leftmost Prefix Rule & Covering Indexes (`INCLUDE` clause).
- Physical Join Algorithms: Nested Loop, Hash Join (Grace Hash spill), Sort-Merge Join.
- Execution Plans (`EXPLAIN ANALYZE`), Cost-Based Optimizer (CBO), Statistics, Histograms, Parameter Sniffing.

### 🔹 Stage 7: Concurrency, MVCC & Wilderness Boss Problems
- ACID properties deeply defined.
- Concurrency Anomalies: Dirty Reads, Non-repeatable Reads, Phantom Reads, Lost Updates, **Write Skew**, Read Skew.
- MVCC Internals: PostgreSQL (`xmin`/`xmax`/Vacuum bloat) vs MySQL InnoDB (Undo logs) vs SQL Server (TempDB Version Store).
- Locking: Shared (S), Exclusive (X), Intent Locks (`IS`, `IX`), Lock Escalation, Deadlock resolution.
- Snapshot Isolation (SI) vs Serializable Snapshot Isolation (SSI).
- 5 Legendary Boss Problems: Gaps & Islands, Point-Event Delta Sweep, Sessionization, FIFO Accounting, Graph Cycle Detection.
