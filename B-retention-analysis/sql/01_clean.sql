-- ============================================================
-- 01 清洗：得到可以分析的事实表
--
-- 与数仓项目口径一致：
--   - 剔除退货（负数量）、零单价、伪商品编号
--   - 剔除完全重复行（原始数据有 5,270 行重复，会让 GMV 和 RFM 的 M 虚高）
--   - 只保留有客户 ID 的记录（留存分析必须有客户标识，这是本项目的硬要求）
-- ============================================================

CREATE OR REPLACE TABLE fact_order AS
SELECT DISTINCT
    "InvoiceNo"                        AS invoice_no,
    "StockCode"                        AS stock_code,
    "Quantity"                         AS quantity,
    "InvoiceDate"                      AS invoice_time,
    "UnitPrice"                        AS unit_price,
    ROUND("Quantity" * "UnitPrice", 2) AS amount,
    CAST("CustomerID" AS VARCHAR)      AS customer_id,
    "Country"                          AS country
FROM src_retail
WHERE "Quantity"    > 0
  AND "UnitPrice"   > 0
  AND "CustomerID"  IS NOT NULL
  AND "InvoiceNo"   IS NOT NULL
  AND "StockCode" NOT IN ('POST', 'DOT', 'M', 'C2', 'BANK CHARGES', 'PADS', 'D', 'S');
