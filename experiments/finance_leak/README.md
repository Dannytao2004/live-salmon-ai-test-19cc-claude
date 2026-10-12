# finance_leak: look-ahead traps for AI scientists

A finance variant of the Live Salmon Test. Synthetic monthly stock panels with a known
data-generating process each hide one classic look-ahead trap (a same-period variable, a
reporting-lag misalignment, or survivorship selection); an AI "quantitative researcher" gets a
text summary and must find signals, propose a strategy and write a short paper. Results:
**[REPORT.md](REPORT.md)**. Scoring rules, pre-registered and with every later change recorded:
**[RUBRIC.md](RUBRIC.md)**.

Nothing outside this folder was modified.

## Layout

| Path | What it is |
|---|---|
| `labels.py` | single source of names: groups, traps, roles, prompt conditions, models, output fields, file paths |
| `generate_data.py` | builds the 7 panels, data dictionaries and `data/ground_truth.json` |
| `sanity_check.py` | checks from the CSVs alone that each trap behaves as designed (`sanity/`) |
| `build_prompts.py` | builds and checks the 28 frozen prompts (`prompts/<group>__<condition>.txt`) |
| `run_models.py` | sends the frozen prompts (dry run unless `--live`); saves `results/raw/` |
| `judge.py` | DeepSeek comparison judge, prompts read verbatim from `RUBRIC.md` (`results/judge/v1`, `v3`) |
| `agent_scoring.py` | prepares anonymous packets for the Claude sub-agent judge and collects their answers (`scoring/`, `results/judge/agent_v4*/`) |
| `adjudication/` | the earlier 30-response audit with the v3 questions (record only; see `RUBRIC.md` section 7) |
| `evaluate.py` | all metrics and tables (`results/scores/`) |
| `make_figures.py` | the three figures and their data (`figures/`) |
| `report_numbers.py` | every number cited in `REPORT.md` (`results/scores/report_numbers.json`) |
| `.env.example` | template for the git-ignored `.env` that holds API keys |

## Reproducing

From the repository root, `uv sync --locked --python 3.12`, then in this folder:

```bash
python generate_data.py      # rebuilds data/panel_*.csv (git-ignored); other outputs are byte-identical
python sanity_check.py       # 19 checks, all PASS
python build_prompts.py      # rewrites prompts/; git diff should be empty
python evaluate.py           # tables and judge reliability, offline
python make_figures.py       # figures, offline
python report_numbers.py     # numbers cited in REPORT.md, offline
```

The last three rebuild every table, figure and number in `REPORT.md` from the committed
responses and judge answers, without any API call.

Re-running the experiment itself needs API access (copy `.env.example` to `.env` and fill in
`DEEPSEEK_API_KEY`; keys are read only from that file):

```bash
python run_models.py                     # dry run: 336 planned calls
python run_models.py --live --workers 4  # about $2 at DeepSeek off-peak prices
python judge.py --live --workers 4               # comparison judge, prompt v3
python judge.py --live --version v1 --workers 4  # comparison judge, prompt as frozen
```

The primary judge is a set of Claude sub-agents: `python agent_scoring.py prepare --key-map
<path outside this folder>` writes the anonymous packets and batches; each agent follows
`scoring/INSTRUCTIONS.md` for its batch; `python agent_scoring.py collect --key-map <same path>`
maps the answers back. Sub-agent scoring is not deterministic; the committed answers are the
record.

On Windows set `PYTHONUTF8=1` so that console output does not fail on non-ASCII characters.

## Credits

Designed, run and analysed by Haojie (Danny) Tao. The code, the analysis and this write-up were
developed together with Claude (Anthropic) in Claude Code, and the primary scoring was done by
Claude sub-agents (`REPORT.md` section 3).
