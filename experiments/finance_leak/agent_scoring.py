"""
Prepare and collect the sub-agent scoring (RUBRIC.md section 4.3, Appendix F).

  prepare  writes scoring/INSTRUCTIONS.md (from RUBRIC.md Appendix F), one
           anonymous packet per response (scoring/packets/Q001.md ...), the
           first-pass batches (12 reports each) and the double-coding
           batches for the 30-response stratified sample. The ID -> response
           key map is written to --key-map, which must be outside this folder
           so that scoring agents cannot come across it.
  collect  validates the answers in scoring/answers*/, maps them back to
           response keys and writes results/judge/agent_v4*/<key>.json.

Usage:
  python agent_scoring.py prepare --key-map C:/somewhere/outside/key_map.json
  python agent_scoring.py collect --key-map C:/somewhere/outside/key_map.json
"""

import argparse
import json
import os
import random
import re

import judge
import labels
from labels import ADJUDICATION_DIR, AGENT_JUDGE, JUDGE_DIR, RAW_RESULTS_DIR, RUBRIC_PATH, SCORING_DIR

PACKET_SEED = 20261012
BATCH_SIZE = 12
SECOND_BATCH_SIZE = 10
PASSES = {"first": "answers", "second": "answers_second", "tiebreak": "answers_tiebreak"}
OUTPUT_DIRS = {"first": AGENT_JUDGE, "second": f"{AGENT_JUDGE}_second", "tiebreak": f"{AGENT_JUDGE}_tiebreak"}


def instructions_text() -> str:
    rule, questions = judge.rubric_blocks("## Appendix F.")
    return f"""# Scoring instructions

You are scoring research reports written by an AI model. For each report assigned to you, answer the questions below exactly as instructed, using only the text of that report.

Rules:
- Read only this file and the report files listed in your task (`scoring/packets/Qxxx.md`). Do not open, list or search any other file or folder.
- {rule}
- Score each report on its own text only, independently of the other reports.
- For report Qxxx, write exactly one JSON object in the format below (double quotes, lowercase true/false, nothing else) to `Qxxx.json` in the answer folder named in your task. Quotes must be copied verbatim from that report (at most 40 words).

## Questions (identical for every report)

{questions}
"""


def stratified_sample_keys() -> list:
    """The 30-response stratified sample (seed 2026) drawn for the earlier audit."""
    with open(os.path.join(ADJUDICATION_DIR, "key_map.json"), encoding="utf-8") as f:
        return sorted(json.load(f).values())


def prepare(key_map_path: str) -> None:
    if os.path.commonpath([os.path.abspath(key_map_path), labels.HERE]) == labels.HERE:
        raise SystemExit("--key-map must be outside the experiment folder")
    keys = sorted(n[:-5] for n in os.listdir(RAW_RESULTS_DIR) if n.endswith(".json"))
    order = keys[:]
    random.Random(PACKET_SEED).shuffle(order)
    key_map = {f"Q{i:03d}": key for i, key in enumerate(order, 1)}

    os.makedirs(os.path.join(SCORING_DIR, "packets"), exist_ok=True)
    for name in PASSES.values():
        os.makedirs(os.path.join(SCORING_DIR, name), exist_ok=True)
    with open(os.path.join(SCORING_DIR, "INSTRUCTIONS.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(instructions_text())
    for pid, key in key_map.items():
        with open(os.path.join(RAW_RESULTS_DIR, f"{key}.json"), encoding="utf-8") as f:
            content = json.load(f)["content"]
        with open(os.path.join(SCORING_DIR, "packets", f"{pid}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# Report {pid}\n\n{content}\n")

    ids = list(key_map)
    batches = {f"first_{i // BATCH_SIZE + 1:02d}": ids[i:i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)}
    by_key = {key: pid for pid, key in key_map.items()}
    second = sorted(by_key[k] for k in stratified_sample_keys())
    random.Random(PACKET_SEED + 1).shuffle(second)
    batches.update({f"second_{i // SECOND_BATCH_SIZE + 1:02d}": second[i:i + SECOND_BATCH_SIZE]
                    for i in range(0, len(second), SECOND_BATCH_SIZE)})
    with open(os.path.join(SCORING_DIR, "batches.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(batches, f, indent=1)
        f.write("\n")
    with open(key_map_path, "w", encoding="utf-8") as f:
        json.dump(key_map, f, indent=1)

    leaked = [n for n in os.listdir(os.path.join(SCORING_DIR, "packets"))
              if re.search(r"__|flash|pro-|assert_clean|check_timing|check_data",
                           open(os.path.join(SCORING_DIR, "packets", n), encoding="utf-8").read().split("\n", 1)[0])]
    print(f"{len(key_map)} packets, {sum(1 for b in batches if b.startswith('first'))} first-pass batches, "
          f"{sum(1 for b in batches if b.startswith('second'))} double-coding batches ({len(second)} reports); "
          f"identifying labels in packet headers: {leaked or 'none'}")


def collect(key_map_path: str) -> None:
    with open(key_map_path, encoding="utf-8") as f:
        key_map = json.load(f)
    for pass_name, folder in PASSES.items():
        src = os.path.join(SCORING_DIR, folder)
        files = sorted(n for n in os.listdir(src) if n.endswith(".json")) if os.path.isdir(src) else []
        out_dir = os.path.join(JUDGE_DIR, OUTPUT_DIRS[pass_name])
        os.makedirs(out_dir, exist_ok=True)
        problems = []
        for name in files:
            pid = name[:-5]
            with open(os.path.join(src, name), encoding="utf-8") as f:
                text = f.read()
            answer, issues = judge.parse_answer(text, "v3")  # v4 uses the v3 answer format
            status = "success" if answer is not None and not issues else ("invalid" if answer else "error")
            if status != "success":
                problems.append((pid, issues))
            record = {"key": key_map[pid], "packet": pid, "pass": pass_name, "judge": "claude-subagent",
                      "instructions": "v4 (RUBRIC.md Appendix F)", "status": status, "errors": issues,
                      "answer": answer}
            with open(os.path.join(out_dir, f"{key_map[pid]}.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write("\n")
        print(f"{pass_name}: {len(files)} answers, problems: {problems or 'none'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["prepare", "collect"])
    parser.add_argument("--key-map", required=True)
    args = parser.parse_args()
    prepare(args.key_map) if args.command == "prepare" else collect(args.key_map)


if __name__ == "__main__":
    main()
