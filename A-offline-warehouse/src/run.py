# -*- coding: utf-8 -*-
"""离线数仓：把 UCI 电商交易数据加工成 ODS → DWD → DWS → ADS 四层。

运行：python src/run.py
产物：reports/metrics.json、reports/findings.md、reports/figs/*.png、warehouse.duckdb
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGS = REPORTS / "figs"
DB = ROOT / "warehouse.duckdb"


def step(msg: str) -> None:
    print(f"  - {msg}")


def stage_raw_to_parquet() -> Path:
    """阶段 0：把两个 Excel 工作表合并成一个 parquet 文件（只做格式转换，不改数据）。"""
    raw_dir = DATA / "raw"
    xs = sorted(raw_dir.rglob("*.xlsx")) if raw_dir.exists() else []
    if not xs:
        raise SystemExit(f"数据文件不存在：请把 *.xlsx 放到 {raw_dir}/ 下")
    xlsx = xs[0]
    out = DATA / "retail.parquet"
    if out.exists():
        step(f"跳过转换，已存在 {out.name}")
        return out

    # Online Retail II 是双工作表（两个年度），Online Retail 只有一张表
    if "retail_ii" in xlsx.name.lower():
        sheets = ["Year 2009-2010", "Year 2010-2011"]
    else:
        sheets = [0]

    frames = []
    for sheet in sheets:
        step(f"读取工作表 {sheet}")
        df = pd.read_excel(xlsx, sheet_name=sheet)
        df["source_period"] = str(sheet)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    # InvoiceNo 里既有数字也有 "C" 开头的退货单，必须统一成字符串
    for _c in ("InvoiceNo", "StockCode", "Description", "CustomerID", "Country"):
        if _c in df.columns:
            df[_c] = df[_c].astype("string")
    for _c in ("Quantity", "UnitPrice"):
        if _c in df.columns:
            df[_c] = pd.to_numeric(df[_c], errors="coerce")
    df.to_parquet(out, index=False)
    step(f"合并 {len(df):,} 行 -> {out.name}")
    return out


def run_sql(con: duckdb.DuckDBPyConnection, name: str) -> None:
    path = SQL_DIR / name
    con.execute(path.read_text(encoding="utf-8"))
    step(f"执行 {name}")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    parquet = stage_raw_to_parquet()

    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(f"CREATE OR REPLACE VIEW src_retail AS SELECT * FROM read_parquet('{parquet.as_posix()}')")

    print("[1/4] ODS 层：原样落地")
    run_sql(con, "01_ods.sql")

    print("[2/4] DWD 层：清洗 + 维度建模")
    run_sql(con, "02_dwd.sql")

    print("[3/4] DWS 层：按主题汇总")
    run_sql(con, "03_dws.sql")

    print("[4/4] ADS 层：面向业务的指标宽表")
    run_sql(con, "04_ads.sql")

    # ---------- 取指标 ----------
    def one(sql: str):
        return con.execute(sql).fetchone()

    rows_ods = one("select count(*) from ods_retail")[0]
    rows_dwd = one("select count(*) from dwd_order_detail")[0]
    kpi = con.execute("select * from ads_kpi_monthly order by stat_month").df()
    summary = con.execute("select * from ads_kpi_summary").df().iloc[0].to_dict()
    top_country = con.execute(
        "select country, gmv from ads_country_rank order by gmv desc limit 1"
    ).df().iloc[0].to_dict()

    metrics = {
        "rows_ods": int(rows_ods),
        "rows_dwd": int(rows_dwd),
        "clean_ratio": round(rows_dwd / rows_ods, 4),
        "customers": int(summary["customers"]),
        "orders": int(summary["orders"]),
        "gmv": round(float(summary["gmv"]), 2),
        "aov": round(float(summary["aov"]), 2),
        "repeat_rate": round(float(summary["repeat_rate"]), 4),
        "return_amount_ratio": round(float(summary["return_amount_ratio"]), 4),
        "months": int(len(kpi)),
        "top_country": {"country": str(top_country["country"]), "gmv": round(float(top_country["gmv"]), 2)},
        "monthly": kpi.assign(stat_month=kpi["stat_month"].astype(str)).to_dict(orient="records"),
    }
    (REPORTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    make_figures(con, kpi)
    write_findings(metrics)
    print("完成：", REPORTS / "metrics.json")
    return 0


def make_figures(con, kpi: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.25

    # 图 1：月度 GMV 与订单数
    fig, ax1 = plt.subplots(figsize=(9, 3.8))
    x = kpi["stat_month"].astype(str)
    ax1.bar(x, kpi["gmv"], color="#2f6f9f", width=0.6, label="GMV")
    ax1.set_ylabel("GMV")
    ax1.tick_params(axis="x", rotation=60, labelsize=8)
    ax2 = ax1.twinx()
    ax2.plot(x, kpi["orders"], "o-", color="#c0504d", lw=1.6, ms=3, label="订单数")
    ax2.set_ylabel("订单数")
    ax2.grid(False)
    ax1.set_title("月度 GMV 与订单数（ADS 层 ads_kpi_monthly）", fontsize=11)
    fig.savefig(FIGS / "fig01_monthly.png", bbox_inches="tight")
    plt.close(fig)

    # 图 2：国家贡献 Top10
    df = con.execute(
        "select country, gmv from ads_country_rank order by gmv desc limit 10"
    ).df()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.barh(df["country"][::-1], df["gmv"][::-1], color="#1f3a5f")
    ax.set_title("GMV 国家 Top10", fontsize=11)
    ax.set_xlabel("GMV")
    fig.savefig(FIGS / "fig02_country.png", bbox_inches="tight")
    plt.close(fig)

    # 图 3：客单价分布
    df = con.execute("select aov from dws_customer where orders >= 1").df()
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    ax.hist(df["aov"].clip(upper=5000), bins=60, color="#2f6f9f")
    ax.set_title("客户客单价分布（截断到 5000）", fontsize=11)
    ax.set_xlabel("客单价")
    ax.set_ylabel("客户数")
    fig.savefig(FIGS / "fig03_aov.png", bbox_inches="tight")
    plt.close(fig)


def write_findings(m: dict) -> None:
    lines = [
        "# 离线数仓：英国电商交易数据的分层建模",
        "",
        "> 由 `src/run.py` 自动生成，数字来自当次运行。",
        "",
        "## 1. 分层结果",
        "",
        "| 层 | 表 | 行数 |",
        "| --- | --- | --- |",
        f"| ODS | `ods_retail`（原始落地） | {m['rows_ods']:,} |",
        f"| DWD | `dwd_order_detail`（清洗后明细） | {m['rows_dwd']:,} |",
        "| DWS | `dws_customer` / `dws_product_daily` | 按客户 / 按商品汇总 |",
        "| ADS | `ads_kpi_monthly` / `ads_kpi_summary` / `ads_country_rank` | 业务指标宽表 |",
        "",
        f"清洗保留了 {m['clean_ratio']:.1%} 的记录，丢弃的是退货单、负数量、零单价和没有客户 ID 的行。",
        "",
        "## 2. 核心指标",
        "",
        f"- GMV：**{m['gmv']:,.0f}**",
        f"- 订单数：**{m['orders']:,}**，客户数：**{m['customers']:,}**",
        f"- 客单价：**{m['aov']:,.2f}**",
        f"- 复购率：**{m['repeat_rate']:.1%}**（下单 ≥2 次的客户占比）",
        f"- 退货金额占比：**{m['return_amount_ratio']:.1%}**",
        f"- 覆盖月份：**{m['months']}** 个月；GMV 最高的国家是 **{m['top_country']['country']}**",
        "",
        "## 3. 为什么这么分层",
        "",
        "- **ODS 不做任何清洗**：原始数据永远是唯一事实来源，出问题可以回溯。",
        "- **DWD 做清洗和维度建模**：把退货单、负数量这些脏数据挡在这里，下游全部不用再判断。",
        "- **DWS 按主题预聚合**：客户维度和商品维度各自汇总，避免 ADS 层重复算。",
        "- **ADS 只放业务口径**：每个指标只在一处定义，避免“同一个复购率三个部门三个数”。",
        "",
        "## 4. 口径说明",
        "",
        "- 复购率 = 下单次数 ≥ 2 的客户数 / 有客户 ID 的客户数；",
        "- 退货金额占比 = 退货单金额绝对值 / 正常销售金额；",
        "- 客单价 = GMV / 订单数（订单按 InvoiceNo 去重）。",
        "",
    ]
    (REPORTS / "findings.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
