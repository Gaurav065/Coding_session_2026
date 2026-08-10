USE CTE_practice_db;
GO


with avg_employee_salary as(
    select
        avg(salary) as mean_salary
    from Employees
),
dept_avg_cte as(
    SELECT
        department_id,
        avg(salary) as mean_salary
    from Employees
    GROUP BY department_id
),
filterd_emp as(
    select e.* 
    from Employees e
    join dept_avg_cte d 
    on d.department_id = e.department_id
    WHERE e.salary > d.mean_salary
),
over_avg as(
    select department_id, avg(salary) as filtered_avg
    from filterd_emp
    group by department_id

)




select department_id, mean_salary 
from dept_avg_cte
where mean_salary>80000;