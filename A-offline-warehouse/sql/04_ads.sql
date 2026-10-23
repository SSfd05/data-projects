-- ============================================================
-- 04 ADS 层：面向业务的指标宽表
-- 原则：每个指标只在这里定义一次，避免"同一个复购率三个部门三个数"。
-- ============================================================

-- ---------- 月度经营指标 ----------
CREATE OR REPLACE TABLE ads_kpi_monthly AS
SELECT
    DATE_TRUNC('month', invoice_time) AS stat_month,
    COUNT(DISTINCT invoice_no)        AS orders,
    COUNT(DISTINCT customer_id)       AS customers,
    ROUND(SUM(amount), 2)             AS gmv
FROM dwd_order_detail
GROUP BY 1
ORDER BY 1;

-- ---------- 国家维度排行 ----------
CREATE OR REPLACE TABLE ads_country_rank AS
SELECT
    country,
    ROUND(SUM(amount), 2)             AS gmv,
    COUNT(DISTINCT customer_id)       AS customers,
    COUNT(DISTINCT invoice_no)        AS orders
FROM dwd_order_detail
GROUP BY 1
ORDER BY gmv DESC;

-- ---------- 全局汇总（一个指标一行口径） ----------
CREATE OR REPLACE TABLE ads_kpi_summary AS
WITH base AS (
    SELECT
        COUNT(DISTINCT customer_id) AS customers,
        COUNT(DISTINCT invoice_no)  AS orders,
        SUM(amount)                 AS gmv
    FROM dwd_order_detail
),
repeat_cust AS (
    SELECT customer_id
    FROM dwd_order_detail
    GROUP BY 1
    HAVING COUNT(DISTINCT invoice_no) >= 2
),
returns AS (
    -- 退货单在 ODS 里是负数量，DWD 已经被过滤掉了，所以回 ODS 取
    SELECT ABS(SUM(quantity * unit_price)) AS return_amount
    FROM ods_retail
    WHERE invoice_no LIKE 'C%' AND quantity < 0
)
SELECT
    b.customers,
    b.orders,
    b.gmv,
    ROUND(b.gmv / b.orders, 2)                                     AS aov,
    ROUND((SELECT COUNT(*) FROM repeat_cust)::DOUBLE / b.customers, 4) AS repeat_rate,
    ROUND(r.return_amount / b.gmv, 4)                              AS return_amount_ratio
FROM base b, returns r;
