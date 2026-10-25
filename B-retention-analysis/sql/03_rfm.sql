-- ============================================================
-- 03 RFM 分层
-- R = 最近一次购买距今多少天，F = 下单次数，M = 累计金额
-- 每个维度用 NTILE(5) 切成 5 档，再组合成客户分层
-- ============================================================

CREATE OR REPLACE TABLE tmp_customer_rfm AS
WITH base AS (
    SELECT
        customer_id,
        MAX(invoice_time)             AS last_order_time,
        COUNT(DISTINCT invoice_no)    AS frequency,
        ROUND(SUM(amount), 2)         AS monetary
    FROM fact_order
    GROUP BY 1
),
anchor AS (
    SELECT MAX(invoice_time) AS snapshot_time FROM fact_order
)
SELECT
    customer_id,
    DATE_DIFF('day', last_order_time, (SELECT snapshot_time FROM anchor)) AS recency_days,
    frequency,
    monetary,
    -- R 越小越好，所以按降序切档：最近买的得 5 分
    -- 末尾的 customer_id 是兜底排序键：NTILE 遇到并列值时，结果会随行顺序变化，
    -- 加上它才能保证每次跑出来的分组完全一致。
    NTILE(5) OVER (ORDER BY DATE_DIFF('day', last_order_time, (SELECT snapshot_time FROM anchor)) DESC, customer_id) AS r_score,
    NTILE(5) OVER (ORDER BY frequency, customer_id)  AS f_score,
    NTILE(5) OVER (ORDER BY monetary,  customer_id)  AS m_score
FROM base;

CREATE OR REPLACE TABLE ads_rfm_segment AS
SELECT
    *,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 THEN '重要价值'
        WHEN r_score >= 4 AND f_score <= 2 THEN '新客户'
        WHEN r_score <= 2 AND f_score >= 4 THEN '重要挽留'
        WHEN r_score <= 2 AND f_score <= 2 THEN '已流失'
        WHEN r_score <= 2                 THEN '沉睡'
        ELSE '一般保持'
    END AS segment
FROM tmp_customer_rfm;

-- 各层的人数与金额贡献 —— 这张表直接就是汇报 PPT 的第一页
CREATE OR REPLACE TABLE ads_rfm_summary AS
SELECT
    segment,
    COUNT(*)                                   AS customers,
    ROUND(COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER (), 4) AS customer_share,
    ROUND(SUM(monetary), 2)                    AS gmv,
    ROUND(SUM(monetary) / SUM(SUM(monetary)) OVER (), 4) AS gmv_share,
    ROUND(AVG(monetary), 2)                    AS avg_gmv,
    ROUND(AVG(recency_days), 0)                AS avg_recency_days,
    ROUND(AVG(frequency), 1)                   AS avg_frequency
FROM ads_rfm_segment
GROUP BY 1
ORDER BY gmv DESC;
