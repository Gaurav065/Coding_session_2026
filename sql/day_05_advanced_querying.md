# Day 5: Advanced Querying & Restructuring

Welcome to Day 5! Today we tackle subqueries, CTEs, and pivoting. These techniques allow you to write incredibly complex, multi-step data transformations within a single SQL statement.

---

## 1. Theory Deep Dive

### Subqueries
A subquery is a query nested inside another query (e.g., inside a `SELECT`, `INSERT`, `UPDATE`, or `DELETE` statement, or inside another subquery).
* **Standard Subquery:** Executes once, and its result is used by the outer query. Often used in the `WHERE` clause (e.g., `WHERE UserID IN (SELECT UserID FROM ActiveUsers)`).
* **Correlated Subquery:** A subquery that references columns from the outer query. It evaluates *once for every row* processed by the outer query. Consequently, they can be very slow for large datasets.

### Common Table Expressions (CTEs)
A CTE provides a temporary, named result set that you can reference within a `SELECT`, `INSERT`, `UPDATE`, or `DELETE` statement. They are created using the `WITH` keyword.
* **Benefits:** They make complex queries much more readable compared to nested subqueries. They can also be referenced multiple times within the main query.
* **Multiple CTEs:** You can define multiple CTEs in a single `WITH` clause, separated by commas.
* **Recursive CTEs:** A CTE that references itself. Extremely powerful for querying hierarchical data, like an organizational chart or folder structures.

### PIVOT and UNPIVOT
* **`PIVOT`**: Rotates a table-valued expression by turning the unique values from one column in the expression into multiple columns in the output. Useful for cross-tabulation reporting (e.g., turning "Month" rows into 12 "Month" columns).
* **`UNPIVOT`**: Performs the reverse operation of PIVOT. It rotates columns of a table-valued expression into column values. Useful when data is provided in a wide format and needs to be normalized.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Netflix)** What is the difference between a CTE and a Temporary Table? When would you use one over the other?
2. **(Meta)** Why might a Correlated Subquery cause performance issues compared to a Standard Subquery or a Join?
3. **(General Data Eng)** Can you UPDATE data within a CTE? If so, what is actually being updated?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You have a table of employee salaries: `EmployeeSalaries (EmpID, Department, Salary)`.

**Task 1: The Correlated Subquery Challenge**
Write a query to find all employees whose salary is higher than the average salary of their *own* department. You must use a Correlated Subquery to solve this.

**Task 2: The CTE Challenge**
Rewrite the exact same logic from Task 1, but this time use a Common Table Expression (CTE) and a JOIN instead of a correlated subquery. 

**Task 3: PIVOT Challenge**
Assume you have sales data: `Sales (Year, Quarter, Amount)`. 
Write a PIVOT query to display the `Year` as rows, and the Quarters (`Q1`, `Q2`, `Q3`, `Q4`) as columns showing the `SUM(Amount)`.

---

### Next Steps
CTEs are an industry standard for readable SQL code. Make sure you are comfortable with Task 2. Reply with your SQL code when ready!
