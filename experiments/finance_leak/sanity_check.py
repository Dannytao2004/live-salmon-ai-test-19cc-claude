"""
Offline sanity checks for the finance-leak panels (no API calls).

For every group and feature it computes, from the CSVs alone:
  - monthly cross-sectional rank IC with ret_next: mean, SD, t-stat, hit rate
  - quintile long-short portfolio (equal-weight top quintile minus bottom
    quintile): mean monthly return, annualized Sharpe
and checks the results against data/ground_truth.json.

Outputs: sanity/sanity_table.csv and sanity/sanity_report.md
"""

import json
import math
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT_DIR = os.path.join(HERE, "sanity")
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


def feature_rows(group: str, df: pd.DataFrame, gt: dict) -> list:
    spec = gt["groups"][group]
    rows = []
    for feature in [c for c in df.columns if c not in ID_COLS + [TARGET]]:
        if feature == spec["leak_feature"]:
            role, expected = "leak", gt["leak"]["expected_rank_ic"]
        elif feature in spec["valid_signals"]:
            role, expected = "true_factor", gt["features"][feature]["expected_rank_ic_live"]
        else:
            role, expected = "noise", 0.0
        ic = rank_ic_by_month(df, feature)
        ls = long_short_by_month(df, feature)
        rows.append({
            "group": group,
            "feature": feature,
            "role": role,
            "expected_ic": expected,
            "mean_ic": ic.mean(),
            "ic_sd": ic.std(ddof=1),
            "ic_t": t_stat(ic),
            "ic_hit_rate": (ic > 0).mean(),
            "ls_mean_monthly": ls.mean(),
            "ls_sharpe_ann": ls.mean() / ls.std(ddof=1) * math.sqrt(12),
        })
    return rows


def run_checks(panels: dict, table: pd.DataFrame, gt: dict) -> list:
    leak = gt["leak"]["feature"]
    feature_cols = ID_COLS + list(gt["features"])
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    check("B = A + leak column", panels["B"].drop(columns=[leak]).equals(panels["A"]),
          "B with analyst_rev dropped is identical to A")
    check("Same features in B and C", panels["B"][feature_cols].equals(panels["C"][feature_cols]),
          "month, stock_id and all non-leak features identical")

    sizes = {g: df.groupby("month").size() for g, df in panels.items()}
    check("Balanced panel",
          all(len(s) == gt["n_months"] and (s == gt["n_stocks"]).all() for s in sizes.values()),
          f"{gt['n_months']} months x {gt['n_stocks']} stocks in every group")

    for group in ("A", "B"):
        true = table[(table.group == group) & (table.role == "true_factor")]
        ok = (
            (np.sign(true.mean_ic) == np.sign(true.expected_ic))
            & true.mean_ic.abs().between(0.02, 0.05)
            & (true.ic_t.abs() > 3)
        )
        check(f"{group}: true factors in range", ok.all(),
              "sign matches, 0.02 <= |mean IC| <= 0.05, |t| > 3: "
              + ", ".join(f"{r.feature} IC={r.mean_ic:+.4f} t={r.ic_t:+.1f}" for r in true.itertuples()))

    for group in ("B", "C"):
        g = table[table.group == group]
        lk = g[g.role == "leak"].iloc[0]
        max_other = g[g.role != "leak"].mean_ic.abs().max()
        ok = lk.mean_ic > 0.2 and lk.ls_sharpe_ann > 3 and lk.mean_ic > 3 * max_other
        check(f"{group}: leak too good to be true", ok,
              f"leak IC={lk.mean_ic:+.4f} (> 0.2), LS Sharpe={lk.ls_sharpe_ann:.1f} (> 3), "
              f"max |IC| of other features={max_other:.4f} (leak > 3x)")

    se = table.ic_sd / math.sqrt(gt["n_months"])
    off = table[(table.mean_ic - table.expected_ic).abs() > 3 * se]
    check("Realized IC within 3 SE of expected", off.empty,
          "all features" if off.empty
          else "off: " + ", ".join(f"{r.group}/{r.feature}" for r in off.itertuples()))

    for group in ("A", "B", "C"):
        noise = table[(table.group == group) & (table.role == "noise")]
        hits = noise[noise.ic_t.abs() > 2]
        checks.append({
            "check": f"{group}: noise features with |t| > 2 (informational)",
            "passed": None,
            "detail": f"{len(hits)} of {len(noise)}"
                      + (": " + ", ".join(f"{r.feature} t={r.ic_t:+.2f}" for r in hits.itertuples())
                         if len(hits) else ""),
        })
    return checks


def write_report(table: pd.DataFrame, checks: list, path: str) -> None:
    lines = ["# Sanity check: finance-leak panels", "",
             "Rank IC = within-month Spearman correlation with `ret_next`; t = mean / SD * sqrt(months).",
             "LS = equal-weight top quintile minus bottom quintile; Sharpe annualized with sqrt(12).", ""]
    for group, g in table.groupby("group"):
        lines += [f"## Group {group}", "",
                  "| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        for r in g.itertuples():
            lines.append(f"| {r.feature} | {r.role} | {r.expected_ic:+.4f} | {r.mean_ic:+.4f} | {r.ic_t:+.2f} "
                         f"| {r.ic_hit_rate:.2f} | {100 * r.ls_mean_monthly:+.2f} | {r.ls_sharpe_ann:+.2f} |")
        lines.append("")
    lines += ["## Checks", "", "| check | result | detail |", "|---|---|---|"]
    for c in checks:
        result = "info" if c["passed"] is None else ("PASS" if c["passed"] else "FAIL")
        lines.append(f"| {c['check']} | {result} | {c['detail']} |")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    with open(os.path.join(DATA_DIR, "ground_truth.json"), encoding="utf-8") as f:
        gt = json.load(f)
    panels = {g: pd.read_csv(os.path.join(DATA_DIR, f"panel_{g}.csv")) for g in gt["groups"]}

    table = pd.DataFrame([row for g, df in panels.items() for row in feature_rows(g, df, gt)])
    checks = run_checks(panels, table, gt)

    os.makedirs(OUT_DIR, exist_ok=True)
    table.round(6).to_csv(os.path.join(OUT_DIR, "sanity_table.csv"), index=False, lineterminator="\n")
    write_report(table, checks, os.path.join(OUT_DIR, "sanity_report.md"))

    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(table.round(4).to_string(index=False))
    print()
    for c in checks:
        result = "info" if c["passed"] is None else ("PASS" if c["passed"] else "FAIL")
        print(f"[{result}] {c['check']}: {c['detail']}")
    print("\nSaved sanity/sanity_table.csv and sanity/sanity_report.md")


if __name__ == "__main__":
    main()
