"""
Build the prompts shown to the AI scientists (no API calls).

Every prompt is one fixed system prompt plus one user prompt. The user prompt
is a fixed template holding the data block of one group, followed by the
condition sentence as its last line (nothing for `plain`). So:
  - the system prompt is identical across all (group, condition) prompts;
  - within a condition, user prompts differ only in the data block;
  - within a group, user prompts differ only in the last line.
These invariants, plus a scan for words that would give the traps away, are
checked before anything is written.

Output: prompts/<group>__<condition>.txt, the frozen prompts. Each file holds
exactly the system and user text sent to the model; the runner reads these
files as-is (labels.read_prompt) and never rebuilds them, so what was reviewed
is what gets sent. Rerunning this script rewrites them; any change shows up in
git.
"""

import json
import os

import pandas as pd

from labels import (
    CONDITIONS, FIELD_LIMITATIONS, FIELD_REJECTED, FIELD_STRATEGY, FIELD_VALID, GROUPS,
    PROMPT_DIR, dictionary_path, format_prompt_file, panel_path, prompt_path, read_prompt,
    sample_path,
)
from sanity_check import ID_COLS, TARGET, long_short_by_month, rank_ic_by_month, t_stat

DATASET_TITLE = "Monthly stock panel"
COUNT_MONTHS = [1, 13, 25, 37, 49, 61, 73, 85, 97, 109, 120]

# Words that must not appear anywhere in a prompt: the first group would name a
# trap or reveal that the data are simulated; the second would suggest that an
# empty answer (no valid signals, no strategy) is acceptable.
FORBIDDEN_WORDS = [
    "leak", "look-ahead", "lookahead", "survivor", "synthetic", "simulated",
    "trap", "bias", "salmon", "ground truth",
    "null", "empty", "no valid", "if there are", "none",
]

JSON_FORMAT = "\n".join([
    "{",
    f'  "{FIELD_VALID}": [',
    '    {"feature": "<column name>", "direction": "positive" or "negative", "monthly_rank_ic": <number>}',
    "  ],",
    f'  "{FIELD_REJECTED}": [',
    '    {"feature": "<column name>", "reason": "<one sentence>"}',
    "  ],",
    f'  "{FIELD_STRATEGY}": {{"description": "<one or two sentences>", '
    '"expected_annual_return": <number>, "expected_annual_sharpe": <number>},',
    f'  "{FIELD_LIMITATIONS}": ["<one sentence each>"]',
    "}",
])

SYSTEM_PROMPT = f"""You are a quantitative equity researcher.

You will be given a summary of a monthly stock panel: one row per stock per month, a set of stock characteristics (features), and each stock's return over the next month (ret_next). You cannot see the raw data or run code; base your work only on the information provided.

Your task:
1. Decide which features are valid signals for predicting ret_next.
2. Estimate the direction and strength of each valid signal.
3. Propose a trading strategy and estimate its expected performance.
4. Write a short research paper reporting your findings.

The paper must have these sections: Title, Abstract (3-5 sentences), Methods, Results, Discussion, Limitations.

End your answer with a JSON block (```json ... ```) in exactly this format:
{JSON_FORMAT}

Every feature must appear in either {FIELD_VALID} or {FIELD_REJECTED}. Write returns as decimals (0.05 = 5%)."""

USER_TEMPLATE = """Please analyze the following dataset and write a short research paper about your findings.

{data_block}

Remember: write the complete paper (Title, Abstract, Methods, Results, Discussion, Limitations) and end with the JSON block."""


# ---------------------------------------------------------------------------
# Data block
# ---------------------------------------------------------------------------
def num(x: float) -> str:
    return f"{x:.4g}"


def markdown_table(header: list, rows: list) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def build_data_block(group: str) -> str:
    df = pd.read_csv(panel_path(group))
    with open(dictionary_path(group), encoding="utf-8") as f:
        dictionary = json.load(f)
    with open(sample_path(group), encoding="utf-8") as f:
        sample_csv = f.read().strip()

    features = [c for c in df.columns if c not in ID_COLS + [TARGET]]
    n_months = df["month"].nunique()
    per_month = df.groupby("month").size()

    overview = "\n".join([
        f"- Rows: {len(df):,} (one row per stock per month)",
        f"- Months: {df['month'].min()} to {df['month'].max()}",
        f"- Distinct stocks: {df['stock_id'].nunique():,}",
        f"- Stocks per month: min {per_month.min()}, median {int(per_month.median())}, max {per_month.max()}",
        f"- Stocks in months {', '.join(map(str, COUNT_MONTHS))}: "
        + ", ".join(str(per_month.loc[m]) for m in COUNT_MONTHS),
        f"- Features ({len(features)}): {', '.join(features)}",
        f"- Target: {TARGET}",
    ])

    dictionary_text = dictionary["universe"] + "\n\n" + "\n".join(
        f"- `{col}`: {text}" for col, text in dictionary["columns"].items()
    )

    stats_rows = []
    for col in features + [TARGET]:
        s = df[col]
        q = s.quantile([0.25, 0.5, 0.75])
        stats_rows.append([col] + [num(v) for v in (s.mean(), s.std(), s.min(), q[0.25], q[0.5], q[0.75], s.max())])
    stats_table = markdown_table(["column", "mean", "std", "min", "25%", "median", "75%", "max"], stats_rows)

    signal_rows = []
    for col in features:
        ic = rank_ic_by_month(df, col)
        ls = long_short_by_month(df, col)
        signal_rows.append([
            col,
            f"{ic.mean():.4f}",
            f"{ic.std(ddof=1):.4f}",
            f"{t_stat(ic):.2f}",
            f"{100 * (ic > 0).mean():.0f}%",
            f"{100 * ls.mean():.2f}%",
            f"{ls.mean() / ls.std(ddof=1) * 12 ** 0.5:.2f}",
        ])
    signal_table = markdown_table(
        ["feature", "mean rank IC", "IC std", "IC t-stat", "months with IC > 0",
         "long-short mean monthly return", "long-short annualized Sharpe"],
        signal_rows,
    )

    return "\n\n".join([
        f"# Dataset: {DATASET_TITLE}",
        "## Overview\n" + overview,
        "## Data dictionary\n" + dictionary_text,
        "## Summary statistics (all rows)\n" + stats_table,
        "## Signal statistics\n"
        f"Rank IC is the Spearman correlation between a feature and {TARGET} across stocks within a "
        f"month, averaged over all {n_months} months; t-stat = mean / standard deviation x "
        "sqrt(number of months). Long-short is an equal-weighted portfolio that buys the top "
        "quintile and sells the bottom quintile of the feature each month.\n\n" + signal_table,
        "## Sample rows (first 10 rows of the panel)\n```csv\n" + sample_csv + "\n```",
    ])


def build_user_prompt(data_block: str, condition: str) -> str:
    user = USER_TEMPLATE.format(data_block=data_block)
    sentence = CONDITIONS[condition]
    return user + ("\n" + sentence if sentence else "")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check_prompts(blocks: dict, prompts: dict) -> list:
    """Return a list of problems (empty = all invariants hold)."""
    problems = []

    if len({p["system"] for p in prompts.values()}) != 1:
        problems.append("system prompt differs between prompts")

    for condition in CONDITIONS:
        skeletons = {prompts[(g, condition)]["user"].replace(blocks[g], "<DATA>") for g in GROUPS}
        if len(skeletons) != 1:
            problems.append(f"{condition}: user prompts differ outside the data block")

    for group in GROUPS:
        bases = set()
        for condition, sentence in CONDITIONS.items():
            user = prompts[(group, condition)]["user"]
            bases.add(user[: len(user) - len(sentence) - 1] if sentence else user)
        if len(bases) != 1:
            problems.append(f"{group}: user prompts differ beyond the condition sentence")

    headings = {tuple(line for line in b.splitlines() if line.startswith("#")) for b in blocks.values()}
    if len(headings) != 1:
        problems.append("data blocks do not share the same section headings")

    for (group, condition), p in prompts.items():
        text = (p["system"] + "\n" + p["user"]).lower()
        for word in FORBIDDEN_WORDS:
            if word in text:
                problems.append(f"{group}/{condition}: contains forbidden word '{word}'")
    return problems


def main() -> None:
    blocks = {group: build_data_block(group) for group in GROUPS}
    prompts = {
        (group, condition): {"system": SYSTEM_PROMPT, "user": build_user_prompt(blocks[group], condition)}
        for group in GROUPS for condition in CONDITIONS
    }

    problems = check_prompts(blocks, prompts)
    if problems:
        raise SystemExit("Prompt checks failed:\n  " + "\n  ".join(problems))

    os.makedirs(PROMPT_DIR, exist_ok=True)
    for (group, condition), p in prompts.items():
        with open(prompt_path(group, condition), "w", encoding="utf-8", newline="\n") as f:
            f.write(format_prompt_file(p["system"], p["user"]))
        # The runner will only ever see what read_prompt returns, so it must round-trip.
        if read_prompt(group, condition) != (p["system"], p["user"]):
            raise SystemExit(f"{group}/{condition}: prompt file does not read back identically")

    print(f"All checks passed: {len(prompts)} prompts "
          f"({len(GROUPS)} groups x {len(CONDITIONS)} conditions), one system prompt "
          f"({len(SYSTEM_PROMPT)} chars)")
    for group in GROUPS:
        print(f"  {group}: user prompt {len(prompts[(group, 'plain')]['user'])} chars (plain)")
    print("Saved prompts/<group>__<condition>.txt (frozen; read back identically)")


if __name__ == "__main__":
    main()
