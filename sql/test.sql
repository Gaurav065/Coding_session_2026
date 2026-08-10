select e1.id, e1.salary,

1+ count(DISTINCT e2.salary) as d_rank
1+ count(e2.salary) as rk 
from employees e1
join employees e2 on e2.salary > e1.salary
group by e1.id, e1. salary
order by e1.salary asc