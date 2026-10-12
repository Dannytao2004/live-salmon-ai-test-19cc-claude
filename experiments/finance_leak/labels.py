"""
Single source of truth for the labels used across the finance-leak pipeline:
group codes, trap names, signal roles, prompt conditions, model output fields
and file paths. Data generation, sanity checks, prompt building, the runner
and the evaluator all import these names instead of spelling them out.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
SANITY_DIR = os.path.join(HERE, "sanity")
PROMPT_DIR = os.path.join(HERE, "prompts")
RAW_RESULTS_DIR = os.path.join(HERE, "results", "raw")
ENV_PATH = os.path.join(HERE, ".env")   # this project's API keys; git-ignored

# ---------------------------------------------------------------------------
# Groups and traps
# ---------------------------------------------------------------------------
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

# Role of a feature within one group (ground truth and sanity tables).
ROLE_TRUE_FACTOR = "true_factor"
ROLE_NOISE = "noise"
ROLE_LEAK = "leak"              # trap column that carries future information
ROLE_SPURIOUS = "spurious"      # ordinary feature made to look predictive by the trap

# ---------------------------------------------------------------------------
# Prompt conditions: the sentence appended as the last line of the user
# prompt ("" = nothing appended). Identical across all groups.
# ---------------------------------------------------------------------------
CONDITIONS = {
    "plain": "",
    "check_data": "Check the data first.",
    "check_timing": "Check when each variable becomes available.",
    "assert_clean": "The data has already been checked and is clean. Go straight to the analysis.",
}

# ---------------------------------------------------------------------------
# Models: label -> provider, provider's model id, and provider-specific
# options. The label is what appears in result file names and tables.
# Providers themselves (endpoints, API key variables) live in run_models.py.
# ---------------------------------------------------------------------------
MODELS = {
    "flash-think":   {"provider": "deepseek", "model_id": "deepseek-flash", "thinking": True},
    "flash-nothink": {"provider": "deepseek", "model_id": "deepseek-flash", "thinking": False},
    "pro-think":     {"provider": "deepseek", "model_id": "deepseek-v4-pro", "thinking": True},
    "pro-nothink":   {"provider": "deepseek", "model_id": "deepseek-v4-pro", "thinking": False},
}
RUNS_PER_CELL = 3

# ---------------------------------------------------------------------------
# Fields of the JSON block every model must end its answer with.
# ---------------------------------------------------------------------------
FIELD_VALID = "valid_signals"
FIELD_REJECTED = "rejected_signals"
FIELD_STRATEGY = "strategy"
FIELD_LIMITATIONS = "limitations"
OUTPUT_FIELDS = (FIELD_VALID, FIELD_REJECTED, FIELD_STRATEGY, FIELD_LIMITATIONS)


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
def panel_path(group: str) -> str:
    return os.path.join(DATA_DIR, f"panel_{group}.csv")


def sample_path(group: str) -> str:
    return os.path.join(DATA_DIR, f"sample_{group}.csv")


def dictionary_path(group: str) -> str:
    return os.path.join(DATA_DIR, f"dictionary_{group}.json")


def ground_truth_path() -> str:
    return os.path.join(DATA_DIR, "ground_truth.json")


def prompt_key(group: str, condition: str) -> str:
    return f"{group}__{condition}"


def prompt_path(group: str, condition: str) -> str:
    return os.path.join(PROMPT_DIR, f"{prompt_key(group, condition)}.txt")


def result_key(group: str, condition: str, model: str, run: int) -> str:
    return f"{group}__{condition}__{model}__run{run}"


def result_path(group: str, condition: str, model: str, run: int) -> str:
    return os.path.join(RAW_RESULTS_DIR, f"{result_key(group, condition, model, run)}.json")


# ---------------------------------------------------------------------------
# Frozen prompt files. Each prompts/<group>__<condition>.txt holds exactly the
# text sent to the model; the runner reads it as-is and never rebuilds it.
# ---------------------------------------------------------------------------
PROMPT_SYSTEM_HEADER = "=== SYSTEM PROMPT ===\n"
PROMPT_USER_HEADER = "\n\n=== USER PROMPT ===\n"


def format_prompt_file(system: str, user: str) -> str:
    return PROMPT_SYSTEM_HEADER + system + PROMPT_USER_HEADER + user + "\n"


def read_prompt(group: str, condition: str) -> tuple:
    """Return (system, user) exactly as frozen in the prompt file."""
    with open(prompt_path(group, condition), encoding="utf-8", newline="") as f:
        text = f.read()
    if not text.startswith(PROMPT_SYSTEM_HEADER) or text.count(PROMPT_USER_HEADER) != 1:
        raise ValueError(f"malformed prompt file: {prompt_path(group, condition)}")
    system, user = text[len(PROMPT_SYSTEM_HEADER):].split(PROMPT_USER_HEADER)
    return system, user[:-1] if user.endswith("\n") else user
