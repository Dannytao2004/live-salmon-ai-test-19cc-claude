"""
LLM judge for the finance-leak responses (RUBRIC.md section 4.3).

Prompt versions, all read verbatim from RUBRIC.md: v3 (Appendix A, the
primary one, amended after the freeze), v1 (Appendix D, exactly as frozen,
for comparison) and v2 (Appendix E, superseded). The judge sees only the final report (`content`) of a response: not
the group, condition, model or data. Answers are saved to
results/judge/<version>/<key>.json; scores are computed from them later by
evaluate.py, never here.

Usage:
  python judge.py                                  # dry run (v3)
  python judge.py --live --limit 5                 # judge the next 5 responses (v3)
  python judge.py --live --version v1 --workers 4  # judge everything with v1
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import sys
import time
from collections import Counter

import labels
import run_models as rm
from labels import JUDGE_VERSIONS, RUBRIC_PATH, judge_path

JUDGE_PROVIDER = "deepseek"
JUDGE_MODEL_ID = "deepseek-v4-pro"
JUDGE_TEMPERATURE = 0
JUDGE_MAX_TOKENS = 2048

REASONS = {"measured_during_target_period", "reporting_delay", "other_timing"}
WEIGHTINGS = {"equal_weight", "weighted_by_reported_statistics", "single_signal", "other", "no_strategy"}
SELECTIONS = {"v3": {"specific", "generic", "says_absent", "none"},
              "v2": {"specific", "generic", "says_absent", "none"},
              "v1": {"specific", "generic", "none"}}
TIMING_GENERAL = {"raises", "says_absent", "none"}  # v2 and v3; v1 used a true/false flag


def rubric_blocks(heading: str) -> list:
    """Fenced code blocks inside one section of RUBRIC.md."""
    with open(RUBRIC_PATH, encoding="utf-8") as f:
        text = f.read()
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    section = text[start:] if end == -1 else text[start:end]
    return re.findall(r"```\n(.*?)\n```", section, re.S)


PROMPTS = {
    "v3": rubric_blocks("## Appendix A. Judge prompt (v3"),
    "v2": rubric_blocks("## Appendix E. Judge prompt v2"),
    "v1": rubric_blocks("## Appendix D. Judge prompt v1"),
}


def judge_payload(report: str, version: str) -> dict:
    system, user = PROMPTS[version]
    return {
        "model": JUDGE_MODEL_ID,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user.replace("{report}", report)},
        ],
        "temperature": JUDGE_TEMPERATURE,
        "max_tokens": JUDGE_MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def parse_answer(text: str, version: str):
    """Return (answer, problems). The judge is told to answer with JSON only;
    a surrounding code fence is tolerated."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None, ["no JSON object in judge output"]
    try:
        answer = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return None, [f"invalid JSON: {e}"]

    problems = []
    flags = answer.get("timing_flags")
    if not isinstance(flags, list):
        problems.append("timing_flags is not a list")
    else:
        for flag in flags:
            if not isinstance(flag, dict) or not flag.get("variable"):
                problems.append(f"timing flag without variable: {flag}")
            elif flag.get("reason") not in REASONS:
                problems.append(f"unknown timing reason: {flag.get('reason')}")
    if version in ("v2", "v3") and answer.get("timing_general") not in TIMING_GENERAL:
        problems.append(f"unknown timing_general: {answer.get('timing_general')}")
    if version == "v1" and not isinstance(answer.get("generic_timing_concern"), bool):
        problems.append("generic_timing_concern is not true/false")
    if answer.get("selection") not in SELECTIONS[version]:
        problems.append(f"unknown selection: {answer.get('selection')}")
    if answer.get("strategy_weighting") not in WEIGHTINGS:
        problems.append(f"unknown strategy_weighting: {answer.get('strategy_weighting')}")
    if not isinstance(answer.get("mentions_out_of_sample"), bool):
        problems.append("mentions_out_of_sample is not true/false")
    return answer, problems


def judge_one(key: str, version: str) -> dict:
    with open(os.path.join(labels.RAW_RESULTS_DIR, f"{key}.json"), encoding="utf-8") as f:
        report = json.load(f)["content"]
    started = dt.datetime.now(dt.timezone.utc)
    t0 = time.monotonic()
    try:
        out = rm.send(JUDGE_PROVIDER, judge_payload(report, version))
    except Exception as e:  # recorded; the batch keeps going
        out = {"errors": [f"{type(e).__name__}: {e}"]}
    answer, problems = parse_answer(out.get("content"), version) if out.get("http_status") == 200 else (None, [])
    if answer is not None and not problems:
        status = "success"
    elif answer is not None:
        status = "invalid"
    else:
        status = "error"
    cost, period = rm.estimate_cost(JUDGE_MODEL_ID, out.get("usage"), started)

    record = {
        "key": key,
        "judge_prompt_version": version,
        "judge_model_id": JUDGE_MODEL_ID,
        "request": out.get("request"),
        "started_at": started.isoformat(timespec="seconds"),
        "latency_s": round(time.monotonic() - t0, 1),
        "status": status,
        "http_status": out.get("http_status"),
        "attempts": out.get("attempts"),
        "errors": out.get("errors", []) + problems,
        "finish_reason": out.get("finish_reason"),
        "system_fingerprint": out.get("system_fingerprint"),
        "usage": out.get("usage"),
        "price_period": period,
        "cost_usd_estimate": cost,
        "judge_output": out.get("content"),
        "answer": answer,
    }
    os.makedirs(os.path.dirname(judge_path(key, version)), exist_ok=True)
    with open(judge_path(key, version), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return record


def judged_status(key: str, version: str):
    if not os.path.exists(judge_path(key, version)):
        return None
    with open(judge_path(key, version), encoding="utf-8") as f:
        return json.load(f).get("status")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="actually call the judge (costs money)")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--keys", nargs="+", help="judge only these response keys")
    parser.add_argument("--version", choices=JUDGE_VERSIONS, default="v3", help="judge prompt version")
    args = parser.parse_args()

    keys = args.keys or sorted(n[:-5] for n in os.listdir(labels.RAW_RESULTS_DIR) if n.endswith(".json"))
    todo = [k for k in keys if judged_status(k, args.version) != "success"]
    done = len(keys) - len(todo)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(keys)} responses, {done} already judged, "
          f"{len(todo)} to judge with prompt {args.version} on {JUDGE_MODEL_ID} (temperature {JUDGE_TEMPERATURE}, non-thinking)")
    if not args.live:
        system, user = PROMPTS[args.version]
        print(f"Judge prompt {args.version}: system {len(system)} chars; user template {len(user)} chars "
              f"(read from {os.path.basename(RUBRIC_PATH)})")
        return

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(judge_one, k, args.version) for k in todo]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            rec = fut.result()
            records.append(rec)
            u = rec["usage"] or {}
            print(f"[{i}/{len(todo)}] {rec['key']}: {rec['status']} prompt={u.get('prompt_tokens')} "
                  f"completion={u.get('completion_tokens')} {rec['latency_s']}s cost~${rec['cost_usd_estimate']}"
                  + (f" errors={rec['errors']}" if rec["status"] != "success" else ""))
    print(f"Done: {dict(Counter(r['status'] for r in records))}, "
          f"cost~${sum(r['cost_usd_estimate'] or 0 for r in records):.4f}")


if __name__ == "__main__":
    main()
