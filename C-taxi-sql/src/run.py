# -*- coding: utf-8 -*-
"""纽约黄色出租车：用 SQL 分析 900 万条真实行程。

运行：python src/run.py   （需要 data/ 下有 yellow_tripdata_*.parquet）
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGS = REPORTS / "figs"
DB = ROOT / "taxi.duckdb"

# 纽约 TLC 官方支付方式编码
PAYMENT_NAMES = {
    0: "灵活计价(Flex)",
    1: "信用卡",
    2: "现金",
    3: "不收费(No charge)",
    4: "争议(Dispute)",
    5: "未知",
    6: "作废行程",
}


def _log(m: str) -> None:
    print(f"  - {m}")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))

    print("[1/3] 数据质量体检")
    con.execute((SQL_DIR / "01_quality.sql").read_text(encoding="utf-8"))
    q = con.execute("select * from quality_check").df().iloc[0].to_dict()

    print("[2/3] 清洗与主题汇总")
    con.execute((SQL_DIR / "02_analysis.sql").read_text(encoding="utf-8"))

    print("[3/3] 出图与报告")
    heat = con.execute("select * from ads_demand_heatmap").df()
    pay = con.execute("select * from ads_payment").df()
    zone = con.execute("select * from ads_zone_rank limit 15").df()
    daily = con.execute("select * from ads_daily order by 1").df()
    clean_rows, avg_min, avg_dist = con.execute(
        "select count(*), avg(duration_min), avg(trip_distance) from dim_trip_clean"
    ).fetchone()
    speed = con.execute(
        "select avg(trip_distance / (duration_min / 60.0)) from dim_trip_clean where duration_min > 5"
    ).fetchone()[0]

    metrics = {
        "total_rows": int(q["total_rows"]),
        "clean_rows": int(clean_rows),
        "clean_ratio": round(clean_rows / q["total_rows"], 4),
        "bad_distance": int(q["bad_distance"]),
        "bad_duration": int(q["bad_duration"]),
        "bad_amount": int(q["bad_amount"]),
        "out_of_range": int(q["out_of_range"]),
        "avg_duration_min": round(float(avg_min), 1),
        "avg_distance_miles": round(float(avg_dist), 2),
        "avg_speed_mph": round(float(speed), 1),
        "payment": pay.to_dict(orient="records"),
        "peak_hour": int(heat.groupby("pickup_hour")["trips"].sum().idxmax()),
        "busiest_zone": int(zone.iloc[0]["pu_zone"]),
        "daily_trips_mean": round(float(daily["trips"].mean()), 0),
    }
    metrics["payment"] = [
        {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in r.items()}
        for r in metrics["payment"]
    ]
    (REPORTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    make_figures(heat, pay, zone, daily)
    write_findings(metrics, pay)
    print("完成：", REPORTS / "metrics.json")
    return 0


def make_figures(heat: pd.DataFrame, pay: pd.DataFrame, zone: pd.DataFrame, daily: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130

    # 图 1：时段 × 星期 热力图
    pivot = heat.pivot_table(index="pickup_dow", columns="pickup_hour", values="trips").fillna(0)
    fig, ax = plt.subplots(figsize=(10.2, 3.2))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
    ax.set_yticks(range(7))
    ax.set_yticklabels(["周日", "周一", "周二", "周三", "周四", "周五", "周六"], fontsize=9)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(range(0, 24, 2), fontsize=8)
    ax.set_xlabel("小时")
    ax.set_title("不同星期 × 小时的行程量（颜色越深越忙）", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    fig.savefig(FIGS / "fig01_demand_heatmap.png", bbox_inches="tight")
    plt.close(fig)

    # 图 2：支付方式
    fig, ax = plt.subplots(figsize=(5.0, 3.8))
    top = pay.head(4)
    ax.pie(top["share"], labels=[f"类型 {int(t)}" for t in top["payment_type"]],
           autopct="%1.1f%%", startangle=90,
           colors=["#1f3a5f", "#2f6f9f", "#7aa6c2", "#c0504d"])
    ax.set_title("支付方式占比", fontsize=11)
    fig.savefig(FIGS / "fig02_payment.png", bbox_inches="tight")
    plt.close(fig)

    # 图 3：上车区域 Top15
    d = zone.iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.barh([f"Zone {int(z)}" for z in d["pu_zone"]], d["trips"], color="#2f6f9f")
    ax.set_title("上车区域 Top15", fontsize=11)
    ax.set_xlabel("行程数")
    ax.grid(alpha=0.25)
    fig.savefig(FIGS / "fig03_zones.png", bbox_inches="tight")
    plt.close(fig)

    # 图 4：日均行程
    fig, ax = plt.subplots(figsize=(9.4, 3.2))
    ax.plot(daily["pickup_date"], daily["trips"], color="#1f3a5f", lw=1.2)
    ax.set_title("每日行程量（找异常天/节假日）", fontsize=11)
    ax.set_ylabel("行程数")
    ax.tick_params(axis="x", labelsize=7)
    ax.grid(alpha=0.25)
    fig.savefig(FIGS / "fig04_daily.png", bbox_inches="tight")
    plt.close(fig)


def write_findings(m: dict, pay: pd.DataFrame) -> None:
    lines = [
        "# 纽约黄色出租车行程分析（SQL）",
        "",
        "> 由 `src/run.py` 自动生成。",
        "",
        "## 1. 数据质量",
        "",
        f"- 原始行数：**{m['total_rows']:,}**",
        f"- 清洗后保留：**{m['clean_rows']:,}**（{m['clean_ratio']:.1%}）",
        f"- 里程 ≤0：{m['bad_distance']:,} 行；时间倒挂：{m['bad_duration']:,} 行；"
        f"金额 ≤0：{m['bad_amount']:,} 行；日期越界：{m['out_of_range']:,} 行",
        "",
        "真实数据的脏是常态。体检这一步不做，后面所有结论都不可信。",
        "",
        "## 2. 关键发现",
        "",
        f"- 平均行程时长 **{m['avg_duration_min']} 分钟**，平均里程 **{m['avg_distance_miles']} 英里**，"
        f"平均速度约 **{m['avg_speed_mph']} 英里/小时**",
        f"- 全周期最忙的小时是 **{m['peak_hour']} 点**；最忙的上车区域是 **Zone {m['busiest_zone']}**",
        f"- 日均行程约 **{m['daily_trips_mean']:,.0f}** 单",
        "",
        "## 3. 支付方式",
        "",
        "| 支付方式 | 编号 | 行程数 | 占比 | 平均小费 | 小费率 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in m["payment"]:
        t = int(r["payment_type"])
        lines.append(
            f"| {PAYMENT_NAMES.get(t, '其他')} | {t} | {int(r['trips']):,} | {r['share']:.1%} | "
            f"{r['avg_tip']:.2f} | {r['tip_rate']:.1%} |"
        )
    lines += [
        "",
        "## 4. 一个必须看出来的陷阱",
        "",
        "表里「现金」的小费率是 **0%**。这不是说现金乘客不给小费，而是**计价器记录不到现金小费**——",
        "小费直接给司机，不进系统。",
        "",
        "所以：",
        "",
        "- 不能得出「现金乘客更小气」的结论；",
        "- 比较小费率时只能限定信用卡用户；",
        "- 「不收费」「争议」这两类的 0% 也不是真实行为，是业务口径不同。",
        "",
        "这类问题叫**指标口径陷阱**：数字本身没错，错的是对它的解释。",
        "",
        "## 5. 可以继续做的",
        "",
        "- 用 Zone ID 关联官方 zone lookup 表，把区域编号换成人看得懂的地名；",
        "- 按天气/节假日/大型活动做外部因素关联；",
        "- 用 12 个月数据做同比，观察季节性。",
        "",
    ]
    (REPORTS / "findings.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
