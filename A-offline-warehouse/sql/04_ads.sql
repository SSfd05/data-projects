-- ============================================================
-- 04 ADS 层：面向业务的指标宽表
-- 原则：每个指标只在这里定义一次，避免「同一个复购率三个部门三个数」。
-- ============================================================

-- ---------- 月度经营指标（全部销售，含匿名订单） ----------
CREATE OR REPLACE TABLE ads_kpi_monthly AS
SELECT
    DATE_TRUNC('month', invoice_time) AS stat_month,
    COUNT(DISTINCT invoice_no)        AS orders,
    COUNT(DISTINCT customer_id)       AS customers,   -- 会员数，匿名不计
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
-- 注意两个分母不一样，报告里必须说清楚：
--   GMV / 订单数 = 全部销售（含匿名）
--   复购率 = 只在能识别出客户的会员里算
CREATE OR REPLACE TABLE ads_kpi_summary AS
WITH base AS (
    SELECT
        COUNT(DISTINCT customer_id) AS customers,
        COUNT(DISTINCT invoice_no)  AS orders,
        SUM(amount)                 AS gmv
    FROM dwd_order_detail
),
member AS (
    SELECT customer_id, COUNT(DISTINCT invoice_no) AS n
    FROM dwd_order_detail
    WHERE customer_id IS NOT NULL
    GROUP BY 1
),
returns AS (
    -- 口径与主表一致：只要有成交的销售单（不要求客户 ID），
    -- 但剔除伪商品编号，否则邮费退款会被算进退货率。
    SELECT ABS(SUM(quantity * unit_price)) AS return_amount
    FROM ods_retail
    WHERE invoice_no LIKE 'C%'
      AND quantity < 0
      AND unit_price > 0
      AND stock_code NOT IN ('POST', 'DOT', 'M', 'C2', 'BANK CHARGES', 'PADS', 'D', 'S')
)
SELECT
    b.customers,
    b.orders,
    b.gmv,
    ROUND(b.gmv / b.orders, 2)                                       AS aov,
    ROUND((SELECT COUNT(*) FROM member WHERE n >= 2)::DOUBLE
          / (SELECT COUNT(*) FROM member), 4)                        AS repeat_rate,
    ROUND(r.return_amount / b.gmv, 4)                                AS return_amount_ratio
FROM base b, returns r;
