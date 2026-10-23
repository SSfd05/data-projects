-- ============================================================
-- 02 分析主表 + 各主题汇总
-- ============================================================

-- 清洗后的行程表：把质量体检里发现的问题都挡掉
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
  AND tpep_dropoff_datetime > tpep_pickup_datetime
  AND total_amount > 0
  AND tpep_pickup_datetime >= TIMESTAMP '2024-01-01'
  AND tpep_pickup_datetime <  TIMESTAMP '2024-04-01'
  AND DATE_DIFF('second', tpep_pickup_datetime, tpep_dropoff_datetime) BETWEEN 60 AND 4 * 3600;

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
