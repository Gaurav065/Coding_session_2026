# Day 4: Aggregation, Set Operations, & Joins

Welcome to Day 4! This is one of the most critical days. The ability to combine datasets and aggregate metrics is the absolute core of what makes SQL powerful.

---

## 1. Theory Deep Dive

### Aggregation & Grouping
* **`GROUP BY`**: Groups rows that have the same values into summary rows. Often used with aggregate functions.
* **Aggregate Functions**: `SUM()`, `AVG()`, `MIN()`, `MAX()`, `COUNT()`.
  - *Note:* `COUNT(*)` counts all rows including NULLs. `COUNT(column_name)` counts only non-NULL values in that column.
* **`HAVING`**: Filters groups *after* the `GROUP BY` aggregation has occurred. (Remember: `WHERE` filters before aggregation, `HAVING` filters after).

### Standard Joins
Joins combine columns from one or more tables based on a related column between them.
* **`INNER JOIN`**: Returns records that have matching values in both tables.
* **`LEFT JOIN` (Left Outer Join)**: Returns all records from the left table, and the matched records from the right table. The result is NULL from the right side if there is no match.
* **`RIGHT JOIN` (Right Outer Join)**: Returns all records from the right table, and the matched records from the left table.
* **`FULL JOIN` (Full Outer Join)**: Returns all records when there is a match in either left or right table.

### Complex Joins
* **`SELF JOIN`**: A regular join, but the table is joined with itself. Very useful for hierarchical data (e.g., Employees and their Managers stored in the same table).
* **`CROSS JOIN`**: Returns the Cartesian product of the two tables. If Table A has 5 rows and Table B has 5 rows, a CROSS JOIN returns 25 rows. No `ON` clause is used.

### Set Operations
Set operations combine the *results* of two or more queries into a single result set. Both queries must have the same number of columns with matching data types.
* **`UNION`**: Combines the result sets and **removes duplicates**.
* **`UNION ALL`**: Combines the result sets and **keeps duplicates**. It is faster than `UNION` because it doesn't have to scan for and remove duplicates.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Amazon)** Can you use an aggregate function in a `WHERE` clause? Why or why not?
2. **(Microsoft)** What is the difference between `UNION` and `UNION ALL`? Which one has better performance?
3. **(Google)** You have two tables: A and B. Table A has 5 rows, Table B has 10 rows. What is the maximum number of rows that can be returned by an `INNER JOIN`? What about a `CROSS JOIN`?
4. **(Meta)** Explain a scenario where you would use a `SELF JOIN`.

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You have two tables in a retail database:
`Departments (DeptID, DeptName)`
`Employees (EmpID, EmpName, DeptID, Salary, ManagerID)`

**Task 1: Aggregation and Filtering (HAVING)**
Write a query to find the `DeptID` and the Average Salary for departments where the Average Salary is greater than $80,000. 

**Task 2: Joins (LEFT JOIN & COALESCE)**
Write a query to list all `DeptName`s and the number of employees in each department. If a department has no employees, it should still appear in the list with a count of 0.

**Task 3: The SELF JOIN Challenge**
Write a query to display the `EmpName` and their manager's name (let's call the column `ManagerName`). Note that `ManagerID` corresponds to the `EmpID` of the manager in the same table. If an employee has no manager (i.e., they are the CEO), display 'No Manager'.

---

### Next Steps
Joins and aggregations are guaranteed to be in your technical interview. Write out your SQL solutions for Task 1, 2, and 3, and let's review them!
