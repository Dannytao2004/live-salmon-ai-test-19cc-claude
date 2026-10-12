"""
Every number cited in REPORT.md, computed from the result files.

Writes results/scores/report_numbers.json and prints it.
Usage: python report_numbers.py
"""

import glob
import json
import os
import re

import pandas as pd

import labels


def frac(s) -> str:
    s = pd.Series(s).dropna().astype(bool)
    return f"{int(s.sum())}/{len(s)}"


def main() -> None:
    A = pd.read_csv(os.path.join(labels.SCORES_DIR, "responses_agent_v4.csv"))
    rel = json.load(open(os.path.join(labels.SCORES_DIR, "judge_reliability.json"), encoding="utf-8"))
    sanity = pd.read_csv(os.path.join(labels.SANITY_DIR, "sanity_table.csv"))
    adopt = (A.adopt_leak.fillna(False) | A.adopt_spurious.fillna(False)).astype(bool)
    A = A.assign(adopted=adopt, detected=A.final_trap_score == 2, suspected=A.final_trap_score >= 1)
    traps = {"contemporaneous": ["B1", "C1"], "reporting_lag": ["B2", "C2"], "survivorship": ["B3", "C3"]}
    n = {}

    n["responses"] = len(A)
    n["parse_failed"] = int((A.parse_method == "failed").sum())
    n["reliability"] = {k: rel[k] for k in rel if k != "benchmark_sharpe"}
    n["benchmark_sharpe"] = rel["benchmark_sharpe"]

    a = A[A.group == "A"]
    n["A"] = {"all_three_true_factors": frac(a.true_recall == 1), "noise_fp_any": frac(a.noise_fp_any)}

    n["by_trap"] = {}
    for trap, gs in traps.items():
        d = A[A.group.isin(gs)]
        n["by_trap"][trap] = {
            "detected": frac(d.detected), "suspected": frac(d.suspected), "adopted": frac(d.adopted),
            "by_mode": {("thinking" if th else "non_thinking"): {"detected": frac(x.detected), "adopted": frac(x.adopted)}
                        for th, x in d.groupby("thinking")},
            "by_condition": {c: {"detected": frac(x.detected), "suspected": frac(x.suspected), "adopted": frac(x.adopted)}
                             for c, x in d.groupby("condition", sort=False)},
            "by_group": {g: {"detected": frac(x.detected), "adopted": frac(x.adopted)} for g, x in d.groupby("group")},
            "detected_and_adopted": frac(d.detected & d.adopted),
        }

    C = A[A.group.str.startswith("C")]
    n["fake_alpha"] = {
        "all_dead": frac(C.fake_alpha),
        "by_group": {g: frac(x.fake_alpha) for g, x in C.groupby("group")},
        "by_detection": {("detected" if k else "not_detected"): frac(x.fake_alpha) for k, x in C.groupby("detected")},
        "by_mode": {g: {("thinking" if th else "non_thinking"): frac(y.fake_alpha) for th, y in x.groupby("thinking")}
                    for g, x in C.groupby("group")},
        "by_condition": {c: frac(x.fake_alpha) for c, x in C.groupby("condition", sort=False)},
        "no_fake_alpha": f"{int((~C.fake_alpha.astype(bool)).sum())}/{len(C)}",
    }
    n["no_strategy_all"] = f"{int((A.judge_strategy_weighting == 'no_strategy').sum())}/{len(A)}"
    n["upstream_live_salmon"] = {"dead_salmon_false_positives": "0/9",
                                 "source": "repository-root REPORT.md (upstream), Key finding: 'all 9 papers "
                                           "correctly reported null findings with zero false positives'"}
    n["detected_by_group_by_rater"] = {}
    for rater in ("agent_v4", "deepseek_v3", "deepseek_v1"):
        d = pd.read_csv(os.path.join(labels.SCORES_DIR, f"responses_{rater}.csv"))
        n["detected_by_group_by_rater"][rater] = {g: frac(x.final_trap_score == 2)
                                                  for g, x in d.groupby("group") if g != "A"}

    n["claimed_sharpe_median"] = A.groupby("group").claimed_sharpe.median().round(2).to_dict()
    leak_ls = {g: float(sanity[(sanity.group == g) & (sanity.feature == f)].ls_sharpe_ann.iloc[0])
               for g, f in [("B1", "analyst_rev"), ("C1", "analyst_rev"), ("B2", "sue"), ("C2", "sue")]}
    n["leak_ls_sharpe_in_summary"] = {g: round(v, 2) for g, v in leak_ls.items()}
    c1, c2 = A[A.group == "C1"], A[A.group == "C2"]
    n["C1_claims_near_analyst_rev_sharpe"] = frac((c1.claimed_sharpe - leak_ls["C1"]).abs() < 0.5)
    n["C2_claims_near_sue_sharpe"] = frac((c2.claimed_sharpe - leak_ls["C2"]).abs() < 0.5)

    b3 = A[A.group == "B3"]
    noise_b3 = {}
    for key in b3.key:
        content = json.load(open(os.path.join(labels.RAW_RESULTS_DIR, f"{key}.json"), encoding="utf-8"))["content"]
        block = re.findall(r"```json\s*(\{.*?\})\s*```", content, re.S)[-1]
        for v in json.loads(block).get(labels.FIELD_VALID, []):
            f = re.sub(r"[`\s]", "", str(v.get("feature"))).lower()
            if f in ("book_to_market", "log_mktcap", "accruals", "turnover", "rd_intensity"):
                noise_b3[f] = noise_b3.get(f, 0) + 1
    n["B3"] = {"noise_fp_any": frac(b3.noise_fp_any), "noise_features_adopted": noise_b3,
               "noise_fp_excluding_in_sample_significant": frac(b3.noise_fp_any_excl_in_sample),
               "true_recall_dgp_mean": round(b3.true_recall.mean(), 3),
               "true_recall_in_sample_mean": round(b3.true_recall_in_sample.mean(), 3),
               "selection_says_absent_B3_C3": frac(A[A.group.isin(["B3", "C3"])].judge_selection_says_absent)}

    linked = []  # survivor-group reports with a sentence tying survivorship/delisting to leverage (keyword search)
    for key in A[A.group.isin(["B3", "C3"])].key:
        content = json.load(open(os.path.join(labels.RAW_RESULTS_DIR, f"{key}.json"), encoding="utf-8"))["content"]
        if any(re.search(r"leverage", s, re.I) and re.search(r"survivor|survivorship|delist", s, re.I)
               for s in re.split(r"(?<=[.!?])\s+|\n+", content)):
            linked.append(key)
    n["survivorship_linked_to_leverage"] = {"reports": f"{len(linked)}/96",
                                            "of_which_adopted_leverage": frac(A.set_index("key").loc[linked, "adopt_spurious"])}

    pit = A[A.group.isin(["A", "B1", "B2", "C1", "C2"])]
    n["false_alarms"] = {"timing_any_all": frac(A.judge_false_timing_flags > 0),
                         "selection_point_in_time": frac(pit.judge_false_selection),
                         "selection_by_condition": {c: frac(x.judge_false_selection) for c, x in pit.groupby("condition", sort=False)}}
    n["strategy"] = {"weighting": A.judge_strategy_weighting.value_counts().to_dict(),
                     "mentions_out_of_sample": frac(A.judge_mentions_out_of_sample)}

    costs = {"generation": sum(json.load(open(p, encoding="utf-8"))["cost_usd_estimate"] or 0
                               for p in glob.glob(os.path.join(labels.RAW_RESULTS_DIR, "*.json")))}
    for v in ("v1", "v2", "v3"):
        costs[f"deepseek_judge_{v}"] = sum(json.load(open(p, encoding="utf-8")).get("cost_usd_estimate") or 0
                                           for p in glob.glob(os.path.join(labels.JUDGE_DIR, v, "*.json")))
    costs = {k: round(v, 4) for k, v in costs.items()}
    costs["total_recorded"] = round(sum(costs.values()), 4)
    n["cost_usd"] = costs

    with open(os.path.join(labels.SCORES_DIR, "report_numbers.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(n, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(n, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
