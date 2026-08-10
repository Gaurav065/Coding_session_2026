# Day 6: Programmability & Procedural SQL

Welcome to Day 6! Today we move beyond simple SELECT statements into the world of database programmability. This is where you encapsulate business logic directly in the database.

---

## 1. Theory Deep Dive

### Stored Procedures (SPs)
A prepared SQL code that you can save, so the code can be reused over and over again.
* **Benefits:** Reduces network traffic (client only sends the SP name), promotes code reusability, enhances security (can grant execute permissions without granting direct table access), and caches execution plans for performance.
* **Parameters:** Can accept Input parameters and Output parameters (`OUTPUT` keyword).
* **Encryption:** `WITH ENCRYPTION` can be used to obfuscate the text of the procedure.
* **Modification:** Use `ALTER PROCEDURE` to modify an existing one without dropping its permissions.

### User-Defined Functions (UDFs)
Functions are similar to Stored Procedures but have stricter rules and different use cases.
* **Scalar UDFs:** Return a single value. Often used in `SELECT` lists or `WHERE` clauses. Can suffer from poor performance if used over large row sets because they execute row-by-row.
* **Table-Valued UDFs (TVFs):**
  - *Inline TVFs:* Contain a single `SELECT` statement and return a `TABLE`. Highly performant, act essentially like parameterized views.
  - *Multi-Statement TVFs:* Return a `TABLE` variable that is populated with multiple statements. Generally slower than Inline TVFs.

### Differences Between SPs and UDFs
* SPs can return multiple result sets, UDFs return only one (Scalar or Table).
* UDFs can be used in a `SELECT` / `WHERE` / `JOIN` clause; SPs cannot (must use `EXEC`).
* UDFs cannot use DML statements (INSERT, UPDATE, DELETE) to modify permanent tables; SPs can.
* SPs can manage transactions (`BEGIN TRAN`); UDFs cannot.

### Dynamic SQL
Building SQL statements dynamically at runtime as strings, and then executing them using `EXEC()` or `sp_executesql`.
* **Use case:** When table names, column names, or pivot structures are not known until runtime.
* **Security:** Always use `sp_executesql` with parameters instead of `EXEC()` to prevent **SQL Injection** attacks.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Microsoft)** What is the primary difference between a Stored Procedure and a User-Defined Function (UDF)?
2. **(Capital One)** Explain SQL Injection. How does Dynamic SQL expose you to it, and how do you prevent it using `sp_executesql`?
3. **(General Architecture)** Why might a DBA ask you to convert your Multi-Statement TVF into an Inline TVF?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You need to build a secure, reusable process to look up user data. `Users(UserID, Name, Email)`.

**Task 1: Stored Procedure Creation**
Write a Stored Procedure named `GetUserInfo` that takes an input parameter `@UserID INT`.
The procedure should return the `Name` and `Email` of the user. If the user is not found, the procedure should not return an error, but simply an empty result set.

**Task 2: Dynamic SQL (Advanced)**
Write a script that dynamically selects data from a table. Assume you have two variables: `@TableName VARCHAR(50) = 'Users'` and `@ColumnName VARCHAR(50) = 'Name'`.
Construct the dynamic SQL string and execute it safely using `sp_executesql` to prevent injection.

---

### Next Steps
Stored Procedures are the backbone of backend database architecture. Try writing out the code for Task 1 and 2 and reply with your answers!
