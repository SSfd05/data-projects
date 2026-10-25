-- ============================================================
-- 02 分析主表 + 各主题汇总
-- ============================================================

-- 清洗后的行程表：把质量体检里发现的问题全部挡掉
--
-- 六条规则，每条都能说出理由：
--   1. 里程 > 0                计价器故障/取消单
--   2. 下车时间 > 上车时间      时间倒挂
--   3. 金额 > 0                退款单
--   4. 上车时间落在本季度内      越界数据
--   5. 时长 1 分钟 ~ 4 小时     太短是误触，太长是忘关表
--   6. 里程 ≤ 100 英里
--      且平均速度 ≤ 60 mph     物理上不可能：原数据最大里程 312,722 英里，
--                              有 421 行速度超过 60 mph，不剔除会污染均值
CREATE OR REPLACE TABLE dim_trip_clean AS
SELECT
    tpep_pickup_datetime  AS pickup_time,
    tpep_dropoff_datetime AS dropoff_time,
    DATE_DIFF('second', tpep_pickup_datetime, tpep_dropoff_datetime) / 60.0 AS duration_min,
    trip_distance,
    PULocationID AS pu_zone,
    DOLocationID AS do_zone,
    passenger_count,
    payment_type,
    fare_amount,
    tip_amount,
    total_amount,
    EXTRACT(hour      FROM tpep_pickup_datetime) AS pickup_hour,
    EXTRACT(dow       FROM tpep_pickup_datetime) AS pickup_dow,
    CAST(tpep_pickup_datetime AS DATE)           AS pickup_date
FROM fact_trip
WHERE trip_distance > 0
  AND trip_distance <= 100
  AND tpep_dropoff_datetime > tpep_pickup_datetime
  AND total_amount > 0
  AND tpep_pickup_datetime >= TIMESTAMP '2024-01-01'
  AND tpep_pickup_datetime <  TIMESTAMP '2024-04-01'
  AND DATE_DIFF('second', tpep_pickup_datetime, tpep_dropoff_datetime) BETWEEN 60 AND 4 * 3600
  AND trip_distance / (DATE_DIFF('second', tpep_pickup_datetime, tpep_dropoff_datetime) / 3600.0) <= 60;

-- 主题一：时段 × 星期 的需求分布
CREATE OR REPLACE TABLE ads_demand_heatmap AS
SELECT
    pickup_dow,
    pickup_hour,
    COUNT(*)        AS trips,
    ROUND(AVG(total_amount), 2) AS avg_amount
FROM dim_trip_clean
GROUP BY 1, 2
ORDER BY 1, 2;

-- 主题二：支付方式
CREATE OR REPLACE TABLE ads_payment AS
SELECT
    payment_type,
    COUNT(*)                          AS trips,
    ROUND(COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER (), 4) AS share,
    ROUND(AVG(tip_amount), 2)         AS avg_tip,
    ROUND(AVG(tip_amount) / NULLIF(AVG(fare_amount), 0), 4) AS tip_rate
FROM dim_trip_clean
GROUP BY 1
ORDER BY trips DESC;

-- 主题三：上车区域 Top20
CREATE OR REPLACE TABLE ads_zone_rank AS
SELECT
    pu_zone,
    COUNT(*)                    AS trips,
    ROUND(AVG(trip_distance), 2) AS avg_distance,
    ROUND(AVG(total_amount), 2)  AS avg_amount,
    ROUND(AVG(duration_min), 1)  AS avg_duration
FROM dim_trip_clean
GROUP BY 1
ORDER BY trips DESC;

-- 主题四：日均节奏
CREATE OR REPLACE TABLE ads_daily AS
SELECT
    pickup_date,
    COUNT(*)                    AS trips,
    ROUND(SUM(total_amount), 2) AS revenue
FROM dim_trip_clean
GROUP BY 1
ORDER BY 1;
