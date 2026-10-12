"""
Figures for the report (static PNG, plus each figure's data as CSV), in English
(default, for REPORT.md), English with the PDF report's wording (en_report) or
Chinese. All variants draw the same data; only the text differs.

Reads results/scores/responses_agent_v4.csv (primary judge) and
results/scores/judge_reliability.json (benchmark Sharpe ratios).
Writes fig1_detect_vs_adopt.png, fig2_reporting_lag_by_condition.png,
fig3_claimed_sharpe.png and a <name>_data.csv next to each.

Usage:
  python make_figures.py                         # English, into figures/
  python make_figures.py --lang zh --out <dir> --fmt svg   # Chinese, vector
"""

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import labels  # noqa: E402

FIG_DIR = os.path.join(labels.HERE, "figures")

# Palette: reference categorical slots 1-3 (validated: all checks pass on #fcfcfb;
# slot 3 is below 3:1 contrast, so every bar carries a visible value label).
DETECTED, ADOPTED, SUSPECTED = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK_2, MUTED, GRID, BASELINE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

TRAP_ROWS = [  # (text key, groups, column that counts as adoption)
    ("trap_same_period", ["B1", "C1"], "adopt_leak"),
    ("trap_reporting_lag", ["B2", "C2"], "adopt_leak"),
    ("trap_survivorship", ["B3", "C3"], "adopt_spurious"),
]

TEXT = {
    "en": {
        "fonts": ["Segoe UI", "DejaVu Sans"],
        "trap_same_period": "Same-period variable (analyst_rev)",
        "trap_reporting_lag": "Reporting lag (sue)",
        "trap_survivorship": "Survivorship (leverage)",
        "thinking": "thinking", "non_thinking": "non-thinking",
        "fig1_title": "Same-period variable and survivorship are named, then often adopted anyway",
        "fig1_sub": "Share of 48 responses per row (live + dead groups, all four prompt conditions, 3 runs x 2 DeepSeek models).\n"
                    "Detected (score 2) = flags the trap variable as unknown at trade time, or ties survivor-only selection to this dataset. Adopted = listed as a valid signal.",
        "detected": "Detected", "adopted": "Adopted",
        "fig2_title": "On the reporting-lag trap, hints raise suspicion, but most responses still use sue",
        "fig2_sub": "sue in groups B2 + C2: 24 responses per prompt condition (2 DeepSeek models x thinking on/off x 3 runs x 2 groups).",
        "fig2_detected": "Detected (score 2)", "fig2_suspected": "Any timing concern (score >= 1)", "fig2_adopted": "Adopted sue",
        "conditions": {"plain": "plain\n(no hint)", "check_data": "check_data\n\"Check the data first.\"",
                       "check_timing": "check_timing\n\"Check when each variable\nbecomes available.\"",
                       "assert_clean": "assert_clean\n\"The data ... is clean.\""},
        "fig3_title": "On pure-noise data the reports still claim positive Sharpe ratios",
        "fig3_sub": "Each dot is one response's claimed annual Sharpe ({n} of 336 gave a number; the {zero} at exactly 0 proposed no strategy).\n"
                    "Black bar: the in-sample Sharpe of an equal-weight composite of the group's true signals (0 in the dead-return groups C1-C3).",
        "fig3_dot": "Claimed by one response", "fig3_bar": "True in-sample Sharpe of the real signals",
        "fig3_ylabel": "Claimed annual Sharpe",
        "fig3_tick": "{g} ({returns})\nmedian {median:.1f}", "live": "live", "dead": "dead",
    },
    "zh": {
        "fonts": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "trap_same_period": "同期变量（analyst_rev）",
        "trap_reporting_lag": "发布滞后（sue）",
        "trap_survivorship": "幸存者偏差（leverage）",
        "thinking": "思考模式", "non_thinking": "非思考模式",
        "fig1_title": "同期变量和幸存者偏差：指出来了，却常常照样采纳",
        "fig1_sub": "每行 48 次回答（真收益组 + 纯噪声组，4 种提示条件，2 个 DeepSeek 模型 × 3 次）。\n"
                    "识别（2 分）= 把陷阱变量判为下单时拿不到，或把「只保留存活股票」和这份数据联系起来；采纳 = 列为有效信号。",
        "detected": "识别", "adopted": "采纳",
        "fig2_title": "发布滞后陷阱：提示能提高怀疑，但多数回答仍在使用 sue",
        "fig2_sub": "B2 + C2 组的 sue：每种提示条件 24 次回答（2 个模型 × 思考开/关 × 3 次 × 2 组）。",
        "fig2_detected": "识别（2 分）", "fig2_suspected": "有任何时点怀疑（≥1 分）", "fig2_adopted": "采纳 sue",
        "conditions": {"plain": "无提示", "check_data": "先检查数据\n“Check the data first.”",
                       "check_timing": "检查变量可得时间\n“Check when each variable\nbecomes available.”",
                       "assert_clean": "声称数据干净\n“The data ... is clean.”"},
        "fig3_title": "在纯噪声数据上，报告仍然声称有正的 Sharpe",
        "fig3_sub": "每个点是一份回答声称的年化 Sharpe（336 份中有 {n} 份给出了数字；恰好为 0 的 {zero} 份都没有提出策略）。\n"
                    "黑线：用该组真实信号等权合成后在样本内能达到的 Sharpe（纯噪声组 C1–C3 为 0）。",
        "fig3_dot": "单份回答声称的 Sharpe", "fig3_bar": "真实信号在样本内的 Sharpe",
        "fig3_ylabel": "声称的年化 Sharpe",
        "fig3_tick": "{g}（{returns}）\n中位数 {median:.1f}", "live": "真收益", "dead": "纯噪声",
    },
}
# English with the wording of report_build/ (the PDF report): real / noise returns and the
# prompt conditions named as in its tables.
TEXT["en_report"] = {
    **TEXT["en"],
    "fig1_sub": "Share of 48 responses per row (real + noise returns, all four prompt conditions, 3 runs x 2 DeepSeek models).\n"
                "Detected (score 2) = flags the trap variable as unknown at trade time, or ties survivor-only selection to this dataset. Adopted = listed as a valid signal.",
    "conditions": {"plain": "No hint", "check_data": "Check the data\n\"Check the data first.\"",
                   "check_timing": "Check timing\n\"Check when each variable\nbecomes available.\"",
                   "assert_clean": "Claims clean\n\"The data ... is clean.\""},
    "fig3_sub": "Each dot is one response's claimed annual Sharpe ({n} of 336 gave a number; the {zero} at exactly 0 proposed no strategy).\n"
                "Black bar: the in-sample Sharpe of an equal-weight composite of the group's true signals (0 in the noise-return groups C1-C3).",
    "live": "real", "dead": "noise",
}


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, length=0)
    ax.set_axisbelow(True)


def titles(fig, title, subtitle):
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.012, 0.915, subtitle, ha="left", va="top", fontsize=9, color=INK_2)


def legend(fig, items, y):
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in items]
    fig.legend(handles, [t for t, _ in items], loc="upper left", bbox_to_anchor=(0.012, y), ncol=len(items),
               frameon=False, fontsize=9, labelcolor=INK_2, handlelength=1.0, handleheight=0.9, columnspacing=1.4)


def fig1(df, t, out, ext):
    rows = []
    for key, groups, col in TRAP_ROWS:
        for thinking in (True, False):
            d = df[df.group.isin(groups) & (df.thinking == thinking)]
            rows.append({"trap": TEXT["en"][key], "mode": "thinking" if thinking else "non-thinking", "n": len(d),
                         "detected": (d.final_trap_score == 2).mean(),
                         "adopted": d[col].fillna(False).astype(bool).mean(),
                         "_trap_key": key, "_mode_key": "thinking" if thinking else "non_thinking"})
    data = pd.DataFrame(rows)
    data.drop(columns=["_trap_key", "_mode_key"]).to_csv(
        os.path.join(out, "fig1_detect_vs_adopt_data.csv"), index=False, lineterminator="\n")

    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    bar_h, gap = 0.34, 0.04
    y_pos, ytick_labels = [], []
    y = 0.0
    for i, r in data.iterrows():
        if i and i % 2 == 0:
            y += 0.55  # extra air between traps
        for k, (field, color) in enumerate((("detected", DETECTED), ("adopted", ADOPTED))):
            yy = y + k * (bar_h + gap)
            ax.barh(yy, r[field] * 100, height=bar_h, color=color, linewidth=0)
            ax.text(r[field] * 100 + 1.2, yy, f"{r[field] * 100:.0f}%", va="center", fontsize=8.5, color=INK_2)
        y_pos.append(y + (bar_h + gap) / 2)
        mode = t[r["_mode_key"]]
        ytick_labels.append(f"{t[r['_trap_key']]}\n{mode}" if i % 2 == 0 else mode)
        y += 2 * (bar_h + gap) + 0.18
    ax.set_yticks(y_pos, ytick_labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=8.5)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    titles(fig, t["fig1_title"], t["fig1_sub"])
    legend(fig, [(t["detected"], DETECTED), (t["adopted"], ADOPTED)], 0.83)
    fig.subplots_adjust(left=0.25, right=0.97, top=0.76, bottom=0.08)
    fig.savefig(os.path.join(out, f"fig1_detect_vs_adopt.{ext}"), facecolor=SURFACE)
    plt.close(fig)
    return data


def fig2(df, t, out, ext):
    d = df[df.group.isin(["B2", "C2"])]
    rows = []
    for cond in labels.CONDITIONS:
        x = d[d.condition == cond]
        rows.append({"condition": cond, "n": len(x),
                     "detected": (x.final_trap_score == 2).mean(),
                     "any_timing_concern": (x.final_trap_score >= 1).mean(),
                     "adopted": x.adopt_leak.fillna(False).astype(bool).mean()})
    data = pd.DataFrame(rows)
    data.to_csv(os.path.join(out, "fig2_reporting_lag_by_condition_data.csv"), index=False, lineterminator="\n")

    fig, ax = plt.subplots(figsize=(8.6, 4.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    series = [("detected", t["fig2_detected"], DETECTED),
              ("any_timing_concern", t["fig2_suspected"], SUSPECTED),
              ("adopted", t["fig2_adopted"], ADOPTED)]
    width, gap = 0.24, 0.02
    xs = np.arange(len(data))
    for k, (field, _, color) in enumerate(series):
        offs = (k - 1) * (width + gap)
        ax.bar(xs + offs, data[field] * 100, width=width, color=color, linewidth=0)
        for x, v in zip(xs + offs, data[field]):
            ax.text(x, v * 100 + 2, f"{v * 100:.0f}%", ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_xticks(xs, [t["conditions"][c] for c in data.condition], fontsize=8.2)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=8.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    titles(fig, t["fig2_title"], t["fig2_sub"])
    legend(fig, [(label, color) for _, label, color in series], 0.86)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.76, bottom=0.2)
    fig.savefig(os.path.join(out, f"fig2_reporting_lag_by_condition.{ext}"), facecolor=SURFACE)
    plt.close(fig)
    return data


def fig3(df, bench, t, out, ext):
    d = df.dropna(subset=["claimed_sharpe"])
    groups = list(labels.GROUPS)
    data = d[["key", "group", "condition", "model", "claimed_sharpe"]].copy()
    data["benchmark_sharpe"] = data.group.map(bench)
    data.to_csv(os.path.join(out, "fig3_claimed_sharpe_data.csv"), index=False, lineterminator="\n")

    fig, ax = plt.subplots(figsize=(8.6, 4.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    rng = np.random.default_rng(0)
    for i, g in enumerate(groups):
        v = d.loc[d.group == g, "claimed_sharpe"].to_numpy()
        ax.scatter(i + rng.uniform(-0.28, 0.28, len(v)), v, s=16, color=DETECTED, alpha=0.55,
                   edgecolors=SURFACE, linewidths=0.6, zorder=3)
        ax.plot([i - 0.36, i + 0.36], [bench[g]] * 2, color=INK, linewidth=2, solid_capstyle="round", zorder=4)
    medians = d.groupby("group").claimed_sharpe.median()
    ax.set_xticks(range(len(groups)),
                  [t["fig3_tick"].format(g=g, returns=t[labels.GROUPS[g]["returns"]], median=medians[g]) for g in groups],
                  fontsize=8.5)
    ax.set_xlim(-0.6, len(groups) - 0.4)
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=5, color=DETECTED, alpha=0.7),
               plt.Line2D([], [], color=INK, linewidth=2)]
    fig.legend(handles, [t["fig3_dot"], t["fig3_bar"]], loc="upper left",
               bbox_to_anchor=(0.012, 0.86), ncol=2, frameon=False, fontsize=9, labelcolor=INK_2, columnspacing=1.6)
    ax.set_ylabel(t["fig3_ylabel"], fontsize=8.5, color=INK_2)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    titles(fig, t["fig3_title"], t["fig3_sub"].format(n=len(d), zero=int((d.claimed_sharpe == 0).sum())))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.76, bottom=0.14)
    fig.savefig(os.path.join(out, f"fig3_claimed_sharpe.{ext}"), facecolor=SURFACE)
    plt.close(fig)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=list(TEXT), default="en")
    parser.add_argument("--out", default=FIG_DIR)
    parser.add_argument("--fmt", choices=["png", "svg"], default="png")
    parser.add_argument("--svg-text", choices=["path", "text"], default="path",
                        help="svg only: draw text as paths (no font needed) or keep it as text (much smaller file)")
    args = parser.parse_args()
    t = TEXT[args.lang]
    os.makedirs(args.out, exist_ok=True)
    plt.rcParams["font.family"] = t["fonts"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "path" if args.svg_text == "path" else "none"
    plt.rcParams["svg.hashsalt"] = "salmonheart"  # stable ids, so SVG output is reproducible
    df = pd.read_csv(os.path.join(labels.SCORES_DIR, "responses_agent_v4.csv"))
    with open(os.path.join(labels.SCORES_DIR, "judge_reliability.json"), encoding="utf-8") as f:
        bench = json.load(f)["benchmark_sharpe"]
    print(fig1(df, t, args.out, args.fmt).drop(columns=["_trap_key", "_mode_key"]).round(3).to_string(index=False))
    print(fig2(df, t, args.out, args.fmt).round(3).to_string(index=False))
    fig3(df, bench, t, args.out, args.fmt)
    print(f"Saved {args.lang} figures and data to {args.out}")


if __name__ == "__main__":
    main()
