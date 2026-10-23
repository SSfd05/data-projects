-- ============================================================
-- 04 复购间隔 + 流失预警
-- ============================================================

-- 每个订单的时间（一个订单可能有多行明细，先按订单去重）
CREATE OR REPLACE TABLE dim_order AS
SELECT
    customer_id,
    invoice_no,
    MIN(invoice_time) AS order_time
FROM fact_order
GROUP BY 1, 2;

-- 相邻两次下单的间隔天数：LAG 取同一客户的上一个订单
CREATE OR REPLACE TABLE ads_repeat_interval AS
SELECT
    customer_id,
    order_time,
    DATE_DIFF(
        'day',
        LAG(order_time) OVER (PARTITION BY customer_id ORDER BY order_time),
        order_time
    ) AS gap_days
FROM dim_order;

-- 客户级汇总
CREATE OR REPLACE TABLE ads_customer_summary AS
SELECT
    customer_id,
    COUNT(*)                          AS orders,
    ROUND(SUM(amount), 2)             AS gmv,
    MIN(invoice_time)                 AS first_order_time,
    MAX(invoice_time)                 AS last_order_time,
    DATE_DIFF('day', MAX(invoice_time),
              (SELECT MAX(invoice_time) FROM fact_order)) AS recency_days
FROM fact_order
GROUP BY 1;

-- 流失预警名单：买过 2 次以上、但已经 90 天没回来
CREATE OR REPLACE TABLE ads_churn_risk AS
SELECT
    customer_id,
    orders,
    gmv,
    recency_days,
    last_order_time
FROM ads_customer_summary
WHERE recency_days > 90 AND orders >= 2
ORDER BY gmv DESC;
