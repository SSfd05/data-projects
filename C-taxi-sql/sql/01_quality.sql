-- ============================================================
-- 01 数据质量体检
-- 真实数据的第一件事永远是：先搞清楚有多少脏数据，脏在哪
-- ============================================================

CREATE OR REPLACE VIEW fact_trip AS
SELECT * FROM read_parquet('data/yellow_tripdata_*.parquet');

CREATE OR REPLACE TABLE quality_check AS
SELECT
    COUNT(*)                                                      AS total_rows,
    SUM(CASE WHEN trip_distance <= 0 THEN 1 ELSE 0 END)           AS bad_distance,
    SUM(CASE WHEN tpep_dropoff_datetime <= tpep_pickup_datetime THEN 1 ELSE 0 END) AS bad_duration,
    SUM(CASE WHEN total_amount <= 0 THEN 1 ELSE 0 END)            AS bad_amount,
    SUM(CASE WHEN passenger_count = 0 THEN 1 ELSE 0 END)          AS zero_passenger,
    SUM(CASE WHEN PULocationID IS NULL OR DOLocationID IS NULL THEN 1 ELSE 0 END) AS missing_zone,
    SUM(CASE WHEN tpep_pickup_datetime < TIMESTAMP '2024-01-01'
               OR tpep_pickup_datetime >= TIMESTAMP '2024-04-01' THEN 1 ELSE 0 END) AS out_of_range
FROM fact_trip;
