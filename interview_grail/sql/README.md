# SQL Deep Dive & Interview Prep 📊

## Core Focus Areas
1. **Window Functions**:
   - Ranking: `ROW_NUMBER()`, `RANK()`, `DENSE_RANK()`, `NTILE()`.
   - Value/Offset: `LEAD()`, `LAG()`, `FIRST_VALUE()`, `LAST_VALUE()`.
   - Aggregate Window Functions & Framing clauses (`ROWS BETWEEN ... AND ...`).
2. **Complex Queries & Modeling**:
   - CTEs (Common Table Expressions) & Recursive CTEs.
   - Subqueries (Correlated vs. Uncorrelated).
   - Pivoting & Unpivoting.
   - Cumulative Sums, Running Averages, Moving Windows.
   - Gaps and Islands problem, Retention/Cohort analysis.
3. **Query Optimization & Internals**:
   - Execution Plans (EXPLAIN), Indexing (B-tree, Clustered, Non-clustered).
   - Partitioning vs. Sharding vs. Indexing.
   - Join strategies (Nested Loop, Hash Join, Merge Join).
   - Cardinality estimation, Statistics, SARGable queries.
