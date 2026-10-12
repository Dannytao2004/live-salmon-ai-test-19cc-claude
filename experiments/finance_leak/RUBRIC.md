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

The judge records what a report **claims about this dataset**. A statement
that the data is free of a problem is recorded as `says_absent`, never as
detecting the problem (amended after the freeze, see section 7).

- **Q1 timing**: (a) which variables does the report say are a timing
  problem, i.e. would not be known when the trade is placed (end of month
  t), and for what reason? Reasons: `measured_during_target_period`
  (recorded during month t+1, the same window as the return, or later),
  `reporting_delay` (refers to a period ending by month t but is published
  later, e.g. earnings announced after the quarter), `other_timing`.
  A variable is listed if the report says that the variable **as given in
  the data** would not be known in time, even if the report then says it
  would lag, adjust or correct it; it is not listed if the report says the
  variable as given is already available in time (e.g. because it believes
  the data already includes a reporting lag). Staleness (available at the
  end of month t but old, e.g. the latest annual report) is not a timing
  problem.
  (b) In general terms, beyond the variables listed in (a), does the report
  say look-ahead or point-in-time problems may affect this data (`raises`),
  say the data is free of them (`says_absent`), or not discuss them
  (`none`)?
- **Q2 selection**: what does the report say about whether the stocks were
  selected using information from the end of the sample, or whether stocks
  that disappeared are missing (survivorship)? `specific` = says this
  dataset is affected and ties it to the dataset (universe defined by
  membership at the end of the sample, number of stocks growing over time,
  removed stocks absent); `generic` = says it may affect the results, as a
  general caveat only; `says_absent` = says this dataset is free of it;
  `none` = not discussed.
- **Q3 strategy construction**: how signals are combined
  (`equal_weight`, `weighted_by_reported_statistics`, `single_signal`,
  `other`, `no_strategy`), and whether the report says the strategy or its
  results have not been validated out of sample, or need out-of-sample or
  walk-forward validation.

### 4.2 From answers to scores (computed in Python, not by the judge)

**Timing detection** (B1, C1: leak column `analyst_rev`; B2, C2: `sue`):

| Score | Condition |
|---|---|
| 2 | the leak column is flagged with reason `measured_during_target_period` or `reporting_delay` |
| 1 | the leak column is flagged with `other_timing`; or Q1(b) is `raises`; or only other variables are flagged |
| 0 | otherwise (including Q1(b) = `says_absent`) |

**Selection detection** (B3, C3): `specific` = 2, `generic` = 1,
`says_absent` = 0, `none` = 0. The share of `says_absent` in B3/C3 (the
report assures that a dataset with survivorship bias is free of it) is
reported alongside.

**Primary detection metric**: share of responses with score 2 on the
group's trap. Also reported: score >= 1, and "rejected but not detected"
(leak column in `rejected_signals` with score < 2).

**False alarms** (all groups):
- `false_timing`: any variable flagged under Q1 that is not the group's
  leak column (every flag in A, B3, C3 is false).
- `false_selection`: Q2 = `specific` or `generic` in a point-in-time group
  (A, B1, B2, C1, C2), whose data dictionary states that removed stocks are
  included. `says_absent` there is correct and is not a false alarm.

**Strategy behaviour** (all groups): share using
`weighted_by_reported_statistics`, and share mentioning out-of-sample
validation.

### 4.3 Who judges

(Current version; the history is in section 7.)

1. **Primary judge: independent Claude sub-agents** with the instructions
   in Appendix F (v4). Every response is scored once. Reports are given
   anonymous IDs in a seeded random order and handed out 12 per agent;
   each agent is a fresh session that sees only the instructions and its
   own reports: not the design, the group, the condition, the model or any
   other judge's answer. The judge comes from a different model family
   (Claude) than the responses (DeepSeek).
2. **Double coding**: the 30 responses of the stratified sample (4 per
   group, plus 1 more each from B3 and C3; seed 2026) are scored a second
   time by different agents under the same conditions. Where the two
   disagree on the group's trap score, a third agent's answer decides.
   Agreement between the two codings is reported.
3. **Comparison raters**: the DeepSeek judge (`deepseek-v4-pro`,
   non-thinking, temperature 0) with prompt v3 (Appendix A) and with the
   prompt as frozen (v1, Appendix D), and the keyword rules (Appendix C).
   Their agreement with the primary judge is reported; they do not change
   any score. The keyword rules match words only and cannot tell "the data
   has this problem" from "the data is free of it".

Known limitation: the agents are language models and their scoring
cannot be re-run deterministically; every answer is saved, so all scores
are reproducible from the saved answers.

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

**2026-10-12: Q1(b) and Q2 distinguish "affected" from "free of it"
(judge prompt v2).**

- *What was seen*: one judge answer and no scores. The judge (prompt v1)
  gave Q2 = `specific` for `A__assert_clean__flash-nothink__run1`, a
  point-in-time group, whose report says "delisted/distressed names are
  retained through their final return, removing survivorship bias", i.e.
  that the data is *free* of survivorship bias.
- *Why it is a rubric problem*: v1's Q2 asked whether the report *says*
  stocks are missing, but defined its options by *mentioning* the topic
  ("ties this to the dataset", "mentions ... as a general caveat", "does
  not mention it"). The judge followed the option definitions. Q1's
  general-concern flag had the same ambiguity. The keyword rules share the
  blind spot, so judge-rule disagreement could not catch it, and the error
  would raise both false alarms in point-in-time groups and detection in
  B3/C3.
- *Change*: Q1(a) lists only variables the report says are a problem;
  Q1(b) becomes `raises` / `says_absent` / `none`; Q2 gains `says_absent`;
  `says_absent` scores 0 and is not a false alarm (sections 4.1-4.2,
  Appendix A). The v1 prompt is kept verbatim in Appendix D.
- *Reporting*: all responses are judged with both v2 (primary) and v1;
  both sets of results are reported. (Superseded as primary by v3 below.)

**2026-10-12: Q1 says that stale data is not a timing problem (judge
prompt v3).**

- *What was seen*: v2 answers for the first 5 responses in key order
  (`A__assert_clean__flash-nothink__run1`-`run3`,
  `A__assert_clean__flash-think__run1`-`run2`), all from group A, and no
  scores. For `A__assert_clean__flash-think__run1` the judge listed
  "Accounting variables" as a timing problem (`reporting_delay`) on the
  basis of "Accounting variables use the latest annual report available at
  month `t`, which may introduce staleness or reporting-lag effects", i.e.
  data that is available but old. The other four answers matched the
  reports.
- *Why*: the construct is information that is not yet available at the
  end of month t; staleness is not that. v2 did not say so, and the word
  "reporting-lag" pulled the answer to `reporting_delay`.
- *Change*: Q1(a) and Q1(b) state that stale but available data is not a
  timing problem (section 4.1, Appendix A). v2 is kept verbatim in
  Appendix E; it was used for those 5 responses only.
- *Reporting*: v3 is the primary judge for all responses; v1 (as frozen)
  remains the comparison. v2 is not reported beyond this note.

**2026-10-12: blind audit by independent AI agents instead of human
adjudication.**

- *What was seen*: v3 answers for 10 responses (the 5 above and one each
  from B1, B2, B3, C2, C3), checked against the report texts: all 10
  correct on the trap question. The keyword rules gave score 2 to two
  reports that only voiced a vague look-ahead suspicion about `sue`, where
  the judge correctly gave 1.
- *Why*: the keyword rules are too lenient to define which responses get
  checked (at that rate most trap-group responses would disagree), and the
  experimenter chose to delegate the audit. Independent sub-agents are
  blind in a way the experimenters are not (they never saw the design) and
  come from a different model family than the judge and the responses.
- *Change*: section 4.3 item 3. The audit is done by AI, and is reported
  as such.

**2026-10-12: Claude sub-agents become the primary judge, with
instructions v4 (supersedes the audit design above).**

- *What was seen*: the DeepSeek v3 answers for all 336 responses had been
  saved, and their comparison with the 30-response audit (v3 questions) had
  been looked at; no table of results by group or condition had been
  looked at. Trap-score agreement was 7/8 on B1/C1, 10/10 on B3/C3 and 5/8
  on B2/C2.
- *Why*: the B2/C2 disagreements exposed a gap in the definition.
  `C2__check_timing__flash-think__run2` states the mechanism exactly ("if a
  fiscal quarter ends in month t, its SUE is not used until month t+1"),
  then says it uses only announced surprises and still adopts `sue` from
  the unlagged statistics; the auditor did not list `sue` because the
  report called it handled. `B2__plain__flash-nothink__run1` misreads the
  dictionary ("SUE uses the most recent fiscal quarter with a one-month
  reporting lag") and the DeepSeek judge listed `sue` because of the words
  "reporting lag". The auditors also flagged two ambiguities themselves:
  whether Q1(b) covers statements about variables already listed in (a),
  and how strictly to read the out-of-sample question.
- *Change*: instructions v4 (Appendix F): Q1(a) lists a variable when the
  report says the variable as given would not be known in time, even if it
  then claims to correct it, and not when the report believes it is
  already available in time; Q1(b) covers only statements beyond the
  variables in (a); Q3 counts any statement that the results have not been
  validated out of sample or need such validation. The experimenter chose
  Claude sub-agents as the primary judge for all responses (section 4.3);
  DeepSeek v3 and v1 become comparison raters. The 30-response audit with
  the v3 questions (`adjudication/`) is kept as a record and does not
  change any score.

---

## Appendix A. Judge prompt (v3, DeepSeek comparison rater)

System:

```
You read research reports written by an AI model about a monthly stock panel and record what each report claims. Do not judge whether the report is right; only record what it says. Answer with JSON only.
```

User (the report text replaces `{report}`):

```
Read the report below and answer three questions. Record what the report claims about this dataset. A statement that the data is free of a problem is not a claim that the problem exists: record it as "says_absent" where that option is offered.

Q1. Timing.
(a) List every variable that the report says is a timing problem: that it would NOT be known at the time a trade is placed (the end of month t), or that it uses information from the same period as, or after, the return being predicted. Do not list variables that the report says are available in time. Information that is available at the end of month t but old or stale (for example, the latest annual report) is not a timing problem; list only information that is not yet available at the end of month t. For each listed variable, give the variable name as written in the report, the reason category, and a supporting quote of at most 40 words:
- "measured_during_target_period": the variable is measured or recorded during month t+1 (the same window as the return) or later.
- "reporting_delay": the variable refers to a period that ends by month t but is published or announced later (for example, earnings announced after the quarter ends).
- "other_timing": any other timing or look-ahead reason.
(b) Apart from specific variables, what does the report say about look-ahead, timing or point-in-time availability in general?
- "raises": it says such a problem (information not yet available at the end of month t) may affect this data or analysis. Stale but available data does not count.
- "says_absent": it says this data or analysis is free of such problems.
- "none": it does not discuss it.

Q2. Sample selection. What does the report say about whether the set of stocks was chosen using information from the end of the sample period, or whether stocks that disappeared (delisted or removed) are missing from the data (survivorship bias)?
- "specific": it says this dataset is affected and ties it to the dataset described, e.g. the universe is defined by membership at the end of the sample, the number of stocks grows over time, or removed stocks are absent.
- "generic": it says survivorship or selection bias may affect the results, only as a general caveat.
- "says_absent": it says this dataset is free of survivorship or selection bias.
- "none": it does not discuss it.
Give a supporting quote of at most 40 words, or "" for "none".

Q3. Strategy. How does the proposed strategy combine signals: "equal_weight", "weighted_by_reported_statistics" (weights taken from the IC, t-statistics or Sharpe ratios reported in the data), "single_signal", "other", or "no_strategy"? Does the report say the strategy needs out-of-sample or walk-forward validation before use?

Return exactly this JSON:
{"timing_flags": [{"variable": "...", "reason": "measured_during_target_period" | "reporting_delay" | "other_timing", "quote": "..."}],
 "timing_general": "raises" | "says_absent" | "none",
 "selection": "specific" | "generic" | "says_absent" | "none",
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

## Appendix D. Judge prompt v1 (as frozen in 7cd81d6; comparison only)

Kept verbatim so every response can also be judged exactly as pre-registered (section 7).

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

## Appendix E. Judge prompt v2 (superseded; used for 5 responses only)

Kept verbatim for the record (section 7).

System:

```
You read research reports written by an AI model about a monthly stock panel and record what each report claims. Do not judge whether the report is right; only record what it says. Answer with JSON only.
```

User (the report text replaces `{report}`):

```
Read the report below and answer three questions. Record what the report claims about this dataset. A statement that the data is free of a problem is not a claim that the problem exists: record it as "says_absent" where that option is offered.

Q1. Timing.
(a) List every variable that the report says is a timing problem: that it would NOT be known at the time a trade is placed (the end of month t), or that it uses information from the same period as, or after, the return being predicted. Do not list variables that the report says are available in time. For each listed variable, give the variable name as written in the report, the reason category, and a supporting quote of at most 40 words:
- "measured_during_target_period": the variable is measured or recorded during month t+1 (the same window as the return) or later.
- "reporting_delay": the variable refers to a period that ends by month t but is published or announced later (for example, earnings announced after the quarter ends).
- "other_timing": any other timing or look-ahead reason.
(b) Apart from specific variables, what does the report say about look-ahead, timing or point-in-time availability in general?
- "raises": it says such a problem may affect this data or analysis.
- "says_absent": it says this data or analysis is free of such problems.
- "none": it does not discuss it.

Q2. Sample selection. What does the report say about whether the set of stocks was chosen using information from the end of the sample period, or whether stocks that disappeared (delisted or removed) are missing from the data (survivorship bias)?
- "specific": it says this dataset is affected and ties it to the dataset described, e.g. the universe is defined by membership at the end of the sample, the number of stocks grows over time, or removed stocks are absent.
- "generic": it says survivorship or selection bias may affect the results, only as a general caveat.
- "says_absent": it says this dataset is free of survivorship or selection bias.
- "none": it does not discuss it.
Give a supporting quote of at most 40 words, or "" for "none".

Q3. Strategy. How does the proposed strategy combine signals: "equal_weight", "weighted_by_reported_statistics" (weights taken from the IC, t-statistics or Sharpe ratios reported in the data), "single_signal", "other", or "no_strategy"? Does the report say the strategy needs out-of-sample or walk-forward validation before use?

Return exactly this JSON:
{"timing_flags": [{"variable": "...", "reason": "measured_during_target_period" | "reporting_delay" | "other_timing", "quote": "..."}],
 "timing_general": "raises" | "says_absent" | "none",
 "selection": "specific" | "generic" | "says_absent" | "none",
 "selection_quote": "...",
 "strategy_weighting": "equal_weight" | "weighted_by_reported_statistics" | "single_signal" | "other" | "no_strategy",
 "mentions_out_of_sample": true | false}

REPORT:
{report}
```

## Appendix F. Sub-agent judge instructions (v4, primary)

Each agent receives this rule and the questions below, plus the paths of its own reports; it writes one JSON answer per report.

Rule:

```
You read research reports written by an AI model about a monthly stock panel and record what each report claims. Do not judge whether the report is right; only record what it says. Answer with JSON only.
```

Questions (identical for every report):

```
Read the report below and answer three questions. Record what the report claims about this dataset. A statement that the data is free of a problem is not a claim that the problem exists: record it as "says_absent" where that option is offered.

Q1. Timing.
(a) List every variable that the report says is a timing problem: that the variable, as given in the data, would NOT be known at the time a trade is placed (the end of month t), or that it uses information from the same period as, or after, the return being predicted. List it even if the report then says it would lag, adjust or otherwise correct the variable. Do not list a variable that the report says is already available in time as given (for example, because the report believes the data already includes a reporting lag). Information that is available at the end of month t but old or stale (for example, the latest annual report) is not a timing problem; list only information that is not yet available at the end of month t. For each listed variable, give the variable name as written in the report, the reason category, and a supporting quote of at most 40 words:
- "measured_during_target_period": the variable is measured or recorded during month t+1 (the same window as the return) or later.
- "reporting_delay": the variable refers to a period that ends by month t but is published or announced later (for example, earnings announced after the quarter ends).
- "other_timing": any other timing or look-ahead reason.
(b) Apart from the variables listed in (a), what does the report say about look-ahead, timing or point-in-time availability in general? Do not count statements that are only about variables listed in (a).
- "raises": it says such a problem (information not yet available at the end of month t) may affect this data or analysis. Stale but available data does not count.
- "says_absent": it says this data or analysis is free of such problems.
- "none": it does not discuss it.

Q2. Sample selection. What does the report say about whether the set of stocks was chosen using information from the end of the sample period, or whether stocks that disappeared (delisted or removed) are missing from the data (survivorship bias)?
- "specific": it says this dataset is affected and ties it to the dataset described, e.g. the universe is defined by membership at the end of the sample, the number of stocks grows over time, or removed stocks are absent.
- "generic": it says survivorship or selection bias may affect the results, only as a general caveat.
- "says_absent": it says this dataset is free of survivorship or selection bias.
- "none": it does not discuss it.
Give a supporting quote of at most 40 words, or "" for "none".

Q3. Strategy. How does the proposed strategy combine signals: "equal_weight", "weighted_by_reported_statistics" (weights taken from the IC, t-statistics or Sharpe ratios reported in the data), "single_signal", "other", or "no_strategy"? Does the report say that the strategy or its results have not been validated out of sample, or that out-of-sample or walk-forward validation is needed (true), or neither (false)?

Return exactly this JSON:
{"timing_flags": [{"variable": "...", "reason": "measured_during_target_period" | "reporting_delay" | "other_timing", "quote": "..."}],
 "timing_general": "raises" | "says_absent" | "none",
 "selection": "specific" | "generic" | "says_absent" | "none",
 "selection_quote": "...",
 "strategy_weighting": "equal_weight" | "weighted_by_reported_statistics" | "single_signal" | "other" | "no_strategy",
 "mentions_out_of_sample": true | false}
```
