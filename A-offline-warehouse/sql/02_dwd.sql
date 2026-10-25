-- ============================================================
-- 02 DWD 层：清洗 + 维度建模
--
-- 清洗规则（每条都要能说出理由）：
--   1. quantity   > 0   剔除退货单（退货在原始数据里是负数）
--   2. unit_price > 0   剔除赠品、内部调拨、价格缺失
--   3. invoice_no / stock_code 非空（事实表的粒度键）
--   4. 剔除伪商品编号：邮费、运费、手工调整、银行手续费
--   5. 去重：原始数据里有 5,270 行完全重复（占 1.0%）
--
-- 这里刻意【不剔除】匿名订单（customer_id 为空）。
-- 它们占 24.9%，是真实发生的销售；剔掉之后算出来的就不是 GMV，
-- 而是「会员销售额」。客户类指标到 DWS / ADS 层再按 customer_id 过滤。
-- ============================================================

CREATE OR REPLACE TABLE dim_date AS
SELECT DISTINCT
    CAST(invoice_time AS DATE)       AS date_key,
    EXTRACT(YEAR  FROM invoice_time) AS year,
    EXTRACT(MONTH FROM invoice_time) AS month,
    EXTRACT(DOW   FROM invoice_time) AS weekday
FROM ods_retail;

CREATE OR REPLACE TABLE dim_customer AS
SELECT
    CAST(customer_id_raw AS VARCHAR) AS customer_id,
    MIN(country)                     AS country
FROM ods_retail
WHERE customer_id_raw IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE TABLE dim_product AS
SELECT
    stock_code,
    ANY_VALUE(description_raw) AS product_name
FROM ods_retail
WHERE stock_code IS NOT NULL
  AND stock_code NOT IN ('POST', 'DOT', 'M', 'C2', 'BANK CHARGES', 'PADS', 'D', 'S')
GROUP BY 1;

CREATE OR REPLACE TABLE dwd_order_detail AS
SELECT DISTINCT
    invoice_no,
    stock_code,
    CAST(customer_id_raw AS VARCHAR) AS customer_id,
    quantity,
    unit_price,
    ROUND(quantity * unit_price, 2)  AS amount,
    invoice_time,
    CAST(invoice_time AS DATE)       AS date_key,
    country,
    source_period
FROM ods_retail
WHERE quantity   > 0
  AND unit_price > 0
  AND invoice_no IS NOT NULL
  AND stock_code IS NOT NULL
  AND stock_code NOT IN ('POST', 'DOT', 'M', 'C2', 'BANK CHARGES', 'PADS', 'D', 'S');
