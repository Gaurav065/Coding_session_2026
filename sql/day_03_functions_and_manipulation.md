# Day 3: Built-in Functions & Data Manipulation

Welcome to Day 3! Today we look at how to manipulate strings, dates, and numbers on the fly using SQL Server's powerful built-in scalar functions.

---

## 1. Theory Deep Dive

### Date Functions
Dates are often stored in UTC and need to be manipulated for reporting.
* **`GETDATE()`**: Returns the current database system timestamp.
* **`DATEDIFF(datepart, startdate, enddate)`**: Returns the count (as a signed integer) of the specified `datepart` boundaries crossed between the start and end dates. 
  - *Example:* `DATEDIFF(day, '2023-01-01', '2023-01-10')` returns `9`.
* **`DATEPART(datepart, date)`**: Returns an integer representing the specified `datepart` (e.g., year, month, day) of the specified date.
  - *Example:* `DATEPART(year, '2023-01-01')` returns `2023`.
* **`DATEADD(datepart, number, date)`**: Adds a specific interval to a date.

### String Functions
Cleaning up user input or formatting text for applications.
* **`UPPER(string)` / `LOWER(string)`**: Converts strings to all uppercase or lowercase.
* **`LEFT(string, n)` / `RIGHT(string, n)`**: Extracts `n` characters from the left or right side of a string.
* **`SUBSTRING(string, start, length)`**: Extracts a portion of a string starting at a specific position for a specified length. (Note: 1-indexed in SQL).
* **`LEN(string)`**: Returns the number of characters in a string (excludes trailing spaces).
* **`REPLACE(string, old_string, new_string)`**: Replaces occurrences of a substring.

### Numeric Functions
Handling financial calculations and rounding.
* **`ROUND(numeric_expr, length)`**: Rounds a value to a specified precision. (e.g., `ROUND(12.345, 2)` -> `12.35`).
* **`CEILING(numeric_expr)`**: Returns the smallest integer greater than or equal to the expression. (e.g., `CEILING(12.1)` -> `13`).
* **`FLOOR(numeric_expr)`**: Returns the largest integer less than or equal to the expression. (e.g., `FLOOR(12.9)` -> `12`).

---

## 2. Top Company Interview Questions (Verbal/Theory)

1. **(Salesforce)** How do you find the first day of the current month using SQL Server date functions?
2. **(Spotify)** You have a `FullName` column (e.g., "John Doe"). How would you use string functions to extract just the First Name?
3. **(Finance/Banking)** What is the difference between `ROUND(4.55, 1)` and `FLOOR(4.55)`?

---

## 3. Scenario-Based Live Coding Challenge

**Scenario:** You are generating a report for an HR database with table `Employees (EmpID, Email, HireDate, Salary)`.

**Task 1: Date Math**
Write a query to find all employees who have been with the company for exactly 5 years as of today. Use `DATEDIFF` and `GETDATE()`.

**Task 2: String Extraction**
Assuming all emails follow the format `firstname.lastname@company.com`, write a query to extract the domain of the email (i.e., everything after the `@` symbol) and return it in a new column called `EmailDomain`.
*Hint: You will need to use `SUBSTRING`, `LEN`, and `CHARINDEX('@', Email)` to find the position of the @ symbol.*

---

### Next Steps
Try writing out the SQL for these tasks. Manipulating strings and dates is one of the most common tasks required in live coding interviews for data roles!
