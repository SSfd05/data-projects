-- ============================================================
-- 02 DWD 层：清洗 + 维度建模
-- 原则：所有脏数据的判断都收敛到这一层，下游不用再写 where 过滤。
-- ============================================================

-- ---------- 维度表：日期 ----------
CREATE OR REPLACE TABLE dim_date AS
SELECT DISTINCT
    CAST(invoice_time AS DATE)          AS date_key,
    EXTRACT(YEAR  FROM invoice_time)    AS year,
    EXTRACT(MONTH FROM invoice_time)    AS month,
    EXTRACT(DOW   FROM invoice_time)    AS weekday
FROM ods_retail;

-- ---------- 维度表：客户 ----------
CREATE OR REPLACE TABLE dim_customer AS
SELECT
    CAST(customer_id_raw AS VARCHAR) AS customer_id,
    MIN(country)                     AS country
FROM ods_retail
WHERE customer_id_raw IS NOT NULL
GROUP BY 1;

-- ---------- 维度表：商品 ----------
CREATE OR REPLACE TABLE dim_product AS
SELECT
    stock_code,
    ANY_VALUE(description_raw) AS product_name
FROM ods_retail
WHERE stock_code IS NOT NULL
  AND stock_code NOT IN ('POST', 'DOT', 'M', 'C2', 'BANK CHARGES', 'PADS', 'D', 'S')
GROUP BY 1;

-- ---------- 事实表：订单明细 ----------
-- 清洗规则（每条都要能说清理由）：
--   1. quantity > 0        ：剔除退货单和录入错误
--   2. unit_price > 0      ：剔除赠品、内部调拨、价格缺失
--   3. customer_id 非空    ：匿名订单无法归属到客户，做不了留存/复购
--   4. invoice_no 非空     ：订单号是事实表的粒度键
CREATE OR REPLACE TABLE dwd_order_detail AS
SELECT
    invoice_no,
    stock_code,
    CAST(customer_id_raw AS VARCHAR) AS customer_id,
    quantity,
    unit_price,
    ROUND(quantity * unit_price, 2)  AS amount,
    invoice_time,
    CAST(invoice_time AS DATE)       AS date_key,
    country,
    source_period,
    CASE WHEN invoice_no LIKE 'C%' THEN 1 ELSE 0 END AS is_return
FROM ods_retail
WHERE quantity    > 0
  AND unit_price  > 0
  AND customer_id_raw IS NOT NULL
  AND invoice_no  IS NOT NULL
  AND stock_code  IS NOT NULL
  -- 5. 剔除「不是商品」的编号：邮费、运费、手工调整、银行手续费
  --    它们有金额但没实物，混进商品维度会让 GMV 虚高约 1.7%，
  --    也会让「单品销售额排名」出现 POST（邮费）这种荒唐结果
  AND stock_code NOT IN ('POST', 'DOT', 'M', 'C2', 'BANK CHARGES', 'PADS', 'D', 'S');
