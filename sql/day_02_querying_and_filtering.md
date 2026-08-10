# Day 2: Querying, Filtering, & Handling Data Anomalies

Welcome to Day 2! Today we focus on how to retrieve exactly the data you need and handle missing or improperly formatted data, which is crucial for robust analysis.

---

## 1. Theory Deep Dive

### Querying Data
* **`SELECT`**: Determines which columns to return. Use `SELECT *` cautiously in production as it can pull unnecessary data and break if table schemas change. Always explicitly list columns.
* **`WHERE`**: Filters rows *before* any groupings or aggregations happen. You can use operators like `=`, `<>`, `>`, `<`, `IN`, `BETWEEN`, and `LIKE`.
* **`ORDER BY`**: Sorts the final result set. Can be `ASC` (default) or `DESC`. Note that SQL Server doesn't guarantee row order unless `ORDER BY` is explicitly used.

### Handling NULL Values
A `NULL` value means "unknown" or "missing". It is *not* zero, and it is *not* an empty string. `NULL = NULL` evaluates to `UNKNOWN`, not `TRUE`!
* **`ISNULL(check_expression, replacement_value)`**: Specifically for SQL Server. Replaces `NULL` with the specified replacement value.
* **`COALESCE(val1, val2, ... valN)`**: An ANSI SQL standard function. It evaluates arguments in order and returns the *first non-null* value. It's more flexible than `ISNULL` because it accepts multiple arguments.
* **`CASE` Statements**: Allows for complex IF-THEN-ELSE logic within a query.
  ```sql
  SELECT 
    EmployeeName, 
    CASE 
      WHEN Salary > 100000 THEN 'High'
      WHEN Salary > 50000 THEN 'Medium'
      ELSE 'Low' 
    END as SalaryBand
  FROM Employees;
  ```

### Data Type Conversion
Sometimes you need to compare or concatenate data of different types (e.g., a String and an Integer).
* **`CAST(expression AS data_type)`**: ANSI SQL standard. Generally preferred for portability across different database systems.
* **`CONVERT(data_type, expression, [style])`**: SQL Server specific. Highly useful because of the `[style]` parameter, which allows you to format dates and times (e.g., converting a datetime to 'YYYY-MM-DD').

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Apple)** What is the difference between `ISNULL()` and `COALESCE()`? Which one is standard SQL?
2. **(Stripe)** If you execute `SELECT * FROM Users WHERE Age <> 25`, will it return users where Age is `NULL`? Why or why not?
3. **(Uber)** You need to concatenate a `VARCHAR` column "Name" and an `INT` column "Age". How do you prevent a type conversion error in SQL Server?
4. **(Data Engineering General)** What is the execution order of `SELECT`, `FROM`, `WHERE`, and `ORDER BY` in a query?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You are analyzing a table of user subscriptions: `Subscriptions (SubID, UserID, PlanType, CancelDate)`.

**Task 1: The COALESCE Challenge**
Write a query to retrieve all subscriptions. Include a calculated column called `CurrentStatus`. 
- If `CancelDate` is NULL, the status should be 'Active'.
- If `CancelDate` has a value, the status should be 'Cancelled'.

**Task 2: The Date Conversion Challenge**
Write a query to return the `UserID` and a concatenated string that reads: `"User [UserID] cancelled on [CancelDate]"`. You must ensure the `CancelDate` is formatted as `YYYY-MM-DD` (Hint: Use `CONVERT` with style `23`). If `CancelDate` is null, do not include the user in the results.

---

### Next Steps
Review the theory and try out the questions! When you are ready, reply with your answers, and we can discuss them!
