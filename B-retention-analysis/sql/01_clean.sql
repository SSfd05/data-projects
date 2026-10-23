-- ============================================================
-- 01 清洗：得到可以分析的事实表
-- 与数仓项目的口径一致：剔除退货、负数量、零单价、无客户 ID
-- ============================================================

CREATE OR REPLACE TABLE fact_order AS
SELECT
    "InvoiceNo"                       AS invoice_no,
    "StockCode"                       AS stock_code,
    "Quantity"                        AS quantity,
    "InvoiceDate"                     AS invoice_time,
    "UnitPrice"                       AS unit_price,
    ROUND("Quantity" * "UnitPrice", 2) AS amount,
    CAST("CustomerID" AS VARCHAR)     AS customer_id,
    "Country"                         AS country
FROM src_retail
WHERE "Quantity"    > 0
  AND "UnitPrice"   > 0
  AND "CustomerID"  IS NOT NULL
  AND "InvoiceNo"   IS NOT NULL;
