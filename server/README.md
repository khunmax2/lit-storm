# server

The API and Worker of the web app that replaces Streamlit
([plan](../docs/web-app-implementation-plan.md), [ADRs](../docs/adr/)).
So far: step 1 — an Engine run outside Streamlit, in a process of its own,
turned into `report.json` and exported.

```bash
uv sync --extra pdf
uv run pytest
```

`pytest` skips the PDF test unless it has a Chromium. On Windows, Edge will do:
`LITSTORM_PDF_BROWSER_CHANNEL=msedge uv run pytest`. Elsewhere,
`uv run playwright install chromium` first and set `LITSTORM_PDF_TEST=1`.

One Run by hand (costs money; keys come from the environment only):

```bash
LITSTORM_LLM_API_KEY=... uv run litstorm run --topic "Songkran" --language th \
    --llm-provider gemini --model gemini-flash-latest --search arxiv --out runs/demo
uv run litstorm export runs/demo --format pdf --evidence -o demo.pdf
```

| path | what it is |
|---|---|
| `engines/base.py` | what an Engine is given and returns |
| `engines/storm/` | STORM: providers, language switch, stages, `report.json` |
| `engines/fake.py` | an Engine a test can script |
| `runner/supervisor.py` | one Run in one process: cancel, deadline, heartbeat |
| `runner/child.py` | the process a Run lives in |
| `report.py` | the `report.json` shape and its checks |
| `visuals.py` | a report's figures: facts from its evidence, the model's blocks, the checks |
| `outcomes.py` | why a Run ended, and whether quota comes back |
| `render/` | HTML, Markdown and PDF from `report.json`; the interactive page with figures (`interactive.py`, ECharts vendored in `render/vendor/`) |
