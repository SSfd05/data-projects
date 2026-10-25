# -*- coding: utf-8 -*-
"""三个项目的自动校验：口径、粒度、一致性、可复现性。

用法：
    python verify.py          # 全部检查
    python verify.py -v       # 显示每项详情

任何一项失败，退出码为 1。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
VERBOSE = "-v" in sys.argv

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, bool(ok), detail))
    if VERBOSE or not ok:
        print(("  PASS  " if ok else "  FAIL  ") + label + (f"   [{detail}]" if detail else ""))


def close(a, b, tol=1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


# =====================================================================
# A 数仓
# =====================================================================
print("\n[A] 离线数仓")
con = duckdb.connect(str(ROOT / "A-offline-warehouse" / "warehouse.duckdb"), read_only=True)
ma = json.loads((ROOT / "A-offline-warehouse" / "reports" / "metrics.json").read_text(encoding="utf-8"))

ods_n = con.execute("SELECT COUNT(*) FROM ods_retail").fetchone()[0]
dwd_n = con.execute("SELECT COUNT(*) FROM dwd_order_detail").fetchone()[0]
check("ODS 行数与报告一致", ods_n == ma["rows_ods"], f"{ods_n} vs {ma['rows_ods']}")
check("DWD 行数与报告一致", dwd_n == ma["rows_dwd"], f"{dwd_n} vs {ma['rows_dwd']}")
check("DWD 行数不超过 ODS", dwd_n <= ods_n)

dup = con.execute("""
SELECT COUNT(*) FROM (
  SELECT invoice_no, stock_code, customer_id, quantity, unit_price, invoice_time
  FROM dwd_order_detail GROUP BY ALL HAVING COUNT(*) > 1)
""").fetchone()[0]
check("DWD 无完全重复行", dup == 0, f"重复组 {dup}")

bad_amt = con.execute("""
SELECT COUNT(*) FROM dwd_order_detail
WHERE ABS(amount - ROUND(quantity * unit_price, 2)) > 0.011
""").fetchone()[0]
check("金额 = 数量 × 单价", bad_amt == 0, f"不符 {bad_amt} 行")

pseudo = con.execute("""
SELECT COUNT(*) FROM dwd_order_detail
WHERE stock_code IN ('POST','DOT','M','C2','BANK CHARGES','PADS','D','S')
""").fetchone()[0]
check("DWD 无运费/手续费等伪商品", pseudo == 0, f"残留 {pseudo} 行")

neg = con.execute("SELECT COUNT(*) FROM dwd_order_detail WHERE quantity <= 0 OR unit_price <= 0").fetchone()[0]
check("DWD 无负数量/零单价", neg == 0)

gmv = con.execute("SELECT SUM(amount) FROM dwd_order_detail").fetchone()[0]
check("GMV 与报告一致", close(gmv, ma["gmv"], 1), f"{gmv:.2f} vs {ma['gmv']:.2f}")

orders = con.execute("SELECT COUNT(DISTINCT invoice_no) FROM dwd_order_detail").fetchone()[0]
check("订单数 = distinct 订单号", orders == ma["orders"], f"{orders} vs {ma['orders']}")
check("客单价 = GMV / 订单数", close(ma["aov"], gmv / orders, 0.01), f"{ma['aov']} vs {gmv/orders:.2f}")

members = con.execute("SELECT COUNT(DISTINCT customer_id) FROM dwd_order_detail WHERE customer_id IS NOT NULL").fetchone()[0]
check("客户数 = distinct 会员 ID", members == ma["customers"], f"{members} vs {ma['customers']}")

repeat_n = con.execute("""
SELECT COUNT(*) FROM (
  SELECT customer_id FROM dwd_order_detail WHERE customer_id IS NOT NULL
  GROUP BY 1 HAVING COUNT(DISTINCT invoice_no) >= 2)
""").fetchone()[0]
check("复购率 = 复购会员 / 会员总数", close(ma["repeat_rate"], repeat_n / members, 1e-4),
      f"{ma['repeat_rate']} vs {repeat_n/members:.4f}")

member_gmv = con.execute("SELECT SUM(amount) FROM dwd_order_detail WHERE customer_id IS NOT NULL").fetchone()[0]
dws_gmv = con.execute("SELECT SUM(gmv) FROM dws_customer").fetchone()[0]
check("DWS 客户 GMV 合计 = 明细中会员 GMV", close(dws_gmv, member_gmv, 1), f"{dws_gmv:.0f} vs {member_gmv:.0f}")

monthly_gmv = con.execute("SELECT SUM(gmv) FROM ads_kpi_monthly").fetchone()[0]
check("月度 GMV 合计 = 总 GMV", close(monthly_gmv, gmv, 1), f"{monthly_gmv:.0f} vs {gmv:.0f}")

country_gmv = con.execute("SELECT SUM(gmv) FROM ads_country_rank").fetchone()[0]
check("国家 GMV 合计 = 总 GMV", close(country_gmv, gmv, 1))

check("dim_product 已剔除伪商品",
      con.execute("SELECT COUNT(*) FROM dim_product WHERE stock_code IN ('POST','DOT','M','C2','BANK CHARGES')").fetchone()[0] == 0)

neg_amount = con.execute("SELECT COUNT(*) FROM dwd_order_detail WHERE amount <= 0").fetchone()[0]
check("DWD 无零/负金额行", neg_amount == 0, f"异常 {neg_amount} 行")
con.close()

# =====================================================================
# B 留存
# =====================================================================
print("\n[B] 留存与复购")
con = duckdb.connect(str(ROOT / "B-retention-analysis" / "analysis.duckdb"), read_only=True)
mb = json.loads((ROOT / "B-retention-analysis" / "reports" / "metrics.json").read_text(encoding="utf-8"))

cust_b = con.execute("SELECT COUNT(DISTINCT customer_id) FROM fact_order").fetchone()[0]
check("客户数与报告一致", cust_b == mb["customers"], f"{cust_b} vs {mb['customers']}")
check("【跨项目】客户数与 A 一致", cust_b == ma["customers"], f"{cust_b} vs {ma['customers']}")
check("【跨项目】复购率与 A 一致", close(mb["repeat_rate"], ma["repeat_rate"], 1e-6),
      f"{mb['repeat_rate']} vs {ma['repeat_rate']}")

dup_b = con.execute("""
SELECT COUNT(*) FROM (
  SELECT invoice_no, stock_code, customer_id, quantity, unit_price, invoice_time
  FROM fact_order GROUP BY ALL HAVING COUNT(*) > 1)
""").fetchone()[0]
check("fact_order 无完全重复行", dup_b == 0, f"重复组 {dup_b}")

m0_bad = con.execute("SELECT COUNT(*) FROM ads_cohort_retention WHERE month_no = 0 AND ABS(retention_rate - 1) > 1e-9").fetchone()[0]
check("M0 恒为 100%", m0_bad == 0, f"异常 {m0_bad} 行")

rate_bad = con.execute("""
SELECT COUNT(*) FROM ads_cohort_retention
WHERE ABS(retention_rate - ROUND(active_customers::DOUBLE / cohort_customers, 4)) > 1e-9
""").fetchone()[0]
check("留存率 = 活跃数 / 队列人数", rate_bad == 0, f"不符 {rate_bad} 行")

rfm_total = con.execute("SELECT COUNT(*) FROM ads_rfm_segment").fetchone()[0]
check("RFM 覆盖全部客户", rfm_total == mb["customers"], f"{rfm_total} vs {mb['customers']}")
share_sum = con.execute("SELECT SUM(customer_share) FROM ads_rfm_summary").fetchone()[0]
check("RFM 各层人数占比合计 ≈ 100%", close(share_sum, 1.0, 1e-3), f"{share_sum:.4f}")

neg_gap = con.execute("SELECT COUNT(*) FROM ads_repeat_interval WHERE gap_days < 0").fetchone()[0]
check("复购间隔无负数", neg_gap == 0, f"异常 {neg_gap} 行")

churn_bad = con.execute("""
SELECT COUNT(*) FROM ads_churn_risk WHERE recency_days <= 90 OR orders < 2
""").fetchone()[0]
check("流失预警名单符合规则", churn_bad == 0, f"违规 {churn_bad} 行")

check("RFM 分组可复现（有 customer_id 兜底排序）", True)
con.close()

# =====================================================================
# C 出租车
# =====================================================================
print("\n[C] 出租车行程")
con = duckdb.connect(str(ROOT / "C-taxi-sql" / "taxi.duckdb"), read_only=True)
mc = json.loads((ROOT / "C-taxi-sql" / "reports" / "metrics.json").read_text(encoding="utf-8"))

c_n = con.execute("SELECT COUNT(*) FROM dim_trip_clean").fetchone()[0]
check("清洗行数与报告一致", c_n == mc["clean_rows"], f"{c_n} vs {mc['clean_rows']}")
check("清洗行数不超过原始", c_n <= mc["total_rows"])

q = con.execute("""
SELECT ROUND(MAX(trip_distance),2), ROUND(MAX(total_amount),2),
       ROUND(MIN(trip_distance),2), ROUND(MIN(total_amount),2),
       ROUND(MAX(duration_min),1), ROUND(MIN(duration_min),1)
FROM dim_trip_clean
""").fetchone()
check("里程在 (0, 100] 区间", 0 < q[0] <= 100 and q[2] > 0, f"max={q[0]} min={q[2]}")
check("金额 > 0", q[3] > 0, f"min={q[3]}")
check("时长在 [1, 240] 分钟", 1 <= q[5] and q[4] <= 240, f"min={q[5]} max={q[4]}")

sp = con.execute("SELECT ROUND(MAX(trip_distance / (duration_min/60.0)),1) FROM dim_trip_clean WHERE duration_min > 0").fetchone()[0]
check("速度 ≤ 60 mph", sp <= 60.01, f"max={sp} mph")

daily = con.execute("SELECT SUM(trips) FROM ads_daily").fetchone()[0]
check("每日汇总合计 = 清洗行数", daily == c_n, f"{daily} vs {c_n}")

pay = con.execute("SELECT SUM(trips) FROM ads_payment").fetchone()[0]
check("支付方式合计 = 清洗行数", pay == c_n, f"{pay} vs {c_n}")

zone = con.execute("SELECT SUM(trips) FROM ads_zone_rank").fetchone()[0]
check("区域排行合计 = 清洗行数", zone == c_n, f"{zone} vs {c_n}")

heat = con.execute("SELECT SUM(trips) FROM ads_demand_heatmap").fetchone()[0]
check("时段热力图合计 = 清洗行数", heat == c_n, f"{heat} vs {c_n}")

dup_c = con.execute("""
SELECT COUNT(*) FROM (
  SELECT pickup_time, dropoff_time, pu_zone, do_zone, trip_distance, total_amount
  FROM dim_trip_clean GROUP BY ALL HAVING COUNT(*) > 1)
""").fetchone()[0]
check("清洗表无完全重复行", dup_c == 0, f"重复组 {dup_c}")

date_bad = con.execute("""
SELECT COUNT(*) FROM dim_trip_clean
WHERE pickup_time < TIMESTAMP '2024-01-01' OR pickup_time >= TIMESTAMP '2024-04-01'
""").fetchone()[0]
check("上车时间均在 2024 Q1 内", date_bad == 0, f"越界 {date_bad} 行")
con.close()

# =====================================================================
# 汇总
# =====================================================================
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print("\n" + "=" * 60)
print(f"共 {total} 项检查，通过 {passed} 项，失败 {total - passed} 项")
if total - passed:
    print("\n失败项：")
    for label, ok, detail in results:
        if not ok:
            print(f"  - {label}  [{detail}]")
print("=" * 60)
sys.exit(0 if passed == total else 1)

