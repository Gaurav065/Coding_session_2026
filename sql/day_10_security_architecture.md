# Day 10: Security, Tracking, & Architecture Concepts

Welcome to Day 10! You made it to the final day. Today we focus on enterprise-level architecture: securing data, tracking historical changes, and data warehouse modeling.

---

## 1. Theory Deep Dive

### Security & Access Control
* **Views:** A virtual table based on the result-set of an SQL statement. Great for security because you can grant users access to a View (which hides sensitive columns) without giving them access to the underlying table.
* **Row-Level Security (RLS):** Restricts data access at the row level based on the user's execution context. (e.g., A regional manager can only query and see rows in the `Sales` table where `Region = 'East'`).
* **Dynamic Data Masking (DDM):** Limits sensitive data exposure by masking it to non-privileged users. (e.g., Masking a credit card to `XXXX-XXXX-XXXX-1234`).

### Triggers
A special kind of stored procedure that automatically executes when an event occurs in the database server.
* **DML Triggers:** Execute on `INSERT`, `UPDATE`, or `DELETE`. Can be `AFTER` (executes after the action) or `INSTEAD OF` (replaces the standard action).
* **DDL Triggers:** Execute in response to structural changes (`CREATE`, `ALTER`, `DROP`). Useful for auditing schema changes.
* **Logon Triggers:** Fire in response to a LOGON event.

### Tracking Changes (CDC)
* **Change Data Capture (CDC):** An SQL Server feature that records insert, update, and delete activity applied to tables. It reads the transaction log asynchronously, so it has minimal performance impact compared to Triggers. Extremely useful for ETL pipelines feeding a Data Warehouse.

### Slowly Changing Dimensions (SCD)
A concept used in Data Warehousing to manage data that changes slowly over time, rather than changing on a regular schedule.
* **Type 1 (Overwrite):** The old data is simply overwritten. No history is kept.
* **Type 2 (Add a new row):** Tracks historical data by creating multiple records for a given natural key with separate surrogate keys and/or different effective dates. (e.g., `ValidFrom`, `ValidTo`, `IsCurrent`).
* **Type 3 (Add a new column):** Keeps a limited history by adding a column (e.g., `PreviousState`). Rarely used.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Capital One)** How would you ensure that a Call Center employee can query a customer's Social Security Number, but only sees the last 4 digits, without changing the data in the physical table?
2. **(Snowflake/Data Eng)** Explain the difference between SCD Type 1 and SCD Type 2. When would you use Type 2?
3. **(Microsoft)** What are the performance implications of using a DML Trigger for auditing changes versus using Change Data Capture (CDC)?
4. **(Salesforce)** What is an `INSTEAD OF` trigger, and on what type of database object are they most commonly used?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You have a table `Products (ProductID, Price, LastUpdated)`. You want to maintain a history of price changes without using CDC.

**Task 1: Audit Trigger**
Write an `AFTER UPDATE` trigger on the `Products` table. 
Whenever a product's price is updated, the trigger should insert a record into a `ProductPriceHistory` table containing `(ProductID, OldPrice, NewPrice, ChangeDate)`. 
*(Hint: You will need to use the special `inserted` and `deleted` logical tables available inside triggers).*

**Task 2: SCD Type 2 Design (Conceptual/DDL)**
You are designing an SCD Type 2 table for `Employees` in your data warehouse to track when they change departments. Write the `CREATE TABLE` script. What extra columns do you need to add to the standard `(EmpID, Name, Department)` to make it a Type 2 dimension?

---

### Congratulations!
You have reached the end of the 10-Day Architect Masterclass! 
Whenever you are ready, tackle Day 10's questions, or let me know if you want to go back to **Day 1** and start the full mock interview process from the beginning!
