-- ============================================================
-- 03 DWS 层：按主题做轻聚合
-- 原则：把"客户"和"商品"两个分析主题各自汇总好，
--      ADS 层就直接拿来用，不用重复算。
-- ============================================================

-- ---------- 主题一：客户宽表 ----------
CREATE OR REPLACE TABLE dws_customer AS
SELECT
    customer_id,
    COUNT(DISTINCT invoice_no)                        AS orders,
    SUM(quantity)                                     AS units,
    ROUND(SUM(amount), 2)                             AS gmv,
    ROUND(SUM(amount) / COUNT(DISTINCT invoice_no), 2) AS aov,
    MIN(invoice_time)                                 AS first_order_time,
    MAX(invoice_time)                                 AS last_order_time,
    DATE_DIFF('day', MAX(invoice_time),
              (SELECT MAX(invoice_time) FROM dwd_order_detail)) AS recency_days
FROM dwd_order_detail
GROUP BY 1;

-- ---------- 主题二：商品 × 日 ----------
CREATE OR REPLACE TABLE dws_product_daily AS
SELECT
    date_key,
    stock_code,
    SUM(quantity)        AS units,
    ROUND(SUM(amount), 2) AS gmv
FROM dwd_order_detail
GROUP BY 1, 2;
