# 10-Day SQL Architect Mastery Plan

This 10-day plan is designed to prepare you for architect-level SQL interviews and live coding sessions. It structurally covers every topic you listed, progressing from fundamental architecture and querying to advanced performance tuning, security, and data warehousing concepts.

> [!TIP]
> **How to use this plan:** Each day, we can do a deep dive into the scheduled topics. Let me know when you're ready to start a day, and I will provide you with **Theory Summaries**, **Top Company Interview Questions**, and **Live Coding Scenarios** for those specific topics.

## Day 1: Foundations, Database Design & Normalization
*Building the foundation of relational databases and structuring data correctly.*
- **SQL Basics:** Importance, use cases, and role in data management.
- **Environment Setup:** SQL Server installation, SSMS setup, authentication methods, and database connectivity.
- **Data Types:** Understanding INT, VARCHAR, DATETIME, and selecting the right types for structured design.
- **Table Creation & Commands:** Essential commands (DDL, DML, DCL) for defining and manipulating data.
- **Constraints:** PRIMARY KEY, FOREIGN KEY, and UNIQUE to enforce data integrity.
- **Normalization:** Addressing data redundancy, anomalies, and explaining Normal Forms (1NF, 2NF, 3NF, BCNF).

## Day 2: Querying, Filtering, & Handling Data Anomalies
*Mastering data retrieval and handling incomplete datasets.*
- **Core Querying:** Deep dive into `SELECT`, `WHERE`, and `ORDER BY` for data analysis.
- **Handling NULL Values:** Using `ISNULL()`, `CASE` statements, and `COALESCE()` to ensure data consistency.
- **Data Type Conversion:** Differences and usage of `CAST()` and `CONVERT()`.

## Day 3: Built-in Functions & Data Manipulation
*Transforming data on the fly using SQL Server's built-in scalar functions.*
- **Date Functions:** Handling time-series data with `GETDATE()`, `DATEDIFF()`, and `DATEPART()`.
- **String Functions:** Formatting text using `UPPER()`, `RIGHT()`, and `SUBSTRING()`.
- **Numeric Functions:** Mathematical operations using `ROUND()`, `CEILING()`, and `FLOOR()`.

## Day 4: Aggregation, Set Operations, & Joins
*Combining datasets and summarizing information.*
- **Aggregation:** Using `GROUP BY`, `HAVING`, and aggregate functions (SUM, AVG, MIN, MAX, COUNT).
- **Standard Joins:** Efficiently combining data using `INNER JOIN`, `LEFT JOIN`, `RIGHT JOIN`, and `FULL JOIN`.
- **Complex Joins:** Managing complex relationships with `SELF JOIN` and `CROSS JOIN`.
- **Set Operations:** Merging datasets efficiently with `UNION` and `UNION ALL`.

## Day 5: Advanced Querying & Restructuring
*Writing complex queries and reshaping query outputs.*
- **Subqueries:** Standard subqueries vs. Correlated subqueries (with sample data execution scenarios).
- **Common Table Expressions (CTEs):** Creation, referencing, multiple CTEs in one `WITH` clause, and recursive CTEs.
- **PIVOT & UNPIVOT:** 
  - `PIVOT`: Transforming unique column values into multiple columns.
  - `UNPIVOT`: Converting columns into rows for data restructuring.

## Day 6: Programmability & Procedural SQL
*Encapsulating logic and building dynamic, reusable code.*
- **Stored Procedures:** Creation, input/output parameters, modification, encryption, and management.
- **User-Defined Functions (UDFs):** Scalar vs. Table-Valued functions, creation, and usage.
- **Dynamic SQL:** Concept, execution (`sp_executesql`), and avoiding SQL injection.

## Day 7: Control Flow, State Management & Transactions
*Handling errors, temporary states, and ensuring ACID compliance.*
- **Temporary Tables:** Local (`#temp`) vs. Global (`##temp`) tables, differences, and specific use cases.
- **MERGE Statement:** Implementing UPSERT (Update/Insert/Delete) logic efficiently.
- **Error Handling:** Using `TRY...CATCH` for exception handling.
- **Cursors:** Usage, implementation, and when to avoid them (performance implications).
- **Transaction Processing:** `BEGIN TRAN`, `COMMIT`, `ROLLBACK`, isolation levels, and ensuring data consistency.

## Day 8: Advanced Analytics & Windowing
*Solving complex analytical problems without complex self-joins.*
- **Window Functions:** Deep dive into `RANK()`, `DENSE_RANK()`, `ROW_NUMBER()`, `LEAD()`, `LAG()`, and partitioned aggregates.
- **String Aggregation:** Combining multiple rows into one using `STRING_AGG()` with separators.

## Day 9: Performance Tuning & Optimization
*Architect-level skills for scaling and speeding up databases.*
- **Indexing Strategies:** Types of indexes (Clustered vs. Non-Clustered), benefits, and how they improve performance.
- **Execution Plans:** Understanding execution strategies to optimize queries.
- **Query Optimization:** Practical tips, tricks, and anti-patterns to avoid (SARGability).
- **Partitioning:** Dividing large tables into smaller, manageable partitions to improve performance.
- **Materialized / Indexed Views:** Storing query results for massive performance gains on complex reads.

## Day 10: Security, Tracking, & Data Warehousing Concepts
*Securing data and managing historical changes at an enterprise scale.*
- **Views:** Creation, abstraction, and security benefits.
- **Triggers:** DML, DDL, and Logon triggers.
- **Security Features:** Restricting access with Data Masking and Row-Level Security (RLS).
- **Change Tracking:** Using Change Data Capture (CDC) for tracking and capturing data changes efficiently.
- **Slowly Changing Dimensions (SCD):** Types 1, 2, and 3, and how they manage evolving data over time in data warehouses.

---

### Ready to start?
Click **Proceed** if this plan looks good to you, and we will immediately kick off **Day 1: Foundations, Database Design & Normalization** with a mock interview scenario!
