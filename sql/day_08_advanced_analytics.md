# Day 8: Advanced Analytics & Windowing

Welcome to Day 8! Window functions are arguably the most powerful analytical feature in SQL. They allow you to perform calculations across a set of table rows that are related to the current row, *without* collapsing the result set (unlike `GROUP BY`).

---

## 1. Theory Deep Dive

### Window Functions Overview
A window function performs a calculation across a set of rows (a "window") using the `OVER()` clause.
* **`PARTITION BY`**: Divides the result set into partitions (similar to `GROUP BY`, but doesn't collapse rows).
* **`ORDER BY`**: Defines the logical order of rows within each partition.

### Ranking Functions
Used to rank rows within a partition.
* **`ROW_NUMBER()`**: Assigns a unique, sequential integer to each row within a partition. (1, 2, 3, 4)
* **`RANK()`**: Assigns a rank. If there's a tie, the same rank is given, and the next rank is skipped. (1, 1, 3, 4)
* **`DENSE_RANK()`**: Similar to `RANK()`, but does *not* skip the next rank after a tie. (1, 1, 2, 3)

### Analytical/Offset Functions
Used to look at data in other rows relative to the current row.
* **`LEAD(column, offset)`**: Accesses data from a *subsequent* row in the same result set.
* **`LAG(column, offset)`**: Accesses data from a *previous* row in the same result set.

### Windowed Aggregate Functions
You can use standard aggregates (`SUM`, `AVG`, `MIN`, `MAX`) with the `OVER()` clause.
* *Example:* `SUM(Salary) OVER (PARTITION BY Department)` calculates the total departmental salary and attaches it to every employee's row.
* **Running Totals:** `SUM(Sales) OVER (ORDER BY Date)` calculates a cumulative running total.

### String Aggregation
* **`STRING_AGG(column, separator)`**: (Available in SQL Server 2017+). Concatenates the values of string expressions and places separator values between them. Replaces the older, clunky `FOR XML PATH` workaround.

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Meta)** Explain the difference between `RANK()`, `DENSE_RANK()`, and `ROW_NUMBER()`. Give an example scenario for each.
2. **(Netflix)** You want to calculate the week-over-week difference in sales. Which window function would you use and why?
3. **(Google)** Is it possible to use a Window Function in a `WHERE` clause directly? (e.g., `WHERE ROW_NUMBER() OVER(...) = 1`). If not, how do you work around it?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You have a `Sales` table: `(SalesID, Salesperson, SaleDate, Amount)`.

**Task 1: Running Total**
Write a query to display each sale, along with a "Running Total" of the `Amount` for each `Salesperson`, ordered chronologically by `SaleDate`.

**Task 2: Finding Top Performers (The Nth Record Problem)**
Write a query to find the top 3 highest sales amounts for *each* `Salesperson`. If there are ties for 3rd place, include them (Hint: Use `DENSE_RANK`). Since you can't use window functions in a WHERE clause, you must wrap this in a CTE or Subquery!

**Task 3: Previous Row Comparison (LAG)**
Write a query to show each sale, and in a new column called `PreviousSaleAmount`, show the amount of the *previous* sale made by that same `Salesperson`.

---

### Next Steps
Window functions are a staple in FAANG data interviews. Mastering `ROW_NUMBER()` inside a CTE to find "Top N per category" is a required skill. Reply with your answers!
