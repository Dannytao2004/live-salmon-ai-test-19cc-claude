"""
Send the frozen prompts to the models and save every response. This is the
only script in the experiment that costs money.

Safety: nothing is sent unless --live is given; without it the script does a
dry run that reads every prompt file and prints the plan. API keys are read
only from this experiment's .env file (copy .env.example), never from global
environment variables, and are never printed or written anywhere else.

Each call is saved to results/raw/<group>__<condition>__<model>__run<k>.json
with the full answer, the reasoning text (if any), finish_reason, usage and an
estimated cost. Calls already saved as "success" or "truncated" are skipped,
so an interrupted run can simply be restarted.

Usage:
  python run_models.py                                   # dry run, full plan
  python run_models.py --live --groups B1 --conditions plain --models flash-think --runs 1
  python run_models.py --summary                         # usage and cost of saved results
"""

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import random
import time
from collections import Counter, defaultdict

import httpx

import labels
from labels import (
    CONDITIONS, GROUPS, HERE, MODELS, RUNS_PER_CELL,
    prompt_path, read_prompt, result_key, result_path,
)

# ---------------------------------------------------------------------------
# Providers. "openai_chat" covers any OpenAI-compatible chat completions API.
# Only deepseek is used so far; the others are reserved so that adding a model
# later only needs an entry in labels.MODELS (and, for anthropic, an adapter).
# ---------------------------------------------------------------------------
PROVIDERS = {
    "deepseek": {"style": "openai_chat", "url": "https://api.deepseek.com/chat/completions",
                 "models_url": "https://api.deepseek.com/models", "key_env": "DEEPSEEK_API_KEY"},
    # Reserved, not exercised yet:
    "openrouter": {"style": "openai_chat", "url": "https://openrouter.ai/api/v1/chat/completions",
                   "key_env": "OPENROUTER_KEY"},
    "openai": {"style": "openai_chat", "url": "https://api.openai.com/v1/chat/completions",
               "key_env": "OPENAI_API_KEY"},
    "anthropic": {"style": "anthropic_messages", "url": "https://api.anthropic.com/v1/messages",
                  "key_env": "ANTHROPIC_API_KEY"},
}

TEMPERATURE = 0.7                        # upstream value; DeepSeek ignores it in thinking mode
MAX_TOKENS = {True: 65536, False: 8192}  # thinking / non-thinking: DeepSeek's defaults, made explicit
REASONING_EFFORT = "high"                # DeepSeek's default for thinking mode, made explicit
RUN_ORDER_SEED = 2026                    # calls are sent in a fixed shuffled order, so that any drift
                                         # in the provider over time is spread across groups and models
TIMEOUT = httpx.Timeout(900.0, connect=30.0)
MAX_ATTEMPTS = 3
RETRY_STATUS = {429, 500, 502, 503, 504}
DONE_STATUSES = {"success", "truncated"}

# USD per 1M tokens as (cache hit, cache miss, output). Source:
# https://api-docs.deepseek.com/quick_start/pricing, checked 2026-10-11.
# Peak = 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday; otherwise off-peak.
# (Chinese public holidays are also off-peak; ignored here, which can only
# overstate the cost.)
PRICES = {
    "deepseek-flash": {"offpeak": (0.003, 0.15, 0.60), "peak": (0.006, 0.30, 1.20)},
    "deepseek-v4-pro": {"offpeak": (0.022, 0.66, 1.98), "peak": (0.044, 1.32, 3.96)},
}


# ---------------------------------------------------------------------------
# Adapters: build a request payload, parse a response
# ---------------------------------------------------------------------------
def openai_chat_payload(model: str, system: str, user: str) -> dict:
    spec = MODELS[model]
    payload = {
        "model": spec["model_id"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS[spec["thinking"]],
        "stream": False,
    }
    if spec["provider"] == "deepseek":
        payload["thinking"] = {"type": "enabled" if spec["thinking"] else "disabled"}
        if spec["thinking"]:
            payload["reasoning_effort"] = REASONING_EFFORT
    return payload


def parse_openai_chat(data: dict) -> dict:
    choice = data["choices"][0]
    message = choice.get("message") or {}
    return {
        "content": message.get("content"),
        "reasoning_content": message.get("reasoning_content"),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage") or {},
        "response_model": data.get("model"),
        "response_id": data.get("id"),
        "system_fingerprint": data.get("system_fingerprint"),
    }


ADAPTERS = {"openai_chat": (openai_chat_payload, parse_openai_chat)}


def load_project_env() -> dict:
    """Parse this project's .env file (NAME=value lines; # comments, optional
    quotes and a leading 'export ' are allowed)."""
    values = {}
    if not os.path.exists(labels.ENV_PATH):
        return values
    with open(labels.ENV_PATH, encoding="utf-8-sig") as f:  # -sig: tolerate a BOM from Notepad
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = (part.strip() for part in line.split("=", 1))
            if name.startswith("export "):
                name = name[len("export "):].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[name] = value
    return values


def get_api_key(name: str):
    """API key read only from this project's .env, never from global
    environment variables, so keys from other projects cannot be picked up.
    Never printed or saved."""
    return load_project_env().get(name) or None


def call_model(model: str, system: str, user: str) -> dict:
    spec = MODELS[model]
    provider = PROVIDERS[spec["provider"]]
    if provider["style"] not in ADAPTERS:
        raise NotImplementedError(f"API style '{provider['style']}' is reserved but not implemented yet")
    key = get_api_key(provider["key_env"])
    if not key:
        raise RuntimeError(f"{provider['key_env']} is not set in {labels.ENV_PATH}")

    build, parse = ADAPTERS[provider["style"]]
    payload = build(model, system, user)
    out = {"request": {k: v for k, v in payload.items() if k != "messages"}, "errors": []}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        out["attempts"] = attempt
        try:
            resp = httpx.post(provider["url"], json=payload, headers=headers, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            out["errors"].append(f"attempt {attempt}: {type(e).__name__}: {e}")
        else:
            out["http_status"] = resp.status_code
            if resp.status_code == 200:
                return {**out, **parse(resp.json())}
            out["errors"].append(f"attempt {attempt}: HTTP {resp.status_code}: {resp.text[:500]}")
            if resp.status_code not in RETRY_STATUS:
                return out
        if attempt < MAX_ATTEMPTS:
            time.sleep(10 * attempt)
    return out


# ---------------------------------------------------------------------------
# One call -> one result file
# ---------------------------------------------------------------------------
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def price_period(t: dt.datetime) -> str:
    if t.weekday() >= 5:
        return "offpeak"
    return "peak" if 1 <= t.hour < 4 or 6 <= t.hour < 10 else "offpeak"


def estimate_cost(model_id: str, usage: dict, started: dt.datetime):
    if model_id not in PRICES or not usage:
        return None, None
    period = price_period(started)
    hit_price, miss_price, out_price = PRICES[model_id][period]
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
    cost = (hit * hit_price + miss * miss_price + usage.get("completion_tokens", 0) * out_price) / 1e6
    return round(cost, 6), period


def run_one(group: str, condition: str, model: str, run: int) -> dict:
    system, user = read_prompt(group, condition)
    started = dt.datetime.now(dt.timezone.utc)
    t0 = time.monotonic()
    try:
        out = call_model(model, system, user)
    except Exception as e:  # recorded in the result file; the batch keeps going
        out = {"errors": [f"{type(e).__name__}: {e}"]}
    latency = round(time.monotonic() - t0, 1)

    if out.get("http_status") == 200 and out.get("finish_reason") == "length":
        status = "truncated"
    elif out.get("http_status") == 200 and out.get("finish_reason") == "stop" and out.get("content"):
        status = "success"
    else:
        status = "error"
    spec = MODELS[model]
    cost, period = estimate_cost(spec["model_id"], out.get("usage"), started)

    record = {
        "key": result_key(group, condition, model, run),
        "group": group,
        "condition": condition,
        "model": model,
        "run": run,
        "provider": spec["provider"],
        "model_id": spec["model_id"],
        "thinking": spec["thinking"],
        "prompt_file": os.path.relpath(prompt_path(group, condition), HERE).replace(os.sep, "/"),
        "system_sha256": sha256(system),
        "user_sha256": sha256(user),
        "started_at": started.isoformat(timespec="seconds"),
        "latency_s": latency,
        "status": status,
        "http_status": out.get("http_status"),
        "attempts": out.get("attempts"),
        "errors": out.get("errors", []),
        "request": out.get("request"),
        "response_model": out.get("response_model"),
        "response_id": out.get("response_id"),
        "system_fingerprint": out.get("system_fingerprint"),
        "finish_reason": out.get("finish_reason"),
        "usage": out.get("usage"),
        "price_period": period,
        "cost_usd_estimate": cost,
        "content": out.get("content"),
        "reasoning_content": out.get("reasoning_content"),
    }
    os.makedirs(labels.RAW_RESULTS_DIR, exist_ok=True)
    with open(result_path(group, condition, model, run), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return record


# ---------------------------------------------------------------------------
# Plan, dry run, live run, summary
# ---------------------------------------------------------------------------
def saved_status(group, condition, model, run):
    path = result_path(group, condition, model, run)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("status")


def build_plan(args) -> list:
    for name, chosen, allowed in (("group", args.groups, GROUPS), ("condition", args.conditions, CONDITIONS),
                                  ("model", args.models, MODELS)):
        unknown = set(chosen) - set(allowed)
        if unknown:
            raise SystemExit(f"unknown {name}(s): {sorted(unknown)}; allowed: {list(allowed)}")
    tasks = [(g, c, m, r) for m in args.models for g in args.groups for c in args.conditions for r in args.runs]
    random.Random(RUN_ORDER_SEED).shuffle(tasks)
    return tasks[: args.limit] if args.limit else tasks


def dry_run(tasks: list) -> None:
    for g, c, _, _ in tasks:
        read_prompt(g, c)  # raises if any prompt file is missing or malformed
    todo = [t for t in tasks if saved_status(*t) not in DONE_STATUSES]
    print(f"DRY RUN (nothing sent). Planned calls: {len(tasks)}; already done: {len(tasks) - len(todo)}; "
          f"to send: {len(todo)}")
    for model, n in Counter(t[2] for t in todo).items():
        spec = MODELS[model]
        provider = PROVIDERS[spec["provider"]]
        key_state = "set" if get_api_key(provider["key_env"]) else "NOT SET"
        print(f"  {model:14s} {spec['provider']}/{spec['model_id']} thinking={spec['thinking']}: "
              f"{n} calls; {provider['key_env']} {key_state} in .env")
    if todo:
        g, c, m, r = todo[0]
        system, user = read_prompt(g, c)
        payload = ADAPTERS[PROVIDERS[MODELS[m]["provider"]]["style"]][0](m, system, user)
        shown = {k: v for k, v in payload.items() if k != "messages"}
        print(f"First call: {result_key(g, c, m, r)}")
        print(f"  payload (messages omitted): {json.dumps(shown)}")
        print(f"  messages: system {len(system)} chars, user {len(user)} chars, from {prompt_path(g, c)}")
        print(f"  would save to: {result_path(g, c, m, r)}")


def live_run(tasks: list, workers: int) -> None:
    todo = [t for t in tasks if saved_status(*t) not in DONE_STATUSES]
    print(f"LIVE: sending {len(todo)} calls ({len(tasks) - len(todo)} already done), workers={workers}")
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, *t): t for t in todo}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            rec = fut.result()
            records.append(rec)
            u = rec["usage"] or {}
            reasoning = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
            print(f"[{i}/{len(todo)}] {rec['key']}: {rec['status']} finish={rec['finish_reason']} "
                  f"prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')} "
                  f"reasoning={reasoning} {rec['latency_s']}s cost~${rec['cost_usd_estimate']}"
                  + (f" errors={rec['errors']}" if rec["status"] == "error" else ""))
    summarize(records)


def list_models() -> None:
    """Ask each provider used in labels.MODELS which model ids this key can use (free)."""
    for name in sorted({spec["provider"] for spec in MODELS.values()}):
        provider = PROVIDERS[name]
        key = get_api_key(provider["key_env"])
        if not key:
            print(f"{name}: {provider['key_env']} not set in .env")
            continue
        resp = httpx.get(provider["models_url"], headers={"Authorization": f"Bearer {key}"}, timeout=30.0)
        if resp.status_code != 200:
            print(f"{name}: HTTP {resp.status_code}: {resp.text[:300]}")
            continue
        available = {m["id"]: m for m in resp.json().get("data", [])}
        print(f"{name}: {len(available)} model(s) available to this key")
        for model_id, m in sorted(available.items()):
            print(f"  {model_id}  (owned_by={m.get('owned_by')})")
        configured = sorted({s["model_id"] for s in MODELS.values() if s["provider"] == name})
        for model_id in configured:
            print(f"  configured in labels.MODELS: {model_id} -> {'available' if model_id in available else 'NOT AVAILABLE'}")


def load_results() -> list:
    if not os.path.isdir(labels.RAW_RESULTS_DIR):
        return []
    records = []
    for name in sorted(os.listdir(labels.RAW_RESULTS_DIR)):
        if name.endswith(".json"):
            with open(os.path.join(labels.RAW_RESULTS_DIR, name), encoding="utf-8") as f:
                records.append(json.load(f))
    return records


def summarize(records: list) -> None:
    by_model = defaultdict(list)
    for rec in records:
        by_model[rec["model"]].append(rec)
    print(f"Summary of {len(records)} result(s):")
    for model, recs in sorted(by_model.items()):
        usage = [r["usage"] or {} for r in recs]
        statuses = Counter(r["status"] for r in recs)
        cost = sum(r["cost_usd_estimate"] or 0 for r in recs)
        print(f"  {model:14s} n={len(recs)} {dict(statuses)} "
              f"prompt={sum(u.get('prompt_tokens', 0) for u in usage)} "
              f"completion={sum(u.get('completion_tokens', 0) for u in usage)} "
              f"reasoning={sum((u.get('completion_tokens_details') or {}).get('reasoning_tokens', 0) for u in usage)} "
              f"cost~${cost:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="actually call the APIs (costs money)")
    parser.add_argument("--summary", action="store_true", help="summarize saved results and exit")
    parser.add_argument("--list-models", action="store_true", help="list model ids available to the key (free)")
    parser.add_argument("--groups", nargs="+", default=list(GROUPS))
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--runs", nargs="+", type=int, default=list(range(1, RUNS_PER_CELL + 1)))
    parser.add_argument("--limit", type=int, default=0, help="send at most this many calls")
    parser.add_argument("--workers", type=int, default=1, help="parallel requests")
    args = parser.parse_args()

    if args.summary:
        summarize(load_results())
        return
    if args.list_models:
        list_models()
        return
    tasks = build_plan(args)
    if args.live:
        live_run(tasks, args.workers)
    else:
        dry_run(tasks)


if __name__ == "__main__":
    main()
