# Day 1: Foundations, Database Design & Normalization

Welcome to Day 1! Today we are building the foundation of relational databases and structuring data correctly. These concepts are heavily tested in system design and data engineering interviews.

---

## 1. Theory Deep Dive

### SQL Basics & Environment
* **SQL (Structured Query Language):** The standard language for relational database management systems (RDBMS). It is essential for managing, querying, and structuring structured data.
* **SQL Server & SSMS:** SQL Server is Microsoft's RDBMS. SQL Server Management Studio (SSMS) is the integrated environment used to manage SQL Server infrastructure and write queries.
* **Authentication:**
  * *Windows Authentication:* Uses Windows credentials. It's more secure as credentials aren't passed over the network.
  * *SQL Server Authentication:* Uses a username and password created within SQL Server. Necessary for cross-domain or web applications.
* **Connectivity:** Involves standard protocols like TCP/IP. You connect using a Connection String containing the Server Name, Database Name, and Authentication details.

### Data Types
Choosing the right data type is crucial for performance and storage efficiency (an architect-level concern).
* `INT`: Integer values. (Uses 4 bytes. Range: -2B to +2B). Use for standard IDs.
* `VARCHAR(n)`: Variable-length string. Uses exactly the space needed plus 2 bytes. (`CHAR(n)` uses fixed space).
* `NVARCHAR(n)`: Stores Unicode characters (multiple languages). Takes 2x the space of `VARCHAR`.
* `DATETIME` / `DATETIME2`: `DATETIME2` is generally preferred now as it has a larger date range and higher fractional seconds precision.

### SQL Commands
* **DDL (Data Definition Language):** Defines structure. `CREATE`, `ALTER`, `DROP`, `TRUNCATE`. *(Note: TRUNCATE is DDL, it resets identity seeds and cannot be rolled back in some older contexts, though SQL Server allows rollback if in a transaction).*
* **DML (Data Manipulation Language):** Manipulates data. `INSERT`, `UPDATE`, `DELETE`.
* **DCL (Data Control Language):** Manages permissions. `GRANT`, `REVOKE`.

### Constraints
Rules enforced on data columns to ensure **Data Integrity**.
* `PRIMARY KEY (PK)`: Uniquely identifies a row. Cannot be NULL. Creates a Clustered Index by default.
* `FOREIGN KEY (FK)`: Ensures referential integrity between tables. A value in the FK column must exist in the referenced PK column.
* `UNIQUE`: Ensures all values are different. Allows *one* NULL value in SQL Server.
* `CHECK`: Ensures values satisfy a specific condition (e.g., `Age >= 18`).
* `DEFAULT`: Sets a default value if none is provided.

### Normalization
The process of organizing data to reduce redundancy and improve data integrity.
* **1NF (First Normal Form):** Every column must be atomic (no comma-separated lists). Each row must be unique.
* **2NF (Second Normal Form):** Must be in 1NF, and all non-key attributes must be fully dependent on the *entire* primary key (eliminates partial dependency in composite keys).
* **3NF (Third Normal Form):** Must be in 2NF, and all non-key attributes must not depend on other non-key attributes (eliminates transitive dependency). *Rule of thumb: Every non-key attribute must provide a fact about the key, the whole key, and nothing but the key.*
* **BCNF (Boyce-Codd Normal Form):** A stricter version of 3NF. For every non-trivial functional dependency X -> Y, X must be a superkey.

---

## 2. Top Company Interview Questions (Verbal/Theory)

> [!TIP]
> Try to answer these mentally before looking up the answers. These are real questions asked by top tech companies.

1. **(Amazon)** What is the difference between `DELETE` and `TRUNCATE`? Which one is faster and why?
2. **(Microsoft)** Can a table have multiple `UNIQUE` constraints? Can a `UNIQUE` constraint contain `NULL` values?
3. **(Meta)** Explain the difference between 3NF and BCNF with a real-world example.
4. **(Google)** Why might you choose *Denormalization* over Normalization in a data warehouse environment?
5. **(Netflix)** You are designing a database for a global application. When would you choose `VARCHAR` vs `NVARCHAR`? What are the performance implications?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You are an architect designing the core tables for an e-commerce platform.

**Task 1: Design & Create Tables**
Write the T-SQL to create the following two tables. Pay close attention to choosing optimal data types and enforcing data integrity using constraints.

*Table 1: `Customers`*
- ID (Must auto-increment, primary key)
- Email (Must be unique, cannot be empty)
- RegistrationDate (Default to the current date/time)

*Table 2: `Orders`*
- OrderID (Must auto-increment, primary key)
- CustomerID (Must relate to the Customers table)
- TotalAmount (Must be greater than 0, capable of storing currency up to 99,999.99)
- Status (Should only allow values: 'Pending', 'Shipped', 'Delivered', 'Cancelled')

**Task 2: Normalization Fix**
You are given the following poorly designed table:
`EmployeeProjects (EmpID, EmpName, Department, ProjectID, ProjectName, ProjectBudget)`
Identify the normalization violations and write the DDL to break this up into a 3NF-compliant structure.

---

### Next Steps
Take your time to review the theory. 
Whenever you are ready, **reply with your answers to the Interview Questions or the SQL code for the Live Coding Challenge**, and I will review it like a real interviewer!
