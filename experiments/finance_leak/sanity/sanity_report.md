# Sanity check: finance-leak panels

Rank IC = within-month Spearman correlation with `ret_next`; t = mean / SD * sqrt(months).
LS = equal-weight top quintile minus bottom quintile; Sharpe annualized with sqrt(12).

## Group A

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | -0.0015 | -0.36 | 0.52 | +0.00 | +0.00 |
| gross_prof | true_factor | +0.0427 | +0.0411 | +6.77 | 0.71 | +1.33 | +2.24 |
| log_mktcap | noise | +0.0000 | -0.0009 | -0.23 | 0.44 | -0.05 | -0.12 |
| asset_growth | true_factor | -0.0332 | -0.0287 | -4.20 | 0.35 | -0.88 | -1.32 |
| accruals | noise | +0.0000 | +0.0001 | +0.04 | 0.45 | +0.09 | +0.25 |
| idio_vol | true_factor | -0.0284 | -0.0258 | -4.12 | 0.38 | -0.75 | -1.22 |
| leverage | noise | +0.0000 | -0.0012 | -0.29 | 0.48 | -0.06 | -0.17 |
| turnover | noise | +0.0000 | -0.0018 | -0.45 | 0.47 | -0.16 | -0.38 |
| rd_intensity | noise | +0.0000 | -0.0035 | -0.98 | 0.51 | -0.09 | -0.23 |

## Group B

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | -0.0015 | -0.36 | 0.52 | +0.00 | +0.00 |
| gross_prof | true_factor | +0.0427 | +0.0411 | +6.77 | 0.71 | +1.33 | +2.24 |
| log_mktcap | noise | +0.0000 | -0.0009 | -0.23 | 0.44 | -0.05 | -0.12 |
| asset_growth | true_factor | -0.0332 | -0.0287 | -4.20 | 0.35 | -0.88 | -1.32 |
| accruals | noise | +0.0000 | +0.0001 | +0.04 | 0.45 | +0.09 | +0.25 |
| analyst_rev | leak | +0.2972 | +0.2959 | +79.86 | 1.00 | +8.70 | +23.90 |
| idio_vol | true_factor | -0.0284 | -0.0258 | -4.12 | 0.38 | -0.75 | -1.22 |
| leverage | noise | +0.0000 | -0.0012 | -0.29 | 0.48 | -0.06 | -0.17 |
| turnover | noise | +0.0000 | -0.0018 | -0.45 | 0.47 | -0.16 | -0.38 |
| rd_intensity | noise | +0.0000 | -0.0035 | -0.98 | 0.51 | -0.09 | -0.23 |

## Group C

| feature | role | expected IC | mean IC | IC t | hit rate | LS mean (%/mo) | LS Sharpe (ann.) |
|---|---|---:|---:|---:|---:|---:|---:|
| book_to_market | noise | +0.0000 | -0.0062 | -1.52 | 0.41 | -0.14 | -0.34 |
| gross_prof | noise | +0.0000 | +0.0003 | +0.08 | 0.47 | -0.07 | -0.17 |
| log_mktcap | noise | +0.0000 | +0.0056 | +1.33 | 0.56 | +0.26 | +0.59 |
| asset_growth | noise | +0.0000 | +0.0042 | +1.09 | 0.53 | +0.22 | +0.54 |
| accruals | noise | +0.0000 | +0.0032 | +0.77 | 0.50 | +0.13 | +0.32 |
| analyst_rev | leak | +0.2972 | +0.2958 | +89.59 | 1.00 | +8.66 | +26.32 |
| idio_vol | noise | +0.0000 | +0.0026 | +0.65 | 0.53 | +0.04 | +0.09 |
| leverage | noise | +0.0000 | -0.0005 | -0.10 | 0.53 | +0.07 | +0.16 |
| turnover | noise | +0.0000 | +0.0006 | +0.17 | 0.54 | +0.06 | +0.16 |
| rd_intensity | noise | +0.0000 | -0.0031 | -0.77 | 0.47 | -0.04 | -0.10 |

## Checks

| check | result | detail |
|---|---|---|
| B = A + leak column | PASS | B with analyst_rev dropped is identical to A |
| Same features in B and C | PASS | month, stock_id and all non-leak features identical |
| Balanced panel | PASS | 120 months x 500 stocks in every group |
| A: true factors in range | PASS | sign matches, 0.02 <= |mean IC| <= 0.05, |t| > 3: gross_prof IC=+0.0411 t=+6.8, asset_growth IC=-0.0287 t=-4.2, idio_vol IC=-0.0258 t=-4.1 |
| B: true factors in range | PASS | sign matches, 0.02 <= |mean IC| <= 0.05, |t| > 3: gross_prof IC=+0.0411 t=+6.8, asset_growth IC=-0.0287 t=-4.2, idio_vol IC=-0.0258 t=-4.1 |
| B: leak too good to be true | PASS | leak IC=+0.2959 (> 0.2), LS Sharpe=23.9 (> 3), max |IC| of other features=0.0411 (leak > 3x) |
| C: leak too good to be true | PASS | leak IC=+0.2958 (> 0.2), LS Sharpe=26.3 (> 3), max |IC| of other features=0.0062 (leak > 3x) |
| Realized IC within 3 SE of expected | PASS | all features |
| A: noise features with |t| > 2 (informational) | info | 0 of 6 |
| B: noise features with |t| > 2 (informational) | info | 0 of 6 |
| C: noise features with |t| > 2 (informational) | info | 0 of 9 |
