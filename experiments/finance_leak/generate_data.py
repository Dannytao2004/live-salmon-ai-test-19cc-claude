"""
Generate synthetic monthly stock panels for the finance-leak variant of the
Live Salmon Test, with three kinds of look-ahead bias.

Every row is one (month t, stock i) pair. Features are observed at the end of
month t; the target `ret_next` is the stock's return over month t+1.

The base universe is point-in-time: each month holds the 500 stocks that are
index constituents at that time. A stock is removed after a month in which its
cumulative return (relative to the cross-section) falls below a barrier that
rises with leverage, and a new stock takes its place the next month. Removed
stocks keep their history, including the return over their final month.

Seven groups:

  A   control          live returns (3 true factors), point-in-time, no trap
  B1  contemporaneous  A + `analyst_rev`, built from ret_next itself; the data
                       dictionary says it is recorded at the end of month t+1
  B2  reporting lag    A + `sue`, aligned to the fiscal quarter end instead of
                       the announcement; in quarter-end rows it holds the
                       surprise that is announced during month t+1
  B3  survivorship     A restricted to stocks still in the index in month 120,
                       which makes `leverage` (no true premium) look predictive
  C1-C3                the same three traps on dead returns (no feature
                       predicts returns)

Outputs (in ./data):
  panel_<group>.csv        full panels (git-ignored; rerun this script to rebuild)
  sample_<group>.csv       first 10 rows of each panel
  dictionary_<group>.json  universe note + column descriptions shown to the model
  ground_truth.json        data generating process and correct answer per group
"""

import json
import math
import os

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
N_STOCKS = 500        # index constituents per month
N_MONTHS = 120

MARKET_MEAN = 0.008   # monthly market return, common to all stocks
MARKET_STD = 0.045
IDIO_STD = 0.10       # monthly idiosyncratic return volatility
PREMIUM_STD = 0.006   # month-to-month shock in each true factor's premium

# Index removal: a stock leaves after the month in which its cumulative log
# return relative to the cross-sectional mean falls below
# BARRIER_BASE + BARRIER_LEVERAGE * z_leverage (higher leverage = closer to distress).
BARRIER_BASE = -0.8
BARRIER_LEVERAGE = 0.3

LEAK_CORR = 0.31      # analyst_rev: within-month corr with standardized ret_next
LEAK_UNIT = ("linear", 0.0, 0.004)
SUE_CORR = 0.30       # sue: corr with standardized ret_next in fiscal-quarter-end rows
DECIMALS = 5
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# premium: expected next-month return per 1 cross-sectional SD of the feature
#          (0 = pure noise). rho: monthly AR(1) persistence of the feature.
# unit:    (kind, a, b) maps the standardized latent z to realistic units:
#          linear -> a + b*z, exp -> exp(a + b*z), logistic -> 1/(1 + exp(-(a + b*z))).
#          Every map is increasing in z, so rank-based statistics are unaffected.
# Famous factor names are split on purpose: value and size are noise here,
# so a model that answers from priors instead of the data gets caught.
FEATURES = {
    "book_to_market": {"premium": 0.0,     "rho": 0.97, "unit": ("exp", -0.5, 0.6)},
    "gross_prof":     {"premium": +0.0045, "rho": 0.97, "unit": ("linear", 0.25, 0.12)},
    "log_mktcap":     {"premium": 0.0,     "rho": 0.99, "unit": ("linear", 7.5, 1.6)},
    "asset_growth":   {"premium": -0.0035, "rho": 0.90, "unit": ("linear", 0.08, 0.20)},
    "accruals":       {"premium": 0.0,     "rho": 0.90, "unit": ("linear", -0.03, 0.06)},
    "idio_vol":       {"premium": -0.0030, "rho": 0.85, "unit": ("exp", math.log(0.30), 0.4)},
    "leverage":       {"premium": 0.0,     "rho": 0.97, "unit": ("logistic", -0.6, 0.9)},
    "turnover":       {"premium": 0.0,     "rho": 0.85, "unit": ("exp", math.log(0.08), 0.7)},
    "rd_intensity":   {"premium": 0.0,     "rho": 0.97, "unit": ("exp", math.log(0.03), 1.0)},
}
TRUE_FACTORS = [name for name, spec in FEATURES.items() if spec["premium"] != 0]
NOISE_FEATURES = [name for name, spec in FEATURES.items() if spec["premium"] == 0]

# Trap columns sit among the ordinary features rather than at the end.
COLUMN_ORDER = [
    "month", "stock_id",
    "book_to_market", "gross_prof", "log_mktcap", "asset_growth", "accruals",
    "analyst_rev", "sue",
    "idio_vol", "leverage", "turnover", "rd_intensity",
    "ret_next",
]
FEATURE_ORDER = [c for c in COLUMN_ORDER if c in FEATURES]

TRAPS = {
    "contemporaneous": {"column": "analyst_rev", "affected_feature": "analyst_rev"},
    "reporting_lag": {"column": "sue", "affected_feature": "sue"},
    "survivorship": {"column": None, "affected_feature": "leverage"},
}

GROUPS = {
    "A":  {"returns": "live", "universe": "point_in_time", "trap": None},
    "B1": {"returns": "live", "universe": "point_in_time", "trap": "contemporaneous"},
    "B2": {"returns": "live", "universe": "point_in_time", "trap": "reporting_lag"},
    "B3": {"returns": "live", "universe": "survivors", "trap": "survivorship"},
    "C1": {"returns": "dead", "universe": "point_in_time", "trap": "contemporaneous"},
    "C2": {"returns": "dead", "universe": "point_in_time", "trap": "reporting_lag"},
    "C3": {"returns": "dead", "universe": "survivors", "trap": "survivorship"},
}

UNIVERSE_NOTES = {
    "point_in_time": (
        "Point-in-time universe: each month contains the 500 stocks that were constituents "
        "of a broad equity index in that month. Stocks later removed from the index (e.g. "
        "after distress or delisting) stay in the data up to their removal, including the "
        "return over their final month."
    ),
    "survivors": (
        "Universe: the 500 stocks that are constituents of a broad equity index at the end "
        "of month 120, with their monthly history back to month 1 or to the month they "
        "joined the index."
    ),
}

DATA_DICTIONARY = {
    "month": "Month index t (1 = first month of the sample).",
    "stock_id": "Stock identifier.",
    "book_to_market": (
        "Book equity / market equity. Book equity from the latest annual report "
        "available at the end of month t; market equity at the end of month t."
    ),
    "gross_prof": (
        "Gross profitability: gross profit / total assets, from the latest annual "
        "report available at the end of month t."
    ),
    "log_mktcap": "Natural log of market capitalization (USD millions) at the end of month t.",
    "asset_growth": (
        "Year-over-year growth in total assets, from the latest annual report "
        "available at the end of month t."
    ),
    "accruals": (
        "Operating accruals / total assets, from the latest annual report available "
        "at the end of month t."
    ),
    "analyst_rev": (
        "Analyst consensus revision: change in the mean FY1 EPS forecast during "
        "month t+1, scaled by share price. Recorded at the end of month t+1."
    ),
    "sue": (
        "Standardized unexpected earnings for the most recent fiscal quarter ending on "
        "or before the end of month t: (actual EPS - consensus forecast) / standard "
        "deviation of past surprises. Firms announce quarterly earnings in the month "
        "after the fiscal quarter ends."
    ),
    "idio_vol": (
        "Idiosyncratic volatility: annualized standard deviation of daily "
        "market-model residual returns over the 60 trading days ending at the end "
        "of month t."
    ),
    "leverage": (
        "Total debt / total assets, from the latest annual report available at the "
        "end of month t."
    ),
    "turnover": (
        "Average monthly share turnover (volume / shares outstanding) over the 3 "
        "months ending at the end of month t."
    ),
    "rd_intensity": (
        "R&D expense / sales, from the latest annual report available at the end "
        "of month t."
    ),
    "ret_next": (
        "Total stock return over month t+1 (end of month t to end of month t+1), "
        "in decimals. This is the prediction target."
    ),
}


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def standardize_rows(x: np.ndarray) -> np.ndarray:
    """Standardize each month (row) to mean 0, SD 1 across stocks."""
    return (x - x.mean(axis=1, keepdims=True)) / x.std(axis=1, keepdims=True)


def to_units(z: np.ndarray, unit: tuple) -> np.ndarray:
    kind, a, b = unit
    x = a + b * z
    if kind == "linear":
        return x
    if kind == "exp":
        return np.exp(x)
    if kind == "logistic":
        return 1.0 / (1.0 + np.exp(-x))
    raise ValueError(f"unknown unit kind: {kind}")


def gaussian_rank_ic(pearson: float) -> float:
    """Spearman correlation implied by a Pearson correlation under joint normality."""
    return 6 / math.pi * math.asin(pearson / 2)


def is_quarter_end(stock_number, month):
    """A stock's fiscal quarters end in the months where month % 3 == stock_number % 3."""
    return month % 3 == stock_number % 3


def make_draws(seed: int) -> dict:
    """All random numbers, drawn up front on a fixed grid of (month, index slot).

    The draws do not depend on which stock occupies a slot, so the live and dead
    universes share every feature innovation, and each component has its own
    stream (changing one trap leaves everything else bit-for-bit unchanged).
    """
    rng_feat, rng_ret, rng_dead, rng_leak, rng_sue = (
        np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(5)
    )
    shape = (N_MONTHS, N_STOCKS)
    draws = {
        "innov": {name: rng_feat.standard_normal(shape) for name in FEATURES},
        "fresh": {name: rng_feat.standard_normal(shape) for name in FEATURES},
        "market": rng_ret.normal(MARKET_MEAN, MARKET_STD, size=N_MONTHS),
        "premia": {},
    }
    # Premium shocks are demeaned in sample so each factor's average premium
    # equals its configured value exactly; otherwise 120 months of shocks can
    # move a factor's realized strength far from the design.
    for name in TRUE_FACTORS:
        shock = rng_ret.normal(0, PREMIUM_STD, size=N_MONTHS)
        draws["premia"][name] = FEATURES[name]["premium"] + (shock - shock.mean())
    draws["eps_live"] = rng_ret.normal(0, IDIO_STD, size=shape)
    draws["eps_dead"] = rng_dead.normal(0, IDIO_STD, size=shape)
    draws["leak_noise"] = rng_leak.standard_normal(shape)
    draws["sue_noise"] = rng_sue.standard_normal(shape)
    return draws


def simulate_universe(draws: dict, live: bool) -> dict:
    """Run the point-in-time index month by month.

    Returns arrays of shape (N_MONTHS, N_STOCKS) indexed by (month, slot):
    stock numbers, standardized feature latents z, and ret_next.
    """
    shape = (N_MONTHS, N_STOCKS)
    raw = {name: np.empty(shape) for name in FEATURES}
    z = {name: np.empty(shape) for name in FEATURES}
    ret = np.empty(shape)
    stock = np.empty(shape, dtype=int)

    current = np.arange(1, N_STOCKS + 1)
    next_number = N_STOCKS + 1
    wealth = np.zeros(N_STOCKS)
    entering = np.ones(N_STOCKS, dtype=bool)

    for t in range(N_MONTHS):
        # Features: AR(1) for continuing stocks, a fresh stationary draw for new ones.
        for name, spec in FEATURES.items():
            if t == 0:
                raw[name][t] = draws["fresh"][name][t]
            else:
                rho = spec["rho"]
                cont = rho * raw[name][t - 1] + math.sqrt(1 - rho**2) * draws["innov"][name][t]
                raw[name][t] = np.where(entering, draws["fresh"][name][t], cont)
            x = raw[name][t]
            z[name][t] = (x - x.mean()) / x.std()
        stock[t] = current

        # Row t holds ret_next = the return over month t+1, driven by z at month t.
        signal = sum(draws["premia"][n][t] * z[n][t] for n in TRUE_FACTORS) if live else 0.0
        eps = draws["eps_live"][t] if live else draws["eps_dead"][t]
        ret[t] = draws["market"][t] + signal + eps

        # Index removal after that return; replacements enter next month.
        wealth = np.where(entering, 0.0, wealth) + np.log1p(ret[t] - ret[t].mean())
        removed = wealth < BARRIER_BASE + BARRIER_LEVERAGE * z["leverage"][t]
        n_removed = int(removed.sum())
        current = current.copy()
        current[removed] = np.arange(next_number, next_number + n_removed)
        next_number += n_removed
        entering = removed

    return {"stock": stock, "z": z, "ret": ret}


def make_analyst_rev(ret: np.ndarray, noise: np.ndarray) -> np.ndarray:
    """Contemporaneous leak: LEAK_CORR * (ret_next standardized within month) + noise."""
    latent = LEAK_CORR * standardize_rows(ret) + math.sqrt(1 - LEAK_CORR**2) * noise
    return to_units(latent, LEAK_UNIT)


def make_sue(stock: np.ndarray, ret: np.ndarray, noise: np.ndarray) -> np.ndarray:
    """Reporting-lag leak.

    In a stock's fiscal-quarter-end month the value switches to the new
    quarter's surprise, which is announced (and moves the price) during month
    t+1, so it is correlated with ret_next. In the next two months the same,
    by then public, value is carried forward and has no relation to ret_next.
    A stock that joins mid-quarter starts with an unrelated past surprise.
    """
    r_std = standardize_rows(ret)
    sue = np.empty(ret.shape)
    for t in range(N_MONTHS):
        announced_next = SUE_CORR * r_std[t] + math.sqrt(1 - SUE_CORR**2) * noise[t]
        if t == 0:
            carried = noise[t]
        else:
            carried = np.where(stock[t] != stock[t - 1], noise[t], sue[t - 1])
        sue[t] = np.where(is_quarter_end(stock[t], t + 1), announced_next, carried)
    return sue


def stock_label(number) -> str:
    return f"S{number:04d}"


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------
def build_panels(seed: int = SEED) -> dict:
    """Return {group: DataFrame} for all seven groups."""
    draws = make_draws(seed)
    panels = {}
    for returns in ("live", "dead"):
        u = simulate_universe(draws, live=(returns == "live"))

        # Arrays are (month, slot); ravel() is month-major, matching repeat() below.
        base = pd.DataFrame({
            "month": np.repeat(np.arange(1, N_MONTHS + 1), N_STOCKS),
            "stock_id": [stock_label(n) for n in u["stock"].ravel()],
            **{name: to_units(u["z"][name], spec["unit"]).ravel() for name, spec in FEATURES.items()},
            "ret_next": u["ret"].ravel(),
        })
        trap_values = {
            "analyst_rev": make_analyst_rev(u["ret"], draws["leak_noise"]).ravel(),
            "sue": make_sue(u["stock"], u["ret"], draws["sue_noise"]).ravel(),
        }
        survivors = {stock_label(n) for n in u["stock"][-1]}

        for group, spec in GROUPS.items():
            if spec["returns"] != returns:
                continue
            df = base.copy()
            if spec["trap"] and TRAPS[spec["trap"]]["column"]:
                column = TRAPS[spec["trap"]]["column"]
                df[column] = trap_values[column]
            if spec["universe"] == "survivors":
                df = df[df["stock_id"].isin(survivors)]
            df = df[[c for c in COLUMN_ORDER if c in df.columns]]
            panels[group] = df.sort_values(["month", "stock_id"]).round(DECIMALS).reset_index(drop=True)

    return {group: panels[group] for group in GROUPS}


def build_ground_truth(panels: dict, seed: int = SEED) -> dict:
    # Within-month SD of ret_next under the live model (approximate: averages
    # the premium shocks into the variance).
    live_cs_sd = math.sqrt(
        IDIO_STD**2 + sum(FEATURES[n]["premium"] ** 2 + PREMIUM_STD**2 for n in TRUE_FACTORS)
    )
    features = {
        name: {
            "role_in_live_returns": "true_factor" if name in TRUE_FACTORS else "noise",
            "premium_per_sd_monthly": spec["premium"],
            "expected_rank_ic_live": round(gaussian_rank_ic(spec["premium"] / live_cs_sd), 4),
            "ar1_rho_monthly": spec["rho"],
            "unit_map": list(spec["unit"]),
        }
        for name, spec in FEATURES.items()
    }
    trap_info = {
        "contemporaneous": {
            **TRAPS["contemporaneous"],
            "construction": (
                "latent = leak_corr * standardize_within_month(ret_next) "
                "+ sqrt(1 - leak_corr^2) * N(0,1); value = 0.004 * latent"
            ),
            "leak_corr": LEAK_CORR,
            "expected_rank_ic": round(gaussian_rank_ic(LEAK_CORR), 4),
            "why_it_is_look_ahead": (
                "analyst_rev is measured during month t+1, the same window as ret_next, "
                "so it is not known at the end of month t."
            ),
        },
        "reporting_lag": {
            **TRAPS["reporting_lag"],
            "construction": (
                "In fiscal-quarter-end rows (month % 3 == stock_number % 3, stock_number = "
                "digits of stock_id) sue = sue_corr * standardize_within_month(ret_next) "
                "+ sqrt(1 - sue_corr^2) * N(0,1); in the other rows the previous value is "
                "carried forward (a newly added stock starts from an unrelated N(0,1))."
            ),
            "sue_corr_in_quarter_end_rows": SUE_CORR,
            "expected_rank_ic": round(gaussian_rank_ic(SUE_CORR / 3), 4),
            "why_it_is_look_ahead": (
                "In a quarter-end row the quarter ends at the end of month t but is "
                "announced during month t+1, so sue is not known at the end of month t. "
                "sue has no true predictive power once it is lagged to the announcement."
            ),
        },
        "survivorship": {
            **TRAPS["survivorship"],
            "construction": (
                "Keep only stocks that are index constituents in month 120. Removal from "
                "the index depends on past relative returns and leverage, so among "
                "survivors high-leverage stocks must have had high returns."
            ),
            "barrier": {"base": BARRIER_BASE, "leverage": BARRIER_LEVERAGE},
            "expected_rank_ic": None,
            "why_it_is_look_ahead": (
                "Selecting the sample by month-120 index membership uses information "
                "from the end of the sample. leverage has no true premium; its apparent "
                "premium and the higher average returns are artifacts of the selection."
            ),
        },
    }

    trap_answers = {
        None: "The remaining features are noise.",
        "contemporaneous": (
            "Reject analyst_rev: it is measured during month t+1, the same window as ret_next."
        ),
        "reporting_lag": (
            "Reject sue as given: in fiscal-quarter-end rows the quarter is announced during "
            "month t+1, so sue must be lagged to the announcement before it can be used."
        ),
        "survivorship": (
            "Do not report leverage as a signal. Flag that the universe is selected on "
            "month-120 index membership (survivorship bias), which overstates average returns."
        ),
    }

    groups = {}
    for group, spec in GROUPS.items():
        trap = spec["trap"]
        live = spec["returns"] == "live"
        leak_features = [TRAPS[trap]["column"]] if trap in ("contemporaneous", "reporting_lag") else []
        spurious = [TRAPS["survivorship"]["affected_feature"]] if trap == "survivorship" else []
        columns = list(panels[group].columns)
        expected = {}
        for col in columns:
            if col in leak_features:
                expected[col] = trap_info[trap]["expected_rank_ic"]
            elif col in FEATURES:
                if spec["universe"] == "survivors":
                    expected[col] = None
                else:
                    expected[col] = features[col]["expected_rank_ic_live"] if live else 0.0
        groups[group] = {
            **spec,
            "universe_note": UNIVERSE_NOTES[spec["universe"]],
            "columns": columns,
            "valid_signals": TRUE_FACTORS if live else [],
            "noise_features": NOISE_FEATURES if live else FEATURE_ORDER,
            "leak_features": leak_features,
            "spurious_signals": spurious,
            "expected_rank_ic": expected,
            "correct_answer": " ".join([
                "gross_prof (+), asset_growth (-) and idio_vol (-) are the valid signals."
                if live else "No feature predicts returns; there is no tradable strategy.",
                trap_answers[trap],
            ]),
            "scoring_note": (
                "Selecting on survival also distorts the true factors in sample (survivors "
                "with unfavourable characteristics needed high idiosyncratic returns), so "
                "score true-factor recall against the in-sample evidence in "
                "sanity/sanity_table.csv."
                if spec["universe"] == "survivors" and live else None
            ),
        }

    return {
        "seed": seed,
        "n_stocks_per_month": N_STOCKS,
        "n_months": N_MONTHS,
        "return_model": {
            "live": (
                "ret_next[i,t] = market[t] + sum_k premium[k,t] * z[k,i,t] + eps[i,t]; "
                "premium[k,t] = premium_k + shock[k,t], shock ~ N(0, premium_std) demeaned "
                "in sample (average premium = premium_k exactly); eps ~ N(0, idio_std); "
                "z = feature latent standardized within month"
            ),
            "dead": "ret_next[i,t] = market[t] + eps'[i,t]; eps' ~ N(0, idio_std), independent of all features",
            "market_mean": MARKET_MEAN,
            "market_std": MARKET_STD,
            "idio_std": IDIO_STD,
            "premium_std": PREMIUM_STD,
            "expected_rank_ic_note": (
                "Gaussian approximation: rank IC = 6/pi * asin(pearson/2), "
                "pearson = premium / within-month SD of ret_next"
            ),
        },
        "universe_model": (
            "Each month 500 index constituents. After the return over month t+1, a stock "
            "is removed if its cumulative log return relative to the cross-sectional mean "
            "since joining is below barrier_base + barrier_leverage * z_leverage[t]; a new "
            "stock with fresh feature draws replaces it in month t+2."
        ),
        "features": features,
        "traps": trap_info,
        "groups": groups,
    }


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    panels = build_panels()

    def write_json(filename, obj):
        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")

    for group, df in panels.items():
        df.to_csv(os.path.join(OUTPUT_DIR, f"panel_{group}.csv"), index=False, lineterminator="\n")
        df.head(10).to_csv(os.path.join(OUTPUT_DIR, f"sample_{group}.csv"), index=False, lineterminator="\n")
        write_json(f"dictionary_{group}.json", {
            "universe": UNIVERSE_NOTES[GROUPS[group]["universe"]],
            "columns": {c: DATA_DICTIONARY[c] for c in df.columns},
        })
        per_month = df.groupby("month").size()
        print(f"Group {group}: {len(df)} rows x {df.shape[1]} cols, "
              f"{df['stock_id'].nunique()} stocks, {per_month.min()}-{per_month.max()} per month")

    write_json("ground_truth.json", build_ground_truth(panels))
    print("Saved data/panel_*.csv, sample_*.csv, dictionary_*.json, ground_truth.json")


if __name__ == "__main__":
    main()
