# -*- coding: utf-8 -*-
"""留存与复购分析：cohort 留存矩阵、复购间隔、RFM 分层、流失预警。

运行：python src/run.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGS = REPORTS / "figs"
DB = ROOT / "analysis.duckdb"


def _log(m: str) -> None:
    print(f"  - {m}")


def resolve_parquet() -> Path:
    """优先用本项目的 parquet；没有就从 Excel 转；再没有就借用兄弟项目的缓存。"""
    own = DATA / "retail.parquet"
    if own.exists():
        _log(f"使用 {own.name}")
        return own

    xs = sorted((DATA / "raw").rglob("*.xlsx")) if (DATA / "raw").exists() else []
    xlsx = xs[0] if xs else None
    if xlsx is not None:
        sheets = ["Year 2009-2010", "Year 2010-2011"] if "retail_ii" in xlsx.name.lower() else [0]
        frames = []
        for sheet in sheets:
            _log(f"读取工作表 {sheet}")
            df = pd.read_excel(xlsx, sheet_name=sheet)
            df["source_period"] = str(sheet)
            frames.append(df)
        df = pd.concat(frames, ignore_index=True)
        df.columns = [c.strip() for c in df.columns]
        for _c in ("InvoiceNo", "StockCode", "Description", "CustomerID", "Country"):
            if _c in df.columns:
                df[_c] = df[_c].astype("string")
        for _c in ("Quantity", "UnitPrice"):
            if _c in df.columns:
                df[_c] = pd.to_numeric(df[_c], errors="coerce")
        df.to_parquet(own, index=False)
        _log(f"已转换 {len(df):,} 行 -> {own.name}")
        return own

    sibling = ROOT.parent / "A-offline-warehouse" / "data" / "retail.parquet"
    if sibling.exists():
        _log(f"未找到原始文件，借用 {sibling.relative_to(ROOT.parent)}")
        return sibling

    raise SystemExit(
        "找不到数据。请把 online_retail_II.xlsx 放到 data/raw/ 下，"
        "或先运行 ../A-offline-warehouse 生成 retail.parquet。"
    )


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    parquet = resolve_parquet()

    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(f"CREATE OR REPLACE VIEW src_retail AS SELECT * FROM read_parquet('{parquet.as_posix()}')")

    for f in ("01_clean.sql", "02_cohort.sql", "03_rfm.sql", "04_interval_churn.sql"):
        print(f"[SQL] {f}")
        con.execute((SQL_DIR / f).read_text(encoding="utf-8"))

    # -------- 指标 --------
    total_customers = con.execute("select count(*) from ads_customer_summary").fetchone()[0]
    repeat_customers = con.execute(
        "select count(*) from ads_customer_summary where orders >= 2"
    ).fetchone()[0]
    gaps = con.execute(
        "select gap_days from ads_repeat_interval where gap_days is not null"
    ).df()["gap_days"]
    rfm = con.execute("select * from ads_rfm_summary").df()
    retention = con.execute("select * from ads_cohort_retention order by 1, 2").df()
    churn = con.execute("select count(*), sum(gmv) from ads_churn_risk").fetchone()

    # 次月留存：所有 cohort 在第 1 个月的平均留存率
    m1 = retention[retention["month_no"] == 1]
    m1_rate = float(m1["active_customers"].sum() / m1["cohort_customers"].sum()) if len(m1) else 0.0

    metrics = {
        "customers": int(total_customers),
        "repeat_customers": int(repeat_customers),
        "repeat_rate": round(repeat_customers / total_customers, 4),
        "median_gap_days": float(gaps.median()) if len(gaps) else None,
        "avg_gap_days": round(float(gaps.mean()), 1) if len(gaps) else None,
        "cohorts": int(retention["first_month"].nunique()),
        "m1_retention": round(m1_rate, 4),
        "churn_customers": int(churn[0]),
        "churn_gmv": round(float(churn[1] or 0), 2),
        "rfm": rfm.to_dict(orient="records"),
    }
    metrics["rfm"] = [
        {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in row.items()}
        for row in metrics["rfm"]
    ]
    (REPORTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    retention.to_csv(REPORTS / "cohort_retention.csv", index=False, encoding="utf-8-sig")
    rfm.to_csv(REPORTS / "rfm_summary.csv", index=False, encoding="utf-8-sig")

    make_figures(retention, gaps, rfm)
    write_findings(metrics, retention)
    print("完成：", REPORTS / "metrics.json")
    return 0


def make_figures(retention: pd.DataFrame, gaps: pd.Series, rfm: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130

    # 图 1：留存热力图
    pivot = retention.pivot_table(
        index="first_month", columns="month_no", values="retention_rate", aggfunc="first"
    ).sort_index()
    sizes = retention.groupby("first_month")["cohort_customers"].max()
    # 样本太少的 cohort 噪声极大（首尾两个月最典型），剔除
    pivot = pivot.loc[[i for i in pivot.index if sizes.get(i, 0) >= 100]]
    pivot = pivot.iloc[:, :13]
    # M0 恒为 100%，会污染色阶，计算分位数时排除掉
    _vals = pivot.drop(columns=[c for c in pivot.columns if c == 0], errors="ignore").values
    vmax = max(float(np.nanpercentile(_vals, 95)), 0.4)
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    im = ax.imshow(pivot.values, cmap="Blues", aspect="auto", vmin=0, vmax=vmax)
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels([f"M{c}" for c in pivot.columns], fontsize=8)
    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels([f"{str(i)[:7]} (n={int(sizes.get(i, 0))})" for i in pivot.index], fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                        fontsize=7, color="white" if v > vmax * 0.6 else "#333")
    ax.set_title("同期群留存矩阵（行=首购月，列=第 N 月，值=留存率 %）", fontsize=10.5)
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    fig.savefig(FIGS / "fig01_cohort_heatmap.png", bbox_inches="tight")
    plt.close(fig)

    # 图 2：复购间隔分布
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.hist(gaps.clip(upper=365), bins=60, color="#2f6f9f")
    ax.axvline(gaps.median(), color="#c0504d", ls="--", lw=1.4,
               label=f"中位数 {gaps.median():.0f} 天")
    ax.set_title("相邻两次下单的间隔分布（截断到 365 天）", fontsize=11)
    ax.set_xlabel("间隔天数")
    ax.set_ylabel("订单数")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.savefig(FIGS / "fig02_repeat_interval.png", bbox_inches="tight")
    plt.close(fig)

    # 图 3：RFM 分层
    d = rfm.sort_values("gmv", ascending=True)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.6))
    axes[0].barh(d["segment"], d["customers"], color="#2f6f9f")
    axes[0].set_title("各层客户数", fontsize=11)
    axes[0].set_xlabel("客户数")
    axes[1].barh(d["segment"], d["gmv_share"] * 100, color="#c0504d")
    axes[1].set_title("各层 GMV 贡献占比 %", fontsize=11)
    axes[1].set_xlabel("%")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.savefig(FIGS / "fig03_rfm.png", bbox_inches="tight")
    plt.close(fig)


def write_findings(m: dict, retention: pd.DataFrame) -> None:
    rfm_rows = "\n".join(
        f"| {r['segment']} | {int(r['customers']):,} | {r['customer_share']:.1%} | "
        f"{r['gmv']:,.0f} | {r['gmv_share']:.1%} | {r['avg_gmv']:,.0f} | "
        f"{r['avg_recency_days']:.0f} | {r['avg_frequency']:.1f} |"
        for r in m["rfm"]
    )
    lines = [
        "# 电商用户留存与复购分析",
        "",
        "> 由 `src/run.py` 自动生成，数字来自当次运行。",
        "",
        "## 1. 整体",
        "",
        f"- 有客户 ID 的客户：**{m['customers']:,}** 人",
        f"- 复购客户（下单 ≥2 次）：**{m['repeat_customers']:,}** 人，复购率 **{m['repeat_rate']:.1%}**",
        f"- 次月留存率（M1）：**{m['m1_retention']:.1%}**",
        f"- 复购间隔中位数：**{m['median_gap_days']:.0f}** 天，均值 {m['avg_gap_days']:.0f} 天",
        f"- 流失预警（≥2 次购买但已 90 天未回）：**{m['churn_customers']:,}** 人，涉及历史 GMV "
        f"{m['churn_gmv']:,.0f}",
        "",
        "## 2. RFM 分层",
        "",
        "| 分层 | 客户数 | 人数占比 | GMV | GMV 占比 | 人均 GMV | 平均距今(天) | 平均购买次数 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        rfm_rows,
        "",
        "## 3. 怎么读留存矩阵",
        "",
        "矩阵的每一行是一个「同期群」：同一个月首次下单的客户。列是第 N 个月还回来消费的比例。",
        "",
        "- **M0 永远是 100%**，因为首购那个月当然在；",
        "- **对角线往下**表示老客户随时间衰减，越远的月份样本越少，参考价值越低；",
        "- **同一列纵向比较**，能看出哪个 cohort 质量更好——通常是促销月拉来的客户留得差。",
        "",
        "## 4. 结论",
        "",
        f"1. 复购间隔中位数 {m['median_gap_days']:.0f} 天，意味着超过这个天数还没回来的客户，流失概率明显上升，"
        "这也是把「90 天未回」作为流失预警阈值的原因。",
        f"2. 「重要价值」和「重要挽留」两层贡献了绝大部分 GMV，但人数占比很小——"
        "运营资源应该向这两层倾斜，而不是全员发券。",
        f"3. 有 {m['churn_customers']:,} 个客户买过两次以上却已经流失，"
        "这是召回成本最低的一批人，优先于拉新。",
        "",
        "## 5. 一个容易读错的地方（数据截断）",
        "",
        "热力图最下面一两行的留存率会明显偏低，**这不是客户质量差**，而是**观察窗口不够**。",
        "",
        "数据到 2011-12-09 结束。最后几批客户（比如 11 月首购的）本来是 12 月才能观察到 M1，",
        "但 12 月只统计到 9 号，回来的人还没走完，于是 M1 被低估。统计上这叫**右删失**。",
        "",
        "正确做法：",
        "",
        "- 比较不同 cohort 时，只比观察窗口完整的那几行；",
        "- 或者把最后 1–2 个 cohort 从对比里剔除；",
        "- 汇报时说清楚「受数据截止时间影响，末尾 cohort 不可比」。",
        "",
        "**这是留存分析最常见的坑**：不处理截断，会把数据问题误判成业务问题。",
        "",
    ]
    (REPORTS / "findings.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())


