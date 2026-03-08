# GAIA Web Eval

This repo now includes a small GAIA-style public web evaluation harness that
drives the real chat HTTP API and captures tool traces from the SSE stream.

Default case catalog:

- `scripts/eval_cases/gaia_level1_web_cases.json`

Runner:

- `scripts/run_gaia_web_eval.py`

What it measures:

- final answer text
- tool-call counts for `web_search` and `read_webpage`
- `read_webpage` failure counts
- optional pass/fail for cases with reference answers
- raw per-case traces in a JSON report

Recommended first run:

```powershell
./venv/Scripts/python scripts/run_gaia_web_eval.py --scored-only
```

If you want to target a specific model:

```powershell
./venv/Scripts/python scripts/run_gaia_web_eval.py --model-id openai:gpt-4.1 --scored-only
```

If you want to run in project context and also enable the two web tools first:

```powershell
./venv/Scripts/python scripts/run_gaia_web_eval.py --context-type project --project-id <PROJECT_ID> --ensure-project-web-tools
```

Reports are written to `docs/eval/` as one JSON file and one markdown file per run.

Current bundled cases are intentionally small and biased toward:

- easy GAIA Level 1 public-web tasks
- tasks that mostly depend on `web_search` and `read_webpage`
- tasks that avoid attachments, OCR, audio, video, or code execution

This is meant to answer a narrow question first: can the current agent complete
multi-round web research tasks with the two web tools enabled?

