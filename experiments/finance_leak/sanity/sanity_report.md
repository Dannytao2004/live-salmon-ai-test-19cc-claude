# Sanity check: finance-leak panels

Rank IC = within-month Spearman correlation with `ret_next`; t = mean / SD * sqrt(months).
LS = equal-weight top quintile minus bottom quintile; Sharpe annualized with sqrt(12).
Expected IC is blank for survivor groups (no closed form).

## Groups

| group | rows | distinct stocks | stocks in month 1 | stocks in month 120 | mean ret_next (%/mo) |
|---|---:|---:|---:|---:|---:|
| A | 60000 | 1217 | 500 | 500 | 0.93 |
| B1 | 60000 | 1217 | 500 | 500 | 0.93 |
| B2 | 60000 | 1217 | 500 | 500 | 0.93 |
| B3 | 34387 | 500 | 139 | 500 | 1.85 |
| C1 | 60000 | 1213 | 500 | 500 | 0.94 |
| C2 | 60000 | 1213 | 500 | 500 | 0.94 |
| C3 | 34708 | 500 | 143 | 500 | 1.82 |

## Group A

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | +0.0027 | +0.68 | 0.53 | +0.09 | +0.23 |
| gross_prof | true_factor | +0.0427 | +0.0378 | +6.07 | 0.70 | +1.16 | +1.94 |
| log_mktcap | noise | +0.0000 | +0.0055 | +1.26 | 0.56 | +0.23 | +0.55 |
| asset_growth | true_factor | -0.0332 | -0.0303 | -4.29 | 0.39 | -0.99 | -1.48 |
| accruals | noise | +0.0000 | +0.0015 | +0.36 | 0.48 | +0.14 | +0.36 |
| idio_vol | true_factor | -0.0284 | -0.0261 | -4.19 | 0.35 | -0.74 | -1.20 |
| leverage | noise | +0.0000 | -0.0011 | -0.30 | 0.54 | +0.02 | +0.05 |
| turnover | noise | +0.0000 | +0.0006 | +0.14 | 0.48 | +0.02 | +0.06 |
| rd_intensity | noise | +0.0000 | -0.0004 | -0.10 | 0.45 | +0.13 | +0.32 |

## Group B1

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | +0.0027 | +0.68 | 0.53 | +0.09 | +0.23 |
| gross_prof | true_factor | +0.0427 | +0.0378 | +6.07 | 0.70 | +1.16 | +1.94 |
| log_mktcap | noise | +0.0000 | +0.0055 | +1.26 | 0.56 | +0.23 | +0.55 |
| asset_growth | true_factor | -0.0332 | -0.0303 | -4.29 | 0.39 | -0.99 | -1.48 |
| accruals | noise | +0.0000 | +0.0015 | +0.36 | 0.48 | +0.14 | +0.36 |
| analyst_rev | leak | +0.2972 | +0.2963 | +80.29 | 1.00 | +8.73 | +24.23 |
| idio_vol | true_factor | -0.0284 | -0.0261 | -4.19 | 0.35 | -0.74 | -1.20 |
| leverage | noise | +0.0000 | -0.0011 | -0.30 | 0.54 | +0.02 | +0.05 |
| turnover | noise | +0.0000 | +0.0006 | +0.14 | 0.48 | +0.02 | +0.06 |
| rd_intensity | noise | +0.0000 | -0.0004 | -0.10 | 0.45 | +0.13 | +0.32 |

## Group B2

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | +0.0027 | +0.68 | 0.53 | +0.09 | +0.23 |
| gross_prof | true_factor | +0.0427 | +0.0378 | +6.07 | 0.70 | +1.16 | +1.94 |
| log_mktcap | noise | +0.0000 | +0.0055 | +1.26 | 0.56 | +0.23 | +0.55 |
| asset_growth | true_factor | -0.0332 | -0.0303 | -4.29 | 0.39 | -0.99 | -1.48 |
| accruals | noise | +0.0000 | +0.0015 | +0.36 | 0.48 | +0.14 | +0.36 |
| sue | leak | +0.0955 | +0.0952 | +26.55 | 1.00 | +2.96 | +7.65 |
| idio_vol | true_factor | -0.0284 | -0.0261 | -4.19 | 0.35 | -0.74 | -1.20 |
| leverage | noise | +0.0000 | -0.0011 | -0.30 | 0.54 | +0.02 | +0.05 |
| turnover | noise | +0.0000 | +0.0006 | +0.14 | 0.48 | +0.02 | +0.06 |
| rd_intensity | noise | +0.0000 | -0.0004 | -0.10 | 0.45 | +0.13 | +0.32 |

## Group B3

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise |  | +0.0029 | +0.54 | 0.46 | -0.06 | -0.11 |
| gross_prof | true_factor |  | +0.0293 | +3.83 | 0.61 | +0.88 | +1.19 |
| log_mktcap | noise |  | -0.0043 | -0.67 | 0.49 | -0.09 | -0.14 |
| asset_growth | true_factor |  | -0.0164 | -1.87 | 0.44 | -0.64 | -0.78 |
| accruals | noise |  | +0.0130 | +2.06 | 0.58 | +0.31 | +0.50 |
| idio_vol | true_factor |  | -0.0266 | -3.76 | 0.37 | -0.78 | -1.15 |
| leverage | spurious |  | +0.0137 | +2.56 | 0.57 | +0.50 | +0.99 |
| turnover | noise |  | +0.0042 | +0.64 | 0.53 | +0.15 | +0.23 |
| rd_intensity | noise |  | +0.0018 | +0.30 | 0.45 | +0.12 | +0.20 |

## Group C1

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | -0.0030 | -0.72 | 0.47 | -0.11 | -0.27 |
| gross_prof | noise | +0.0000 | +0.0039 | +0.93 | 0.52 | +0.10 | +0.26 |
| log_mktcap | noise | +0.0000 | +0.0001 | +0.02 | 0.51 | +0.03 | +0.08 |
| asset_growth | noise | +0.0000 | +0.0061 | +1.64 | 0.54 | +0.28 | +0.72 |
| accruals | noise | +0.0000 | +0.0055 | +1.34 | 0.50 | +0.29 | +0.70 |
| analyst_rev | leak | +0.2972 | +0.2958 | +89.59 | 1.00 | +8.66 | +26.38 |
| idio_vol | noise | +0.0000 | +0.0043 | +1.14 | 0.55 | +0.03 | +0.08 |
| leverage | noise | +0.0000 | -0.0043 | -1.00 | 0.46 | -0.02 | -0.05 |
| turnover | noise | +0.0000 | +0.0001 | +0.02 | 0.51 | +0.01 | +0.02 |
| rd_intensity | noise | +0.0000 | -0.0002 | -0.05 | 0.52 | +0.05 | +0.13 |

## Group C2

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | -0.0030 | -0.72 | 0.47 | -0.11 | -0.27 |
| gross_prof | noise | +0.0000 | +0.0039 | +0.93 | 0.52 | +0.10 | +0.26 |
| log_mktcap | noise | +0.0000 | +0.0001 | +0.02 | 0.51 | +0.03 | +0.08 |
| asset_growth | noise | +0.0000 | +0.0061 | +1.64 | 0.54 | +0.28 | +0.72 |
| accruals | noise | +0.0000 | +0.0055 | +1.34 | 0.50 | +0.29 | +0.70 |
| sue | leak | +0.0955 | +0.0998 | +23.25 | 0.99 | +3.04 | +7.31 |
| idio_vol | noise | +0.0000 | +0.0043 | +1.14 | 0.55 | +0.03 | +0.08 |
| leverage | noise | +0.0000 | -0.0043 | -1.00 | 0.46 | -0.02 | -0.05 |
| turnover | noise | +0.0000 | +0.0001 | +0.02 | 0.51 | +0.01 | +0.02 |
| rd_intensity | noise | +0.0000 | -0.0002 | -0.05 | 0.52 | +0.05 | +0.13 |

## Group C3

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise |  | -0.0017 | -0.28 | 0.51 | -0.05 | -0.08 |
| gross_prof | noise |  | +0.0012 | +0.23 | 0.50 | +0.12 | +0.22 |
| log_mktcap | noise |  | +0.0014 | +0.26 | 0.56 | -0.07 | -0.14 |
| asset_growth | noise |  | +0.0055 | +1.16 | 0.52 | +0.37 | +0.74 |
| accruals | noise |  | +0.0059 | +1.03 | 0.54 | +0.24 | +0.41 |
| idio_vol | noise |  | +0.0056 | +0.86 | 0.50 | +0.13 | +0.19 |
| leverage | spurious |  | +0.0164 | +2.74 | 0.59 | +0.52 | +0.92 |
| turnover | noise |  | -0.0005 | -0.10 | 0.53 | +0.13 | +0.23 |
| rd_intensity | noise |  | +0.0010 | +0.20 | 0.52 | -0.06 | -0.11 |

## Checks

| check | result | detail |
|---|---|---|
| B1 = A + analyst_rev | PASS | B1 with analyst_rev dropped is identical to A |
| B2 = A + sue | PASS | B2 with sue dropped is identical to A |
| C1 and C2 share one dead panel | PASS | C1 without analyst_rev == C2 without sue |
| B3 = A restricted to month-120 constituents | PASS | same rows and values, nothing else changed |
| C3 = dead panel restricted to month-120 constituents | PASS | same rows and values, nothing else changed |
| Point-in-time panels: 500 stocks every month | PASS | A: 1217 distinct stocks, B1: 1217 distinct stocks, B2: 1217 distinct stocks, C1: 1213 distinct stocks, C2: 1213 distinct stocks |
| Survivor panels: 500 stocks in month 120, fewer earlier | PASS | B3: 139 in month 1 -> 500 in month 120, C3: 143 in month 1 -> 500 in month 120 |
| A: true factors in range | PASS | sign matches, 0.02 <= |mean IC| <= 0.05, |t| > 3: gross_prof IC=+0.0378 t=+6.1, asset_growth IC=-0.0303 t=-4.3, idio_vol IC=-0.0261 t=-4.2 |
| B1: analyst_rev too good to be true | PASS | IC=+0.2963 t=+80.3 LS Sharpe=24.2; max |IC| of other features=0.0378 |
| C1: analyst_rev too good to be true | PASS | IC=+0.2958 t=+89.6 LS Sharpe=26.4; max |IC| of other features=0.0061 |
| B2: sue is the strongest signal | PASS | IC=+0.0952 t=+26.5 LS Sharpe=7.6; max |IC| of other features=0.0378 |
| B2: sue leak sits in quarter-end rows | PASS | quarter-end rows IC=+0.2833 (t=+47.4); other rows IC=+0.0009 (t=+0.19) |
| C2: sue is the strongest signal | PASS | IC=+0.0998 t=+23.2 LS Sharpe=7.3; max |IC| of other features=0.0061 |
| C2: sue leak sits in quarter-end rows | PASS | quarter-end rows IC=+0.2932 (t=+49.2); other rows IC=+0.0025 (t=+0.46) |
| B3: survivorship makes leverage look predictive | PASS | leverage IC=+0.0137 t=+2.56 among survivors vs IC=-0.0011 t=-0.30 in point-in-time A |
| B3: survivors' average return overstated | PASS | mean ret_next 1.85%/mo vs 0.93%/mo in A (+11.0%/yr) |
| C3: survivorship makes leverage look predictive | PASS | leverage IC=+0.0164 t=+2.74 among survivors vs IC=-0.0043 t=-1.00 in point-in-time C1 |
| C3: survivors' average return overstated | PASS | mean ret_next 1.82%/mo vs 0.94%/mo in C1 (+10.6%/yr) |
| Realized IC within 3 SE of expected (point-in-time groups) | PASS | 49 features checked |
| A: noise features with |t| > 2 (informational) | info | 0 of 6 |
| B1: noise features with |t| > 2 (informational) | info | 0 of 6 |
| B2: noise features with |t| > 2 (informational) | info | 0 of 6 |
| B3: noise features with |t| > 2 (informational) | info | 1 of 5: accruals t=+2.06 |
| C1: noise features with |t| > 2 (informational) | info | 0 of 9 |
| C2: noise features with |t| > 2 (informational) | info | 0 of 9 |
| C3: noise features with |t| > 2 (informational) | info | 0 of 8 |
