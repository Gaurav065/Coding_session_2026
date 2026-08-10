# Day 7: Control Flow, State Management & Transactions

Welcome to Day 7! Today is about managing state during complex operations, handling errors gracefully, and understanding how data is safely committed to disk.

---

## 1. Theory Deep Dive

### Temporary Tables
Used to store data temporarily during a session.
* **Local Temp Tables (`#TempTable`):** Visible only to the current connection/session. Dropped automatically when the session closes.
* **Global Temp Tables (`##TempTable`):** Visible to *all* connections. Dropped when the creating session closes AND all other sessions stop referencing it.
* **Table Variables (`@TableVar`):** Live in memory (mostly). Generally used for smaller datasets as they don't generate statistics like temp tables do.

### The MERGE Statement
Provides a way to perform `INSERT`, `UPDATE`, or `DELETE` operations on a target table based on the results of a join with a source table. Often referred to as "UPSERT".
* Highly useful in Data Warehousing for synchronizing dimension tables.
* Consists of `WHEN MATCHED`, `WHEN NOT MATCHED BY TARGET`, and `WHEN NOT MATCHED BY SOURCE` clauses.

### Error Handling
* **`TRY...CATCH`:** Allows for robust error handling. If an error occurs in the `TRY` block, control is immediately passed to the `CATCH` block.
* Functions like `ERROR_NUMBER()`, `ERROR_MESSAGE()`, and `ERROR_SEVERITY()` can be used inside the `CATCH` block to log the error.

### Transactions
A transaction is a single logical unit of work. SQL Server adheres to **ACID** properties (Atomicity, Consistency, Isolation, Durability).
* `BEGIN TRAN`: Starts the transaction.
* `COMMIT TRAN`: Saves the changes permanently.
* `ROLLBACK TRAN`: Reverts the changes if an error occurred.
* **Isolation Levels:** Control how locks are held. Common levels include `READ UNCOMMITTED` (allows dirty reads), `READ COMMITTED` (default), and `SERIALIZABLE`.

### Cursors
Cursors allow row-by-row processing of a result set.
* **Warning:** In a set-based language like SQL, cursors are notoriously slow and should generally be avoided unless absolutely necessary (e.g., executing a dynamic SP for every row in a table).
* Lifecycle: `DECLARE`, `OPEN`, `FETCH NEXT`, `CLOSE`, `DEALLOCATE`.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Amazon)** Explain the ACID properties of a database transaction.
2. **(Stripe)** You need to store temporary intermediate data for a complex calculation. When would you choose a Local Temp Table (`#Temp`) versus a Table Variable (`@Table`)?
3. **(Uber)** Your team is using a `CURSOR` to update salaries for 500,000 employees. It's taking hours. How would you optimize this?
4. **(Data Engineering General)** What is a "Dirty Read" and which Transaction Isolation Level allows it?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You have a `SourceUsers` table (incoming new data) and a `TargetUsers` table (your production table). Both have `(UserID, UserName, Email)`.

**Task 1: The MERGE Challenge (UPSERT)**
Write a `MERGE` statement to synchronize `TargetUsers` with `SourceUsers`.
- If the `UserID` exists in both, UPDATE the Name and Email in Target.
- If the `UserID` exists in Source but not in Target, INSERT the record into Target.
- *(Optional)* If the `UserID` exists in Target but not in Source, DELETE it from Target.

**Task 2: Transaction and Error Handling**
Wrap a simple `INSERT` statement inside a `TRY...CATCH` block. Ensure the `INSERT` is part of a transaction (`BEGIN TRAN`). If the `INSERT` succeeds, `COMMIT`. If it fails, `ROLLBACK` and print the `ERROR_MESSAGE()`.

---

### Next Steps
Understanding Transactions and MERGE is essential for Architect and Data Engineer roles. Give the tasks a try!
