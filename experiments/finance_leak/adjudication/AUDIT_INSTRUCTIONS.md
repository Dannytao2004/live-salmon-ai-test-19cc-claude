# Blind audit instructions

You are auditing research reports written by an AI model. For each report assigned to you, answer the questions below exactly as instructed, using only the text of that report.

Rules:
- Read only this file and the report files you are assigned (`adjudication/packets/Pxx.md`). Do not open, list or search any other file or folder in the repository.
- You read research reports written by an AI model about a monthly stock panel and record what each report claims. Do not judge whether the report is right; only record what it says. Answer with JSON only.
- Write your answer for report Pxx to `adjudication/audit/Pxx.json`: exactly one JSON object in the format below, nothing else.

## Questions (identical for every report)

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
