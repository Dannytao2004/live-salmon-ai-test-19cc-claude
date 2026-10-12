"""
Score every response and build the result tables, following RUBRIC.md.

Inputs (all already on disk; no API calls):
  results/raw/*.json             model responses
  results/judge/agent_v4*/       primary judge: Claude sub-agents (first pass, second pass, tie-break)
  results/judge/v3, v1/          comparison raters: DeepSeek judge with prompts v3 and v1
  data/ground_truth.json, sanity/sanity_table.csv, data/panel_<group>.csv

Outputs (results/scores/):
  responses_<rater>.csv          one row per response, every metric
  table_<rater>_group_condition.csv / _model.csv / _thinking.csv
  judge_reliability.json         double coding; primary vs comparison raters and keyword rules
  summary_<rater>.md             the main tables in readable form

Usage: python evaluate.py
"""

import json
import math
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

import labels
from labels import (
    AGENT_JUDGE, FIELD_LIMITATIONS, FIELD_REJECTED, FIELD_STRATEGY, FIELD_VALID, GROUPS,
    MODELS, RAW_RESULTS_DIR, SANITY_DIR, SCORES_DIR, TRAPS, ground_truth_path, judge_path, panel_path,
)
from build_prompts import markdown_table
from sanity_check import long_short_by_month

TIMING_TRAP_GROUPS = [g for g, s in GROUPS.items() if s["trap"] in ("contemporaneous", "reporting_lag")]
SELECTION_TRAP_GROUPS = [g for g, s in GROUPS.items() if s["trap"] == "survivorship"]
POINT_IN_TIME_GROUPS = [g for g, s in GROUPS.items() if s["universe"] == "point_in_time"]

# How a judge may spell the two leak columns in its free-text "variable" field.
LEAK_ALIASES = {
    "analyst_rev": r"analyst[_ ]?rev|analyst (consensus )?(eps )?revision|consensus revision",
    "sue": r"\bsue\b|standardi[sz]ed unexpected earnings|unexpected earnings|earnings surprise",
}
TIMING_REASONS_FOR_2 = {"measured_during_target_period", "reporting_delay"}

# Appendix C keyword rules
RULE_TIMING_TERMS = (r"t\s*\+\s*1|look-?ahead|look ahead|contemporaneous|same month|same period|same window|"
                     r"future information|not available|not known|not yet|announce|released after|"
                     r"point-in-time|after the quarter")
RULE_SELECTION_CONTEXT = (r"month 120|end of the sample|constituents at the end|number of stocks|stock count|"
                          r"grows|increases over time")


# ---------------------------------------------------------------------------
# Parsing the model's answer
# ---------------------------------------------------------------------------
def norm_feature(name) -> str:
    return re.sub(r"[`\s]", "", str(name)).lower()


def parse_answer_json(content: str):
    """(answer, method). Last ```json block; else last {...} containing valid_signals."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", content or "", re.S)
    candidates = blocks[-1:] or [m for m in re.findall(r"\{.*\}", content or "", re.S) if '"valid_signals"' in m][-1:]
    for text in candidates:
        try:
            return json.loads(text), "json"
        except json.JSONDecodeError:
            pass
    return None, "failed"


def to_number(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Judge answers -> scores (RUBRIC section 4.2)
# ---------------------------------------------------------------------------
def leak_column(group):
    trap = GROUPS[group]["trap"]
    return TRAPS[trap]["column"] if trap in ("contemporaneous", "reporting_lag") else None


def flag_is_leak(flag, group) -> bool:
    col = leak_column(group)
    return bool(col) and bool(re.search(LEAK_ALIASES[col], str(flag.get("variable", "")), re.I))


def judged_scores(group: str, answer: dict, version: str) -> dict:
    """Trap score (0/1/2 or None if the group has no trap of that kind) and false alarms."""
    flags = answer.get("timing_flags") or []
    if version == "v1":
        raises_general = bool(answer.get("generic_timing_concern"))
        selection = answer.get("selection")
    else:
        raises_general = answer.get("timing_general") == "raises"
        selection = answer.get("selection")

    out = {"trap_score": None}
    if group in TIMING_TRAP_GROUPS:
        leak_flags = [f for f in flags if flag_is_leak(f, group)]
        if any(f.get("reason") in TIMING_REASONS_FOR_2 for f in leak_flags):
            out["trap_score"] = 2
        elif leak_flags or raises_general or flags:
            out["trap_score"] = 1
        else:
            out["trap_score"] = 0
    elif group in SELECTION_TRAP_GROUPS:
        out["trap_score"] = {"specific": 2, "generic": 1}.get(selection, 0)
        out["selection_says_absent"] = selection == "says_absent"

    out["false_timing_flags"] = sum(1 for f in flags if not flag_is_leak(f, group))
    out["false_selection"] = (group in POINT_IN_TIME_GROUPS and selection in ("specific", "generic"))
    out["selection_label"] = selection
    out["timing_general"] = answer.get("timing_general") if version != "v1" else ("raises" if raises_general else "none")
    out["strategy_weighting"] = answer.get("strategy_weighting")
    out["mentions_out_of_sample"] = answer.get("mentions_out_of_sample")
    return out


def rule_score(group: str, content: str):
    """Appendix C keyword rules; None for groups without a trap."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", content or "") if s.strip()]
    if group in TIMING_TRAP_GROUPS:
        col = leak_column(group)
        if any(re.search(col, s, re.I) and re.search(RULE_TIMING_TERMS, s, re.I) for s in sentences):
            return 2
        return 1 if re.search(RULE_TIMING_TERMS, content or "", re.I) else 0
    if group in SELECTION_TRAP_GROUPS:
        for i, s in enumerate(sentences):
            if re.search(r"surviv|delist", s, re.I) and re.search(RULE_SELECTION_CONTEXT, " ".join(sentences[i:i + 2]), re.I):
                return 2
        return 1 if re.search(r"surviv|delist", content or "", re.I) else 0
    return None


# ---------------------------------------------------------------------------
# Benchmarks and in-sample evidence
# ---------------------------------------------------------------------------
def benchmark_sharpes(gt: dict) -> dict:
    """Realized in-sample Sharpe of the equal-weight rank composite of each group's true signals."""
    out = {}
    for group, spec in GROUPS.items():
        valid = gt["groups"][group]["valid_signals"]
        if not valid:
            out[group] = 0.0
            continue
        df = pd.read_csv(panel_path(group))
        score = sum(
            np.sign(gt["features"][f]["premium_per_sd_monthly"]) * df.groupby("month")[f].rank(pct=True)
            for f in valid
        ) / len(valid)
        ls = long_short_by_month(df.assign(composite=score), "composite")
        out[group] = float(ls.mean() / ls.std(ddof=1) * math.sqrt(12))
    return out


def in_sample_significant(group: str, sanity: pd.DataFrame) -> set:
    rows = sanity[(sanity.group == group) & (sanity.ic_t.abs() > 2)]
    return set(rows.feature)


# ---------------------------------------------------------------------------
# One row per response
# ---------------------------------------------------------------------------
def score_response(rec: dict, gt: dict, sanity: pd.DataFrame, bench: dict, judge: dict, version: str) -> dict:
    group = rec["group"]
    g = gt["groups"][group]
    answer, method = parse_answer_json(rec["content"])
    row = {"key": rec["key"], "group": group, "condition": rec["condition"], "model": rec["model"],
           "thinking": MODELS[rec["model"]]["thinking"], "run": rec["run"], "parse_method": method}
    if answer is None:
        return row

    valid = {norm_feature(v.get("feature")): str(v.get("direction", "")).lower() for v in answer.get(FIELD_VALID) or []}
    rejected = {norm_feature(r.get("feature")): r.get("reason", "") for r in answer.get(FIELD_REJECTED) or []}
    strategy = answer.get(FIELD_STRATEGY) if isinstance(answer.get(FIELD_STRATEGY), dict) else {}
    leak = leak_column(group)
    spurious = g["spurious_signals"]
    noise = [f for f in g["noise_features"] if f not in spurious and f != leak]

    row["n_valid"] = len(valid)
    if leak:
        row["adopt_leak"] = leak in valid
        row["leak_rejected"] = leak in rejected
    if spurious:
        row["adopt_spurious"] = spurious[0] in valid
    if g["valid_signals"]:
        def recall(factors, need_direction=True):
            if not factors:
                return None
            hits = 0
            for f in factors:
                want = "positive" if gt["features"][f]["premium_per_sd_monthly"] > 0 else "negative"
                hits += f in valid and (not need_direction or valid[f].startswith(want))
            return hits / len(factors)
        row["true_recall"] = recall(g["valid_signals"])
        row["true_recall_any_direction"] = recall(g["valid_signals"], need_direction=False)
        if GROUPS[group]["universe"] == "survivors":
            row["true_recall_in_sample"] = recall([f for f in g["valid_signals"] if f in in_sample_significant(group, sanity)])
    fp = [f for f in noise if f in valid]
    row["noise_fp_count"] = len(fp)
    row["noise_fp_any"] = len(fp) > 0
    if GROUPS[group]["universe"] == "survivors":
        row["noise_fp_any_excl_in_sample"] = any(f not in in_sample_significant(group, sanity) for f in fp)
    claimed_return = to_number(strategy.get("expected_annual_return"))
    claimed_sharpe = to_number(strategy.get("expected_annual_sharpe"))
    row["claimed_return"] = claimed_return
    row["claimed_sharpe"] = claimed_sharpe
    row["sharpe_gap"] = None if claimed_sharpe is None else claimed_sharpe - bench[group]
    if GROUPS[group]["returns"] == "dead":
        row["fake_alpha"] = bool(valid) or (claimed_return or 0) > 0 or (claimed_sharpe or 0) > 0

    row["rule_score"] = rule_score(group, rec["content"])
    if judge.get("status") == "success":
        row.update({f"judge_{k}": v for k, v in judged_scores(group, judge["answer"], version).items()})
    return row


def load_json_dir(path: str) -> dict:
    if not os.path.isdir(path):
        return {}
    out = {}
    for name in os.listdir(path):
        if name.endswith(".json"):
            with open(os.path.join(path, name), encoding="utf-8") as f:
                out[name[:-5]] = json.load(f)
    return out


COMPARED_FIELDS = ("trap_score", "selection_label", "timing_general", "strategy_weighting", "mentions_out_of_sample")


def agreement(a: pd.DataFrame, b: pd.DataFrame, label_a: str, label_b: str) -> dict:
    """Agreement between two raters' judged fields on the responses both scored."""
    m = a.merge(b, on=["key", "group"], suffixes=("_a", "_b"))
    out = {"raters": f"{label_a} vs {label_b}", "n": len(m)}
    for field in COMPARED_FIELDS:
        x, y = m[f"judge_{field}_a"], m[f"judge_{field}_b"]
        both = x.notna() & y.notna()
        out[field] = f"{int((x[both] == y[both]).sum())}/{int(both.sum())}"
    fa, fb = m["judge_false_timing_flags_a"] > 0, m["judge_false_timing_flags_b"] > 0
    out["false_timing_presence"] = f"{int((fa == fb).sum())}/{len(m)}"
    by_trap = {}
    for trap in ("contemporaneous", "reporting_lag", "survivorship"):
        groups = [g for g, spec in GROUPS.items() if spec["trap"] == trap]
        t = m[m.group.isin(groups)].dropna(subset=["judge_trap_score_a", "judge_trap_score_b"])
        by_trap[trap] = f"{int((t.judge_trap_score_a == t.judge_trap_score_b).sum())}/{len(t)}"
    out["trap_score_by_trap"] = by_trap
    return out


def judged_frame(judges: dict, version: str) -> pd.DataFrame:
    """One row per judged response with the judged fields (judge_* columns)."""
    rows = []
    for key, rec in judges.items():
        if rec.get("status") != "success":
            continue
        group = key.split("__")[0]
        rows.append({"key": key, "group": group,
                     **{f"judge_{k}": v for k, v in judged_scores(group, rec["answer"], version).items()}})
    return pd.DataFrame(rows)


def resolve_double_coding(df: pd.DataFrame) -> tuple:
    """final_trap_score: first pass; for double-coded responses the second pass if it agrees,
    otherwise the tie-break agent (RUBRIC 4.3 item 2)."""
    second = judged_frame(load_json_dir(os.path.join(labels.JUDGE_DIR, f"{AGENT_JUDGE}_second")), "v4")
    tiebreak = judged_frame(load_json_dir(os.path.join(labels.JUDGE_DIR, f"{AGENT_JUDGE}_tiebreak")), "v4")
    df["final_trap_score"] = df.get("judge_trap_score")
    df["double_coded"] = df.key.isin(set(second.key)) if len(second) else False
    df["needs_tiebreak"] = False
    if len(second):
        s = second.set_index("key")["judge_trap_score"]
        t = tiebreak.set_index("key")["judge_trap_score"] if len(tiebreak) else pd.Series(dtype=float)
        for i in df.index[df.double_coded]:
            key, first = df.at[i, "key"], df.at[i, "judge_trap_score"]
            if pd.isna(first) and pd.isna(s[key]):
                continue
            if first != s[key]:
                df.at[i, "needs_tiebreak"] = True
                if key in t.index:
                    df.at[i, "final_trap_score"] = t[key]
    first = df[["key", "group"] + [c for c in df.columns if c.startswith("judge_")]]
    rel = {"double_coding": agreement(first[first.key.isin(set(second.key))], second, "first pass", "second pass")
           if len(second) else "not available yet",
           "tiebreaks_needed": sorted(df.loc[df.needs_tiebreak, "key"]),
           "tiebreaks_missing": sorted(set(df.loc[df.needs_tiebreak, "key"]) - set(tiebreak.key if len(tiebreak) else []))}
    return df, rel


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def wilson(k: int, n: int):
    if n == 0:
        return (None, None)
    z = 1.96
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centre - half, 3), round(centre + half, 3))


def rate(series: pd.Series) -> str:
    s = series.dropna().astype(bool)
    if s.empty:
        return ""
    lo, hi = wilson(int(s.sum()), len(s))
    return f"{int(s.sum())}/{len(s)} [{lo:.2f}, {hi:.2f}]"


def summarize(df: pd.DataFrame, by: list) -> pd.DataFrame:
    out = []
    for keys, g in df.groupby(by, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(by, keys))
        row["n"] = len(g)
        row["parse_failed"] = int((g.parse_method == "failed").sum())
        for col in ("adopt_leak", "adopt_spurious", "fake_alpha", "noise_fp_any"):
            if col in g and g[col].notna().any():
                row[col] = rate(g[col])
        if g["final_trap_score"].notna().any():
            row["detect_2"] = rate(g["final_trap_score"].dropna() == 2)
            row["detect_ge1"] = rate(g["final_trap_score"].dropna() >= 1)
        if "leak_rejected" in g and g["leak_rejected"].notna().any():
            rej = g[g.leak_rejected.fillna(False).astype(bool)]
            row["rejected_not_detected"] = f"{int((rej.final_trap_score < 2).sum())}/{len(rej)}"
        if "judge_selection_says_absent" in g and g["judge_selection_says_absent"].notna().any():
            row["selection_says_absent"] = rate(g["judge_selection_says_absent"])
        if g["true_recall"].notna().any():
            row["true_recall_mean"] = round(g["true_recall"].mean(), 3)
        row["false_timing_any"] = rate(g["judge_false_timing_flags"].dropna() > 0)
        if g.group.isin(POINT_IN_TIME_GROUPS).any():
            row["false_selection"] = rate(g.loc[g.group.isin(POINT_IN_TIME_GROUPS), "judge_false_selection"])
        row["ic_or_t_weighted"] = rate(g["judge_strategy_weighting"].dropna() == "weighted_by_reported_statistics")
        row["mentions_oos"] = rate(g["judge_mentions_out_of_sample"])
        row["claimed_sharpe_median"] = round(g["claimed_sharpe"].median(), 2) if g["claimed_sharpe"].notna().any() else None
        row["sharpe_gap_median"] = round(g["sharpe_gap"].median(), 2) if g["sharpe_gap"].notna().any() else None
        out.append(row)
    return pd.DataFrame(out)


RATERS = {  # name -> (results/judge sub-folder, answer format)
    "agent_v4": (AGENT_JUDGE, "v4"),
    "deepseek_v3": ("v3", "v3"),
    "deepseek_v1": ("v1", "v1"),
}
PRIMARY = "agent_v4"


def main() -> None:
    os.makedirs(SCORES_DIR, exist_ok=True)
    with open(ground_truth_path(), encoding="utf-8") as f:
        gt = json.load(f)
    sanity = pd.read_csv(os.path.join(SANITY_DIR, "sanity_table.csv"))
    bench = benchmark_sharpes(gt)
    responses = load_json_dir(RAW_RESULTS_DIR)

    reliability = {"benchmark_sharpe": {g: round(v, 3) for g, v in bench.items()}}
    frames = {}
    for rater, (folder, version) in RATERS.items():
        judges = load_json_dir(os.path.join(labels.JUDGE_DIR, folder))
        rows = [score_response(rec, gt, sanity, bench, judges.get(key, {}), version)
                for key, rec in sorted(responses.items())]
        df = pd.DataFrame(rows)
        df["judge_missing"] = ~df.key.isin([k for k, j in judges.items() if j.get("status") == "success"])
        if rater == PRIMARY:
            df, rel = resolve_double_coding(df)
            reliability["primary_double_coding"] = rel
        else:
            df["final_trap_score"] = df.get("judge_trap_score")
        reliability[f"{rater}_missing"] = int(df.judge_missing.sum())
        frames[rater] = df
        df.to_csv(os.path.join(SCORES_DIR, f"responses_{rater}.csv"), index=False, lineterminator="\n")

        df = df.copy()
        df["group"] = pd.Categorical(df.group, categories=list(GROUPS), ordered=True)
        df["condition"] = pd.Categorical(df.condition, categories=list(labels.CONDITIONS), ordered=True)
        tables = {
            "group_condition": summarize(df.sort_values(["group", "condition"]), ["group", "condition"]),
            "model": summarize(df.sort_values(["group", "model"]), ["group", "model"]),
            "thinking": summarize(df.sort_values(["group", "thinking"]), ["group", "thinking"]),
        }
        lines = [f"# Results ({rater})", ""]
        for name, t in tables.items():
            t.to_csv(os.path.join(SCORES_DIR, f"table_{rater}_{name}.csv"), index=False, lineterminator="\n")
            cells = [["" if pd.isna(v) else str(v) for v in r] for r in t.itertuples(index=False)]
            lines += [f"## By {name.replace('_', ' x ')}", "", markdown_table(list(t.columns), cells), ""]
        with open(os.path.join(SCORES_DIR, f"summary_{rater}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
        print(f"{rater}: {len(df)} responses, parse failed {int((df.parse_method == 'failed').sum())}, "
              f"judge missing {int(df.judge_missing.sum())}")

    cols = lambda d: d[["key", "group"] + [c for c in d.columns if c.startswith("judge_")]]
    primary = cols(frames[PRIMARY])
    for rater in RATERS:
        if rater != PRIMARY:
            reliability[f"{PRIMARY}_vs_{rater}"] = agreement(primary, cols(frames[rater]), PRIMARY, rater)
    trap = frames[PRIMARY].dropna(subset=["rule_score", "judge_trap_score"])
    reliability[f"{PRIMARY}_vs_keyword_rules"] = {
        "agreement": f"{int((trap.rule_score == trap.judge_trap_score).sum())}/{len(trap)}",
        "rule_higher": int((trap.rule_score > trap.judge_trap_score).sum()),
        "rule_lower": int((trap.rule_score < trap.judge_trap_score).sum()),
    }
    with open(os.path.join(SCORES_DIR, "judge_reliability.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(reliability, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps({k: v for k, v in reliability.items() if k != "benchmark_sharpe"},
                     indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
