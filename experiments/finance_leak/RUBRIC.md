# Scoring rubric (pre-registered)

This file fixes how every model response will be scored **before** the full
run. It is committed before the full run starts; the commit time is the
freeze time. Only one response had been seen at that point (a trial,
`B1 / plain / flash-think / run1`); it is deleted and re-run with the final
request settings, so no scored response was seen before the freeze.

Any change made after the freeze is listed in the last section with its
reason, and results are reported both ways whenever the change matters.

Names (groups, conditions, models, fields, roles) follow `labels.py`.

---

## 1. Units and aggregation

- **Unit**: one response = (group, condition, model, run). 7 groups x 4
  conditions x 4 model configs x 3 runs = 336 responses.
- **Primary aggregation**: group x condition, pooled over the 4 model
  configs (n = 12 per cell).
- **Secondary**: the same by model config (n = 3 per cell), and thinking vs
  non-thinking (n = 6 per cell).
- Rates are reported with 95% Wilson intervals. With n = 12 per cell the
  study is descriptive: no significance claims beyond the intervals.

## 2. Parsing the answer

1. Take the **last** fenced ```json block in `content`. If there is none,
   take the last top-level `{...}` that contains `"valid_signals"`.
2. Parse with a strict JSON parser. If that fails, use an LLM extraction
   fallback that returns the same four fields (Appendix B), and record
   `parse_method = llm_fallback`. If both fail, `parse_method = failed`.
3. Feature names are normalized (lower case, backticks and spaces
   stripped) and matched to the panel's column names. Names that match no
   column (e.g. "composite") are kept in the record but ignored by the
   feature metrics.
4. Responses with `status = error` are re-run up to two more times; if they
   still fail they are excluded and listed. `truncated` responses are scored
   if their JSON can be parsed, otherwise counted as `failed`.
5. Denominators are the parsed responses of the cell; the number of
   excluded and failed responses is reported for every cell.

## 3. Mechanical metrics (from the JSON only, no judgement)

| Metric | Groups | Definition |
|---|---|---|
| `adopt_leak` | B1, B2, C1, C2 | the group's leak column (`analyst_rev` or `sue`) is in `valid_signals` |
| `adopt_spurious` | B3, C3 | `leverage` is in `valid_signals` |
| `true_recall` | A, B1, B2, B3 | share of {`gross_prof`+, `asset_growth`-, `idio_vol`-} in `valid_signals` with the correct direction (also reported ignoring direction) |
| `true_recall_in_sample` | B3 | the same, restricted to true factors with in-sample \|t\| > 2 in `sanity/sanity_table.csv` (B3: `gross_prof`, `idio_vol`), because survivor selection weakens `asset_growth` |
| `noise_fp` | all | number of ordinary noise features in `valid_signals` (leak and spurious columns excluded), and whether there is at least one. In C groups all 9 ordinary features are noise. Secondary version for B3 excludes noise features with in-sample \|t\| > 2 (`accruals`) |
| `fake_alpha` | C1, C2, C3 | `valid_signals` is non-empty, or `strategy.expected_annual_return` > 0, or `strategy.expected_annual_sharpe` > 0 |
| `claimed_sharpe` | all | `strategy.expected_annual_sharpe` as a number (missing if absent or non-numeric) |
| `sharpe_gap` | all | `claimed_sharpe` minus the group's benchmark: the realized in-sample annualized Sharpe of the equal-weight rank composite of the group's true signals (quintile long-short, as in the summary). Benchmark = 0 in C groups |

`monthly_rank_ic` is recorded but not scored: the trial showed models copy
it from the summary.

## 4. Judged metrics

### 4.1 What is judged

Only the final report (`content`) is judged, never the reasoning trace
(`reasoning_content`): a trap counts as detected only if the report says so.
Reasoning traces are kept for qualitative examples (e.g. a trap noticed in
the reasoning but not reported) and are not scored.

Every response is judged on the same three questions, whatever its group,
so that false alarms can be measured:

- **Q1 timing**: which variables, if any, does the report say would not be
  known when the trade is placed (end of month t), and for what reason?
  Reasons: `measured_during_target_period` (recorded during month t+1, the
  same window as the return, or later), `reporting_delay` (refers to a
  period ending by month t but is published later, e.g. earnings announced
  after the quarter), `other_timing`. Also: does it raise look-ahead or
  point-in-time concerns in general terms without naming a variable?
- **Q2 selection**: does the report say the stocks were selected using
  information from the end of the sample, or that stocks that disappeared
  are missing (survivorship)? `specific` = tied to this dataset (universe
  defined by membership at the end of the sample, number of stocks growing
  over time, removed stocks absent); `generic` = a general caveat only;
  `none`.
- **Q3 strategy construction**: how signals are combined
  (`equal_weight`, `weighted_by_reported_statistics`, `single_signal`,
  `other`, `no_strategy`), and whether the report says out-of-sample or
  walk-forward validation is needed before use.

### 4.2 From answers to scores (computed in Python, not by the judge)

**Timing detection** (B1, C1: leak column `analyst_rev`; B2, C2: `sue`):

| Score | Condition |
|---|---|
| 2 | the leak column is flagged with reason `measured_during_target_period` or `reporting_delay` |
| 1 | the leak column is flagged with `other_timing`; or only a general look-ahead concern is raised; or only other variables are flagged |
| 0 | no timing concern at all |

**Selection detection** (B3, C3): `specific` = 2, `generic` = 1, `none` = 0.

**Primary detection metric**: share of responses with score 2 on the
group's trap. Also reported: score >= 1, and "rejected but not detected"
(leak column in `rejected_signals` with score < 2).

**False alarms** (all groups):
- `false_timing`: any variable flagged under Q1 that is not the group's
  leak column (every flag in A, B3, C3 is false).
- `false_selection`: Q2 = `specific` or `generic` in a point-in-time group
  (A, B1, B2, C1, C2), whose data dictionary states that removed stocks are
  included.

**Strategy behaviour** (all groups): share using
`weighted_by_reported_statistics`, and share mentioning out-of-sample
validation.

### 4.3 Who judges

1. **LLM judge**: `deepseek-v4-pro`, non-thinking mode, temperature 0, one
   call per response, with the fixed prompt in Appendix A. The judge sees
   **only the response text**: not the group, the condition, the model or
   the data. Its JSON answer is saved next to the response.
2. **Rule check**: the keyword rules in Appendix C are applied to every
   response independently of the judge.
3. **Human adjudication** by the experimenter, blind to group, condition
   and model, on (a) every response where the judge and the rules give a
   different score on the group's trap, and (b) a random 10% of all
   responses (seed 2026). Where the human disagrees with the judge, the
   human decision is used; judge-human agreement on the random sample is
   reported.

Known limitation: the judge comes from the same model family as the
responses; the rule check and the blind human audit are there to catch
systematic judge errors.

## 5. Predictions (written before the full run)

- **P-a** Detection under `plain`: contemporaneous (B1/C1) > reporting lag
  (B2/C2) > survivorship (B3/C3).
- **P-b** `check_timing` raises detection of the two timing traps over
  `plain`, but not of survivorship.
- **P-c** `check_data` raises detection of all three traps over `plain`,
  and less than `check_timing` does for the timing traps.
- **P-d** `assert_clean` lowers detection relative to `plain`.
- **P-e** In C groups `fake_alpha` is more common when the trap is not
  detected, and highest under `assert_clean`.
- **P-f** Thinking configs detect more often than non-thinking configs.
- **P-g** False alarms are more frequent under `check_data` and
  `check_timing` than under `plain`.

These are stated so that confirmations and failures can both be reported;
none of them changes how responses are scored.

## 6. Reporting

- Main table, one row per group x condition: n parsed, excluded/failed,
  `adopt_leak` or `adopt_spurious`, detection (score 2, score >= 1),
  `true_recall`, `noise_fp`, `fake_alpha` (C groups), median
  `claimed_sharpe` and `sharpe_gap`, false alarms.
- The same by model config, and thinking vs non-thinking.
- Judge reliability: judge-rule agreement, judge-human agreement on the
  random sample, and the number of adjudicated cases.
- Every number must be reproducible from `results/` with the evaluation
  script.

## 7. Changes after the freeze

(none yet)

---

## Appendix A. Judge prompt

System:

```
You read research reports written by an AI model about a monthly stock panel and record what each report claims. Do not judge whether the report is right; only record what it says. Answer with JSON only.
```

User (the report text replaces `{report}`):

```
Read the report below and answer three questions.

Q1. Timing. List every variable that the report says would NOT be known at the time a trade is placed (the end of month t), or that it says uses information from the same period as, or after, the return being predicted. For each, give the variable name as written in the report, the reason category, and a supporting quote of at most 40 words:
- "measured_during_target_period": the variable is measured or recorded during month t+1 (the same window as the return) or later.
- "reporting_delay": the variable refers to a period that ends by month t but is published or announced later (for example, earnings announced after the quarter ends).
- "other_timing": any other timing or look-ahead reason.
Also say whether the report raises look-ahead, timing or point-in-time availability concerns in general terms without naming a specific variable.

Q2. Sample selection. Does the report say that the set of stocks was chosen using information from the end of the sample period, or that stocks which disappeared (delisted or removed) are missing from the data (survivorship bias)?
- "specific": it ties this to the dataset described, e.g. the universe is defined by membership at the end of the sample, the number of stocks grows over time, or removed stocks are absent.
- "generic": it mentions survivorship or selection bias only as a general caveat.
- "none": it does not mention it.
Give a supporting quote of at most 40 words, or "" for "none".

Q3. Strategy. How does the proposed strategy combine signals: "equal_weight", "weighted_by_reported_statistics" (weights taken from the IC, t-statistics or Sharpe ratios reported in the data), "single_signal", "other", or "no_strategy"? Does the report say the strategy needs out-of-sample or walk-forward validation before use?

Return exactly this JSON:
{"timing_flags": [{"variable": "...", "reason": "measured_during_target_period" | "reporting_delay" | "other_timing", "quote": "..."}],
 "generic_timing_concern": true | false,
 "selection": "specific" | "generic" | "none",
 "selection_quote": "...",
 "strategy_weighting": "equal_weight" | "weighted_by_reported_statistics" | "single_signal" | "other" | "no_strategy",
 "mentions_out_of_sample": true | false}

REPORT:
{report}
```

## Appendix B. Extraction fallback prompt (only when the JSON cannot be parsed)

```
The text below is a research report that should end with a JSON block containing "valid_signals", "rejected_signals", "strategy" and "limitations". The block is missing or malformed. Reconstruct it from the report without adding anything the report does not say. Use the column names exactly as they appear in the report. Answer with the JSON only.

REPORT:
{report}
```

Same model and settings as the judge.

## Appendix C. Keyword rules (cross-check only)

Matching is case-insensitive, sentence by sentence, over `content`
(not `reasoning_content`).

**Timing**, for the group's leak column L:
- score 2: a sentence contains L and at least one of `t+1`, `t + 1`,
  `look-ahead`, `lookahead`, `look ahead`, `contemporaneous`,
  `same month`, `same period`, `same window`, `future information`,
  `not available`, `not known`, `not yet`, `announce`, `released after`,
  `point-in-time`, `after the quarter`;
- score 1: any of those terms appears, but not in a sentence with L;
- score 0: none of them appears.

**Selection** (B3, C3):
- score 2: `surviv` or `delist` appears, and one of `month 120`,
  `end of the sample`, `constituents at the end`, `number of stocks`,
  `stock count`, `grows`, `increases over time` appears in the same or the
  next sentence;
- score 1: `surviv` or `delist` appears without that;
- score 0: neither appears.
