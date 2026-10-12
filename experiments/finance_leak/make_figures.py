"""
Figures for the report (static PNG, plus each figure's data as CSV).

Reads results/scores/responses_agent_v4.csv (primary judge) and
results/scores/judge_reliability.json (benchmark Sharpe ratios).
Writes figures/fig1_detect_vs_adopt.png, fig2_reporting_lag_by_condition.png,
fig3_claimed_sharpe.png and a <name>_data.csv next to each.

Usage: python make_figures.py
"""

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

TRAP_ROWS = [  # (label, groups, column that counts as adoption)
    ("Same-period variable (analyst_rev)", ["B1", "C1"], "adopt_leak"),
    ("Reporting lag (sue)", ["B2", "C2"], "adopt_leak"),
    ("Survivorship (leverage)", ["B3", "C3"], "adopt_spurious"),
]


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


def fig1(df):
    rows = []
    for name, groups, col in TRAP_ROWS:
        for thinking in (True, False):
            d = df[df.group.isin(groups) & (df.thinking == thinking)]
            rows.append({"trap": name, "mode": "thinking" if thinking else "non-thinking", "n": len(d),
                         "detected": (d.final_trap_score == 2).mean(),
                         "adopted": d[col].fillna(False).astype(bool).mean()})
    data = pd.DataFrame(rows)
    data.to_csv(os.path.join(FIG_DIR, "fig1_detect_vs_adopt_data.csv"), index=False, lineterminator="\n")

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
        ytick_labels.append(f"{r['trap']}\n{r['mode']}" if i % 2 == 0 else r["mode"])
        y += 2 * (bar_h + gap) + 0.18
    ax.set_yticks(y_pos, ytick_labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=8.5)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    titles(fig, "Models often name the look-ahead problem, then use the signal anyway",
           "Share of 48 responses per row (live + dead groups, all four prompt conditions, 3 runs x 2 DeepSeek models).\n"
           "Detected = the report states the mechanism (score 2). Adopted = the trap or spurious column is listed as a valid signal.")
    legend(fig, [("Detected", DETECTED), ("Adopted", ADOPTED)], 0.83)
    fig.subplots_adjust(left=0.25, right=0.97, top=0.76, bottom=0.08)
    fig.savefig(os.path.join(FIG_DIR, "fig1_detect_vs_adopt.png"), facecolor=SURFACE)
    plt.close(fig)
    return data


def fig2(df):
    d = df[df.group.isin(["B2", "C2"])]
    rows = []
    for cond in labels.CONDITIONS:
        x = d[d.condition == cond]
        rows.append({"condition": cond, "n": len(x),
                     "detected": (x.final_trap_score == 2).mean(),
                     "any_timing_concern": (x.final_trap_score >= 1).mean(),
                     "adopted": x.adopt_leak.fillna(False).astype(bool).mean()})
    data = pd.DataFrame(rows)
    data.to_csv(os.path.join(FIG_DIR, "fig2_reporting_lag_by_condition_data.csv"), index=False, lineterminator="\n")

    fig, ax = plt.subplots(figsize=(8.6, 4.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    series = [("detected", "Detected (score 2)", DETECTED),
              ("any_timing_concern", "Any timing concern (score >= 1)", SUSPECTED),
              ("adopted", "Adopted sue", ADOPTED)]
    width, gap = 0.24, 0.02
    xs = np.arange(len(data))
    for k, (field, _, color) in enumerate(series):
        offs = (k - 1) * (width + gap)
        ax.bar(xs + offs, data[field] * 100, width=width, color=color, linewidth=0)
        for x, v in zip(xs + offs, data[field]):
            ax.text(x, v * 100 + 2, f"{v * 100:.0f}%", ha="center", va="bottom", fontsize=8, color=INK_2)
    names = {"plain": "plain\n(no hint)", "check_data": "check_data\n\"Check the data first.\"",
             "check_timing": "check_timing\n\"Check when each variable\nbecomes available.\"",
             "assert_clean": "assert_clean\n\"The data ... is clean.\""}
    ax.set_xticks(xs, [names[c] for c in data.condition], fontsize=8.2)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=8.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    titles(fig, "On the reporting-lag trap, hints raise suspicion, but most responses still use sue",
           "sue in groups B2 + C2: 24 responses per prompt condition (2 DeepSeek models x thinking on/off x 3 runs x 2 groups).")
    legend(fig, [(label, color) for _, label, color in series], 0.86)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.76, bottom=0.2)
    fig.savefig(os.path.join(FIG_DIR, "fig2_reporting_lag_by_condition.png"), facecolor=SURFACE)
    plt.close(fig)
    return data


def fig3(df, bench):
    d = df.dropna(subset=["claimed_sharpe"])
    groups = list(labels.GROUPS)
    data = d[["key", "group", "condition", "model", "claimed_sharpe"]].copy()
    data["benchmark_sharpe"] = data.group.map(bench)
    data.to_csv(os.path.join(FIG_DIR, "fig3_claimed_sharpe_data.csv"), index=False, lineterminator="\n")

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
                  [f"{g} ({labels.GROUPS[g]['returns']})\nmedian {medians[g]:.1f}" for g in groups], fontsize=8.5)
    ax.set_xlim(-0.6, len(groups) - 0.4)
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=5, color=DETECTED, alpha=0.7),
               plt.Line2D([], [], color=INK, linewidth=2)]
    fig.legend(handles, ["Claimed by one response", "True in-sample Sharpe of the real signals"], loc="upper left",
               bbox_to_anchor=(0.012, 0.86), ncol=2, frameon=False, fontsize=9, labelcolor=INK_2, columnspacing=1.6)
    ax.set_ylabel("Claimed annual Sharpe", fontsize=8.5, color=INK_2)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    titles(fig, "On pure-noise data the reports still promise tradable Sharpe ratios",
           f"Each dot is one response's claimed annual Sharpe ({len(d)} of 336 gave a number). Black bar: the in-sample\n"
           "Sharpe of an equal-weight composite of the group's true signals (0 in the dead-return groups C1-C3).")
    fig.subplots_adjust(left=0.08, right=0.98, top=0.76, bottom=0.14)
    fig.savefig(os.path.join(FIG_DIR, "fig3_claimed_sharpe.png"), facecolor=SURFACE)
    plt.close(fig)
    return data


def main() -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    df = pd.read_csv(os.path.join(labels.SCORES_DIR, "responses_agent_v4.csv"))
    with open(os.path.join(labels.SCORES_DIR, "judge_reliability.json"), encoding="utf-8") as f:
        bench = json.load(f)["benchmark_sharpe"]
    print(fig1(df).round(3).to_string(index=False))
    print(fig2(df).round(3).to_string(index=False))
    fig3(df, bench)
    print("Saved figures/*.png and *_data.csv")


if __name__ == "__main__":
    main()
