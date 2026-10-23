-- ============================================================
-- 02 留存：cohort（同期群）分析
-- 核心思路：先给每个客户定一个"首购月"，再看他之后每个月有没有回来
-- ============================================================

-- 每个客户的首购月（决定他属于哪个 cohort）
CREATE OR REPLACE TABLE dim_first_purchase AS
SELECT
    customer_id,
    DATE_TRUNC('month', MIN(invoice_time)) AS first_month
FROM fact_order
GROUP BY 1;

-- 每个客户每个月的活跃记录
CREATE OR REPLACE TABLE fact_activity AS
SELECT DISTINCT
    customer_id,
    DATE_TRUNC('month', invoice_time) AS act_month
FROM fact_order;

-- 每个 cohort 的规模（留存率的分母）
CREATE OR REPLACE TABLE cohort_size AS
SELECT first_month, COUNT(*) AS cohort_customers
FROM dim_first_purchase
GROUP BY 1;

-- 留存矩阵：第 N 个月还有多少人回来
CREATE OR REPLACE TABLE ads_cohort_retention AS
SELECT
    f.first_month,
    DATE_DIFF('month', f.first_month, a.act_month) AS month_no,
    COUNT(DISTINCT a.customer_id)                  AS active_customers,
    s.cohort_customers,
    ROUND(COUNT(DISTINCT a.customer_id)::DOUBLE / s.cohort_customers, 4) AS retention_rate
FROM dim_first_purchase f
JOIN fact_activity a USING (customer_id)
JOIN cohort_size   s USING (first_month)
GROUP BY f.first_month,
         DATE_DIFF('month', f.first_month, a.act_month),
         s.cohort_customers
ORDER BY 1, 2;
