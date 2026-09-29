# The Streamlit era

Documents from the first lit-storm, a Streamlit app on Supabase
(`frontend/demo_light/`, `deploy/`). It was replaced by the web app in
`server/`, `web/` and `stack/`, and removed on 2026-09-30. Nothing had real
users; its reports were exported as HTML outside the repository.

Kept for what they record, not as instructions: paths and commands in them
point at files that no longer exist. The code itself is in git history, for
example:

```bash
git log --diff-filter=D --stat -- frontend/demo_light
```

| File | What it was |
| --- | --- |
| `TROUBLESHOOTING.md` | Symptom-to-fix guide for the Streamlit app (Thai) |
| `lit-storm.architecture.*` | Architecture diagram of the Streamlit app and its framed siblings |
| `REPORT_handoff_2026-09-20.md` | Handoff report written before the web-app rebuild |
