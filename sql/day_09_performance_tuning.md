# Day 9: Performance Tuning & Optimization

Welcome to Day 9! This is the domain of Database Architects. Knowing how to write a query is one thing; knowing how to make it run fast over billions of rows is what gets you hired at top tech companies.

---

## 1. Theory Deep Dive

### Indexing Strategies
An index is a data structure (typically a B-Tree) that improves the speed of data retrieval operations.
* **Clustered Index:** Sorts and stores the actual data rows in the table based on their key values. Because the data rows themselves can only be sorted in one order, a table can have **only one** clustered index (usually the Primary Key).
* **Non-Clustered Index:** Contains the index key values and a pointer to the actual data row (either a row locator or the clustered index key). You can have multiple non-clustered indexes on a table. Think of it like an index at the back of a book.
* **Covering Index:** A non-clustered index that includes all the columns requested in the `SELECT`, `JOIN`, and `WHERE` clauses of a query, meaning the database engine doesn't have to look at the actual data table (no "Key Lookup"). Use the `INCLUDE` keyword in SQL Server.

### Execution Plans
A visual or text representation of how the SQL Server Query Optimizer intends to execute a query.
* Look for expensive operations like **Table Scans** (reading the whole table) or **Index Scans** (reading the whole index), and try to convert them into **Index Seeks** (finding the exact rows quickly).
* Look out for **Key Lookups**, which happen when a non-clustered index finds a row, but the query asks for columns not in the index, forcing the engine to jump back to the clustered index to get the rest of the data.

### SARGability
Search Argument Able. Writing queries in a way that allows SQL Server to use indexes.
* *Non-SARGable:* `WHERE YEAR(OrderDate) = 2023` (Applying a function to a column prevents index usage).
* *SARGable:* `WHERE OrderDate >= '2023-01-01' AND OrderDate < '2024-01-01'` (Index can be used).

### Partitioning
Dividing large tables into smaller, more manageable pieces (partitions) while maintaining a single logical table.
* **Benefits:** Drastically improves query performance (Partition Elimination - the engine only scans the relevant partitions), and makes maintenance easier (e.g., dropping old data by switching out a partition instead of running a massive `DELETE`).

### Indexed / Materialized Views
A standard view is just a saved query. An **Indexed View** (Materialized View) physically stores the result set of the query on disk by creating a unique clustered index on the view.
* Extremely useful for data warehouses where the same complex aggregations are queried constantly.
* Downside: Slows down `INSERT`/`UPDATE`/`DELETE` operations on the underlying base tables, as the view must also be updated.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Amazon)** What is the difference between a Clustered Index and a Non-Clustered Index? How many of each can a table have?
2. **(Microsoft)** You see a "Key Lookup" in your execution plan taking up 80% of the query cost. How do you fix it?
3. **(Uber)** Explain the concept of Table Partitioning. What column would you typically choose as the partition key for a massive `Orders` table?
4. **(Google)** Why is `WHERE LEFT(PhoneNumber, 3) = '555'` a bad idea for performance? How would you rewrite it?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You have a massive table `UserActivityLog (LogID, UserID, Action, LogDate)`. 
The `LogID` is the Primary Key (Clustered Index).
You frequently run this query for dashboards:
```sql
SELECT Action, COUNT(*) 
FROM UserActivityLog 
WHERE UserID = @UserID 
GROUP BY Action
```

**Task 1: Index Creation**
The query currently performs a Clustered Index Scan (reading the entire table) because it is filtering on `UserID`. Write the DDL command to create an optimal Non-Clustered Index that will "cover" this query and result in an Index Seek.

**Task 2: SARGable Rewrite**
You have this query: 
`SELECT * FROM Employees WHERE ISNULL(Department, 'Unassigned') = 'Sales'`
Rewrite this query so that it is SARGable (allowing it to use an index on the `Department` column).

---

### Next Steps
Performance tuning is the most crucial skill for senior roles. Review the theory and try out the Indexing task!
