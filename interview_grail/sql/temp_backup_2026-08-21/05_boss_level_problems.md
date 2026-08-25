# Module 05: The Wilderness Boss SQL Problems & Mastery Solutions

This module contains the rarest, highest-difficulty SQL problems asked in Staff/Principal Data Engineering and quantitative finance interviews.

---

## 👹 Boss Problem 1: Gaps & Islands (Multi-Method Breakdown)

### Problem Statement:
Given a table of user login dates, identify all **continuous login streaks** (islands) per user, returning `user_id`, `streak_start_date`, `streak_end_date`, and `streak_length_days`.

```sql
-- Schema & Sample Data:
CREATE TABLE UserLogins (
    user_id INT,
    login_date DATE
);
```

### Method 1: The Difference of Ranks Technique (`ROW_NUMBER()` Offset)
**Mathematical Intuition**: If dates are consecutive ($D, D+1, D+2\dots$) and row numbers are consecutive ($1, 2, 3\dots$), then the mathematical difference:
$$\text{Island Group Key} = \text{login\_date} - \text{ROW\_NUMBER}() \text{ days}$$
remains **strictly constant** across all dates in the same continuous streak!

```sql
WITH RankedLogins AS (
    SELECT 
        user_id,
        login_date,
        -- Deduplicate logins on same day first if necessary:
        ROW_NUMBER() OVER (
            PARTITION BY user_id 
            ORDER BY login_date
        ) AS rn
    FROM (SELECT DISTINCT user_id, login_date FROM UserLogins) d
),
GroupedIslands AS (
    SELECT 
        user_id,
        login_date,
        -- Subtract rn days from login_date to form the immutable island anchor:
        DATEADD(day, -rn, login_date) AS island_key -- (In Postgres: login_date - (rn * INTERVAL '1 day'))
    FROM RankedLogins
)
SELECT 
    user_id,
    MIN(login_date) AS streak_start_date,
    MAX(login_date) AS streak_end_date,
    COUNT(*) AS streak_length_days
FROM GroupedIslands
GROUP BY user_id, island_key
HAVING COUNT(*) >= 1
ORDER BY user_id, streak_start_date;
```

---

## 👹 Boss Problem 2: Peak Concurrency (The Delta-Sweep / Point-Event Algorithm)

### Problem Statement:
Given a table of server jobs with `start_time` and `end_time`, find the **maximum number of concurrently running jobs** across the entire cluster and the exact time interval when this peak occurred.

```sql
CREATE TABLE ServerJobs (
    job_id INT,
    start_time TIMESTAMP,
    end_time TIMESTAMP
);
```

### The $O(N \log N)$ Delta-Sweep Algorithm:
Instead of expensive pairwise $O(N^2)$ interval overlap joins, convert each interval into two discrete point events:
- At `start_time`, concurrency increases by `+1`.
- At `end_time`, concurrency decreases by `-1`.

```sql
WITH PointEvents AS (
    -- Start event (+1)
    SELECT start_time AS event_time, 1 AS delta FROM ServerJobs
    UNION ALL
    -- End event (-1)
    SELECT end_time AS event_time, -1 AS delta FROM ServerJobs
),
AggregatedPoints AS (
    -- Aggregate deltas occurring at the exact same timestamp
    SELECT event_time, SUM(delta) AS net_delta
    FROM PointEvents
    GROUP BY event_time
),
RunningConcurrency AS (
    SELECT 
        event_time AS window_start,
        LEAD(event_time) OVER (ORDER BY event_time) AS window_end,
        SUM(net_delta) OVER (
            ORDER BY event_time 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS active_jobs
    FROM AggregatedPoints
),
MaxPeak AS (
    SELECT MAX(active_jobs) AS peak_count FROM RunningConcurrency
)
SELECT 
    rc.window_start,
    rc.window_end,
    rc.active_jobs AS peak_concurrency
FROM RunningConcurrency rc
JOIN MaxPeak mp ON rc.active_jobs = mp.peak_count;
```

---

## 👹 Boss Problem 3: Dynamic Inactivity-Based Sessionization

### Problem Statement:
Given a clickstream table with `user_id`, `event_time`, and `page_url`, group events into **User Sessions**, where a new session begins whenever there is an **inactivity gap of 30 minutes or more** since the previous event for that user. Assign a unique incremental `session_id` per user.

```sql
WITH EventDeltas AS (
    SELECT 
        user_id,
        event_time,
        page_url,
        LAG(event_time) OVER (
            PARTITION BY user_id 
            ORDER BY event_time
        ) AS prev_event_time
    FROM Clickstream
),
SessionFlags AS (
    SELECT 
        user_id,
        event_time,
        page_url,
        -- Flag = 1 if inactivity gap >= 30 minutes OR if it's the user's first event:
        CASE 
            WHEN prev_event_time IS NULL THEN 1
            WHEN DATEDIFF(minute, prev_event_time, event_time) >= 30 THEN 1
            ELSE 0 
        END AS is_new_session
    FROM EventDeltas
)
SELECT 
    user_id,
    event_time,
    page_url,
    -- Running sum of session flags generates the dynamic session_id:
    SUM(is_new_session) OVER (
        PARTITION BY user_id 
        ORDER BY event_time 
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS session_id
FROM SessionFlags
ORDER BY user_id, event_time;
```

---

## 👹 Boss Problem 4: FIFO Inventory Accounting & Realized P&L

### Problem Statement:
You have a stock ledger with `BUY` and `SELL` transactions. Calculate the **realized profit/loss** for each sell order by consuming shares from prior purchase lots strictly under **FIFO (First-In, First-Out)** order.

```sql
CREATE TABLE StockTrades (
    trade_id INT,
    symbol VARCHAR(10),
    trade_type VARCHAR(4), -- 'BUY' or 'SELL'
    shares INT,
    price DECIMAL(10,2),
    trade_time TIMESTAMP
);
```

### Pure SQL Solution with Running Balances:
```sql
WITH CumulativeTrades AS (
    SELECT 
        trade_id, symbol, trade_type, shares, price, trade_time,
        -- Running total of shares bought up to this trade
        SUM(CASE WHEN trade_type = 'BUY' THEN shares ELSE 0 END) OVER (
            PARTITION BY symbol ORDER BY trade_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cum_buy_shares,
        -- Running total of shares sold up to this trade
        SUM(CASE WHEN trade_type = 'SELL' THEN shares ELSE 0 END) OVER (
            PARTITION BY symbol ORDER BY trade_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cum_sell_shares
    FROM StockTrades
),
BuyLots AS (
    SELECT 
        trade_id AS buy_id, symbol, shares AS buy_shares, price AS buy_price, trade_time AS buy_time,
        cum_buy_shares - buy_shares AS buy_range_start,
        cum_buy_shares AS buy_range_end
    FROM CumulativeTrades WHERE trade_type = 'BUY'
),
SellLots AS (
    SELECT 
        trade_id AS sell_id, symbol, shares AS sell_shares, price AS sell_price, trade_time AS sell_time,
        cum_sell_shares - sell_shares AS sell_range_start,
        cum_sell_shares AS sell_range_end
    FROM CumulativeTrades WHERE trade_type = 'SELL'
),
MatchedLots AS (
    SELECT 
        s.sell_id, s.symbol, s.sell_time, s.sell_price,
        b.buy_id, b.buy_time, b.buy_price,
        -- Overlapping shares between the sell range and buy range:
        (CASE WHEN s.sell_range_end < b.buy_range_end THEN s.sell_range_end ELSE b.buy_range_end END) -
        (CASE WHEN s.sell_range_start > b.buy_range_start THEN s.sell_range_start ELSE b.buy_range_start END) AS matched_shares
    FROM SellLots s
    JOIN BuyLots b 
      ON s.symbol = b.symbol
     AND s.sell_range_start < b.buy_range_end
     AND s.sell_range_end > b.buy_range_start
)
SELECT 
    sell_id, symbol, sell_time,
    SUM(matched_shares) AS total_sold_shares,
    SUM(matched_shares * sell_price) AS total_sell_proceeds,
    SUM(matched_shares * buy_price) AS total_cost_basis,
    SUM(matched_shares * (sell_price - buy_price)) AS realized_profit_loss
FROM MatchedLots
GROUP BY sell_id, symbol, sell_time
ORDER BY symbol, sell_time;
```

---

## 👹 Boss Problem 5: Graph Cycle Detection with Recursive CTEs

### Problem Statement:
Given an employee manager hierarchy `Employees(emp_id, manager_id, name)`, traverse the tree starting from the top-level executives, compute employee level/depth and full reporting path string (`"CEO -> VP -> Director -> Emp"`), and **detect circular references (cycles)** without infinite looping!

```sql
WITH RECURSIVE Hierarchy AS (
    -- Anchor Member: Root Nodes (CEOs / Top Managers with NULL manager_id)
    SELECT 
        emp_id,
        manager_id,
        name,
        1 AS level,
        CAST(name AS VARCHAR(1000)) AS path_str,
        ARRAY[emp_id] AS visited_ids, -- In Postgres: ARRAY[emp_id]
        FALSE AS is_cycle
    FROM Employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive Member: Traverse Children
    SELECT 
        e.emp_id,
        e.manager_id,
        e.name,
        h.level + 1,
        CAST(h.path_str || ' -> ' || e.name AS VARCHAR(1000)),
        h.visited_ids || e.emp_id,
        -- Cycle detected if current emp_id already exists in ancestor visited array:
        e.emp_id = ANY(h.visited_ids) AS is_cycle
    FROM Employees e
    JOIN Hierarchy h ON e.manager_id = h.emp_id
    -- STOP recursion immediately if cycle encountered:
    WHERE NOT h.is_cycle AND NOT (e.emp_id = ANY(h.visited_ids))
)
SELECT 
    emp_id,
    name,
    manager_id,
    level,
    path_str,
    is_cycle
FROM Hierarchy
ORDER BY level, path_str;
```
