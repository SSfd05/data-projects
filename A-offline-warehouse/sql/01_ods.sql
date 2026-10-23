-- ============================================================
-- 01 ODS 层：原始数据原样落地
-- 原则：这一层不做任何清洗、不去重、不转换类型。
--      原始数据是唯一事实来源，出了问题能一路回溯到这里。
-- ============================================================

CREATE OR REPLACE TABLE ods_retail AS
SELECT
    "InvoiceNo"   AS invoice_no,      -- 订单号，以 C 开头的是退货单
    "StockCode"   AS stock_code,      -- 商品编号
    "Description" AS description_raw, -- 商品名称（可能有缺失）
    "Quantity"    AS quantity,        -- 数量，退货为负数
    "InvoiceDate" AS invoice_time,    -- 下单时间
    "UnitPrice"   AS unit_price,      -- 单价
    "CustomerID"  AS customer_id_raw, -- 客户 ID，匿名订单为空
    "Country"     AS country,
    source_period                     -- 数据来自哪个年度工作表
FROM src_retail;
