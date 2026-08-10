if  EXISTS

USE CTE_practice_db;
Go


CREATE TABLE Employees (
    employee_id INT PRIMARY KEY,
    employee_name VARCHAR(100),
    department_id INT,
    manager_id INT NULL,
    salary DECIMAL(10,2),
    hire_date DATE
);


CREATE TABLE Departments (
    department_id INT PRIMARY KEY,
    department_name VARCHAR(100)
);


CREATE TABLE Orders (
    order_id INT PRIMARY KEY,
    customer_id INT,
    order_date DATE,
    order_amount DECIMAL(10,2)
);

CREATE TABLE Customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(100),
    city VARCHAR(100)
);


CREATE TABLE Products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10,2)
);

CREATE TABLE Order_Items (
    order_item_id INT PRIMARY KEY,
    order_id INT,
    product_id INT,
    quantity INT,
    total_price DECIMAL(10,2)
);


INSERT INTO Departments VALUES
(1, 'Engineering'),
(2, 'HR'),
(3, 'Sales'),
(4, 'Finance');

INSERT INTO Employees VALUES
(1, 'Alice', 1, NULL, 120000, '2018-01-10'),
(2, 'Bob', 1, 1, 90000, '2019-03-15'),
(3, 'Charlie', 2, NULL, 70000, '2020-06-20'),
(4, 'David', 3, NULL, 80000, '2017-08-10'),
(5, 'Eva', 1, 2, 60000, '2021-09-25'),
(6, 'Frank', 3, 4, 75000, '2019-11-30'),
(7, 'Grace', 4, NULL, 95000, '2016-04-18');


INSERT INTO Customers VALUES
(1, 'John', 'Delhi'),
(2, 'Jane', 'Mumbai'),
(3, 'Mike', 'Bangalore'),
(4, 'Sara', 'Delhi');


INSERT INTO Orders VALUES
(101, 1, '2023-01-10', 500),
(102, 2, '2023-02-15', 700),
(103, 1, '2023-03-01', 300),
(104, 3, '2023-03-05', 900),
(105, 4, '2023-04-10', 400);

INSERT INTO Products VALUES
(1, 'Laptop', 'Electronics', 1000),
(2, 'Phone', 'Electronics', 600),
(3, 'Desk', 'Furniture', 200),
(4, 'Chair', 'Furniture', 150);

INSERT INTO Order_Items VALUES
(1, 101, 1, 1, 1000),
(2, 101, 2, 1, 600),
(3, 102, 3, 2, 400),
(4, 103, 4, 2, 300),
(5, 104, 1, 1, 1000),
(6, 105, 2, 1, 600);

