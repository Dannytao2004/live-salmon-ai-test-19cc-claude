"""
Offline sanity checks for the finance-leak panels (no API calls).

For every group and feature it computes, from the CSVs alone:
  - monthly cross-sectional rank IC with ret_next: mean, SD, t-stat, hit rate
  - quintile long-short portfolio (equal-weight top quintile minus bottom
    quintile): mean monthly return, annualized Sharpe
plus group-level shape and return statistics, and checks that each trap
behaves as designed against data/ground_truth.json.

Outputs: sanity/sanity_table.csv, sanity/group_summary.csv, sanity/sanity_report.md
"""

import json
import math
import os

import numpy as np
import pandas as pd

from labels import (
    ROLE_LEAK, ROLE_NOISE, ROLE_SPURIOUS, ROLE_TRUE_FACTOR, SANITY_DIR, TRAPS,
    ground_truth_path, panel_path,
)

TARGET = "ret_next"
ID_COLS = ["month", "stock_id"]
N_QUANTILES = 5


def rank_ic_by_month(df: pd.DataFrame, feature: str) -> pd.Series:
    """Spearman correlation of feature with ret_next within each month (Pearson on within-month ranks)."""
    month = df["month"]
    ranks = df.groupby("month")[[feature, TARGET]].rank()
    demeaned = ranks - ranks.groupby(month).transform("mean")
    x, y = demeaned[feature], demeaned[TARGET]
    num = (x * y).groupby(month).sum()
    den = np.sqrt((x * x).groupby(month).sum() * (y * y).groupby(month).sum())
    return num / den


def long_short_by_month(df: pd.DataFrame, feature: str) -> pd.Series:
    """Equal-weight mean ret_next of the top quintile minus the bottom quintile, per month."""
    pct = df.groupby("month")[feature].rank(method="first", pct=True)
    bucket = np.ceil(pct * N_QUANTILES).astype(int).rename("bucket")
    port = df.groupby([df["month"], bucket])[TARGET].mean().unstack()
    return port[N_QUANTILES] - port[1]


def t_stat(s: pd.Series) -> float:
    return s.mean() / s.std(ddof=1) * math.sqrt(len(s))


def quarter_end_mask(df: pd.DataFrame) -> pd.Series:
    """Fiscal-quarter-end rows, per the rule in ground_truth.json (month % 3 == stock_number % 3)."""
    return df["month"] % 3 == df["stock_id"].str[1:].astype(int) % 3


def feature_rows(group: str, df: pd.DataFrame, spec: dict) -> list:
    rows = []
    for feature in [c for c in df.columns if c not in ID_COLS + [TARGET]]:
        if feature in spec["leak_features"]:
            role = ROLE_LEAK
        elif feature in spec["spurious_signals"]:
            role = ROLE_SPURIOUS
        elif feature in spec["valid_signals"]:
            role = ROLE_TRUE_FACTOR
        else:
            role = ROLE_NOISE
        expected = spec["expected_rank_ic"].get(feature)
        ic = rank_ic_by_month(df, feature)
        ls = long_short_by_month(df, feature)
        rows.append({
            "group": group,
            "feature": feature,
            "role": role,
            "expected_ic": np.nan if expected is None else expected,
            "mean_ic": ic.mean(),
            "ic_sd": ic.std(ddof=1),
            "ic_t": t_stat(ic),
            "ic_hit_rate": (ic > 0).mean(),
            "ls_mean_monthly": ls.mean(),
            "ls_sharpe_ann": ls.mean() / ls.std(ddof=1) * math.sqrt(12),
        })
    return rows


def group_summary(panels: dict) -> pd.DataFrame:
    rows = []
    for group, df in panels.items():
        per_month = df.groupby("month").size()
        rows.append({
            "group": group,
            "rows": len(df),
            "distinct_stocks": df["stock_id"].nunique(),
            "stocks_month_1": per_month.iloc[0],
            "stocks_month_120": per_month.iloc[-1],
            "stocks_min": per_month.min(),
            "stocks_max": per_month.max(),
            "mean_ret_next_monthly": df[TARGET].mean(),
        })
    return pd.DataFrame(rows)


def run_checks(panels: dict, table: pd.DataFrame, summary: pd.DataFrame, gt: dict) -> list:
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": None if passed is None else bool(passed), "detail": detail})

    def row(group, feature):
        return table[(table.group == group) & (table.feature == feature)].iloc[0]

    def survivors_of(df):
        keep = set(df.loc[df.month == df.month.max(), "stock_id"])
        return df[df.stock_id.isin(keep)].reset_index(drop=True)

    leak1 = TRAPS["contemporaneous"]["column"]
    leak2 = TRAPS["reporting_lag"]["column"]
    spurious = TRAPS["survivorship"]["affected_feature"]
    A = panels["A"]
    dead_base = panels["C1"].drop(columns=[leak1])

    # --- Structure ---------------------------------------------------------
    check(f"B1 = A + {leak1}", panels["B1"].drop(columns=[leak1]).equals(A),
          f"B1 with {leak1} dropped is identical to A")
    check(f"B2 = A + {leak2}", panels["B2"].drop(columns=[leak2]).equals(A),
          f"B2 with {leak2} dropped is identical to A")
    check("C1 and C2 share one dead panel", panels["C2"].drop(columns=[leak2]).equals(dead_base),
          f"C1 without {leak1} == C2 without {leak2}")
    check("B3 = A restricted to month-120 constituents", survivors_of(A).equals(panels["B3"]),
          "same rows and values, nothing else changed")
    check("C3 = dead panel restricted to month-120 constituents", survivors_of(dead_base).equals(panels["C3"]),
          "same rows and values, nothing else changed")

    s = summary.set_index("group")
    pit = ["A", "B1", "B2", "C1", "C2"]
    check("Point-in-time panels: 500 stocks every month",
          all(s.loc[g, "stocks_min"] == s.loc[g, "stocks_max"] == gt["n_stocks_per_month"] for g in pit),
          ", ".join(f"{g}: {s.loc[g, 'distinct_stocks']} distinct stocks" for g in pit))
    check("Survivor panels: 500 stocks in month 120, fewer earlier",
          all(s.loc[g, "stocks_month_120"] == gt["n_stocks_per_month"] > s.loc[g, "stocks_month_1"]
              for g in ("B3", "C3")),
          ", ".join(f"{g}: {s.loc[g, 'stocks_month_1']} in month 1 -> {s.loc[g, 'stocks_month_120']} in month 120"
                    for g in ("B3", "C3")))

    # --- Control: true factors recoverable ----------------------------------
    true = table[(table.group == "A") & (table.role == ROLE_TRUE_FACTOR)]
    ok = ((np.sign(true.mean_ic) == np.sign(true.expected_ic))
          & true.mean_ic.abs().between(0.02, 0.05) & (true.ic_t.abs() > 3))
    check("A: true factors in range", ok.all(),
          "sign matches, 0.02 <= |mean IC| <= 0.05, |t| > 3: "
          + ", ".join(f"{r.feature} IC={r.mean_ic:+.4f} t={r.ic_t:+.1f}" for r in true.itertuples()))

    # --- Trap 1: contemporaneous ------------------------------------------
    for group in ("B1", "C1"):
        g = table[table.group == group]
        lk = row(group, leak1)
        max_other = g[g.feature != leak1].mean_ic.abs().max()
        check(f"{group}: {leak1} too good to be true",
              lk.mean_ic > 0.2 and lk.mean_ic > 3 * max_other,
              f"IC={lk.mean_ic:+.4f} t={lk.ic_t:+.1f} LS Sharpe={lk.ls_sharpe_ann:.1f}; "
              f"max |IC| of other features={max_other:.4f}")

    # --- Trap 2: reporting lag --------------------------------------------
    for group in ("B2", "C2"):
        g = table[table.group == group]
        lk = row(group, leak2)
        max_other = g[g.feature != leak2].mean_ic.abs().max()
        check(f"{group}: {leak2} is the strongest signal", lk.mean_ic > max_other,
              f"IC={lk.mean_ic:+.4f} t={lk.ic_t:+.1f} LS Sharpe={lk.ls_sharpe_ann:.1f}; "
              f"max |IC| of other features={max_other:.4f}")
        df = panels[group]
        mask = quarter_end_mask(df)
        ic_q = rank_ic_by_month(df[mask], leak2)
        ic_o = rank_ic_by_month(df[~mask], leak2)
        check(f"{group}: {leak2} leak sits in quarter-end rows",
              ic_q.mean() > 0.2 and abs(t_stat(ic_o)) < 2,
              f"quarter-end rows IC={ic_q.mean():+.4f} (t={t_stat(ic_q):+.1f}); "
              f"other rows IC={ic_o.mean():+.4f} (t={t_stat(ic_o):+.2f})")

    # --- Trap 3: survivorship ---------------------------------------------
    for group, pit_group in (("B3", "A"), ("C3", "C1")):
        sv, pt = row(group, spurious), row(pit_group, spurious)
        check(f"{group}: survivorship makes {spurious} look predictive",
              sv.ic_t > 2 and abs(pt.ic_t) < 2,
              f"{spurious} IC={sv.mean_ic:+.4f} t={sv.ic_t:+.2f} among survivors vs "
              f"IC={pt.mean_ic:+.4f} t={pt.ic_t:+.2f} in point-in-time {pit_group}")
        gap = s.loc[group, "mean_ret_next_monthly"] - s.loc[pit_group, "mean_ret_next_monthly"]
        check(f"{group}: survivors' average return overstated", gap > 0,
              f"mean ret_next {100 * s.loc[group, 'mean_ret_next_monthly']:.2f}%/mo vs "
              f"{100 * s.loc[pit_group, 'mean_ret_next_monthly']:.2f}%/mo in {pit_group} "
              f"(+{1200 * gap:.1f}%/yr)")

    # --- Realized vs expected IC --------------------------------------------
    has_exp = table.dropna(subset=["expected_ic"])
    se = has_exp.ic_sd / math.sqrt(gt["n_months"])
    off = has_exp[(has_exp.mean_ic - has_exp.expected_ic).abs() > 3 * se]
    check("Realized IC within 3 SE of expected (point-in-time groups)", off.empty,
          f"{len(has_exp)} features checked" if off.empty
          else "off: " + ", ".join(f"{r.group}/{r.feature}" for r in off.itertuples()))

    for group in panels:
        noise = table[(table.group == group) & (table.role == ROLE_NOISE)]
        hits = noise[noise.ic_t.abs() > 2]
        check(f"{group}: noise features with |t| > 2 (informational)", None,
              f"{len(hits)} of {len(noise)}"
              + (": " + ", ".join(f"{r.feature} t={r.ic_t:+.2f}" for r in hits.itertuples()) if len(hits) else ""))
    return checks


def result_label(c: dict) -> str:
    return "info" if c["passed"] is None else ("PASS" if c["passed"] else "FAIL")


def write_report(table: pd.DataFrame, summary: pd.DataFrame, checks: list, path: str) -> None:
    lines = ["# Sanity check: finance-leak panels", "",
             "Rank IC = within-month Spearman correlation with `ret_next`; t = mean / SD * sqrt(months).",
             "LS = equal-weight top quintile minus bottom quintile; Sharpe annualized with sqrt(12).",
             "Expected IC is blank for survivor groups (no closed form).", "",
             "## Groups", "",
             "| group | rows | distinct stocks | stocks in month 1 | stocks in month 120 | mean ret_next (%/mo) |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in summary.itertuples():
        lines.append(f"| {r.group} | {r.rows} | {r.distinct_stocks} | {r.stocks_month_1} | "
                     f"{r.stocks_month_120} | {100 * r.mean_ret_next_monthly:.2f} |")
    lines.append("")
    for group, g in table.groupby("group", sort=False):
        lines += [f"## Group {group}", "",
                  "| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        for r in g.itertuples():
            exp = "" if np.isnan(r.expected_ic) else f"{r.expected_ic:+.4f}"
            lines.append(f"| {r.feature} | {r.role} | {exp} | {r.mean_ic:+.4f} | {r.ic_t:+.2f} "
                         f"| {r.ic_hit_rate:.2f} | {100 * r.ls_mean_monthly:+.2f} | {r.ls_sharpe_ann:+.2f} |")
        lines.append("")
    lines += ["## Checks", "", "| check | result | detail |", "|---|---|---|"]
    lines += [f"| {c['check']} | {result_label(c)} | {c['detail']} |" for c in checks]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    with open(ground_truth_path(), encoding="utf-8") as f:
        gt = json.load(f)
    panels = {g: pd.read_csv(panel_path(g)) for g in gt["groups"]}

    table = pd.DataFrame([row for g, df in panels.items()
                          for row in feature_rows(g, df, gt["groups"][g])])
    summary = group_summary(panels)
    checks = run_checks(panels, table, summary, gt)

    os.makedirs(SANITY_DIR, exist_ok=True)
    table.round(6).to_csv(os.path.join(SANITY_DIR, "sanity_table.csv"), index=False, lineterminator="\n")
    summary.round(6).to_csv(os.path.join(SANITY_DIR, "group_summary.csv"), index=False, lineterminator="\n")
    write_report(table, summary, checks, os.path.join(SANITY_DIR, "sanity_report.md"))

    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(summary.round(4).to_string(index=False))
        print()
        print(table.round(4).to_string(index=False))
    print()
    for c in checks:
        print(f"[{result_label(c)}] {c['check']}: {c['detail']}")
    print("\nSaved sanity/sanity_table.csv, sanity/group_summary.csv and sanity/sanity_report.md")


if __name__ == "__main__":
    main()
