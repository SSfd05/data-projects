-- ============================================================
-- 03 DWS 层：按主题做轻聚合
--
-- 客户主题必须过滤 customer_id 非空；商品主题保留全部销售，
-- 否则商品销量会被「只有会员才计入」这条规则带偏。
-- ============================================================

CREATE OR REPLACE TABLE dws_customer AS
SELECT
    customer_id,
    COUNT(DISTINCT invoice_no)                         AS orders,
    SUM(quantity)                                      AS units,
    ROUND(SUM(amount), 2)                              AS gmv,
    ROUND(SUM(amount) / COUNT(DISTINCT invoice_no), 2)  AS aov,
    MIN(invoice_time)                                  AS first_order_time,
    MAX(invoice_time)                                  AS last_order_time,
    DATE_DIFF('day', MAX(invoice_time),
              (SELECT MAX(invoice_time) FROM dwd_order_detail)) AS recency_days
FROM dwd_order_detail
WHERE customer_id IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE TABLE dws_product_daily AS
SELECT
    date_key,
    stock_code,
    SUM(quantity)         AS units,
    ROUND(SUM(amount), 2) AS gmv
FROM dwd_order_detail
GROUP BY 1, 2;
