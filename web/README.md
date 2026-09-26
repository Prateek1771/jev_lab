# Jev Lab — web UI

> **Unofficial.** Independent tests by Prateek Hitli ([prateekhitli.dev](https://prateekhitli.dev)), not affiliated with or endorsed by TypeSafe AI or Jev. Every run used his own OpenRouter API key, with OpenRouter as the provider for the Jev model (`typesafe/jev-1.13`) and the baseline LLMs.

Next.js front end for Jev Lab, in the TypeSafe/Jev design language (`D:\personal\jev\jev_ui\DESIGN.md`).
It talks to the Python API in `../api`, which serves the same project contract the Streamlit app uses.

## Run it

One command, from the repo root (Ctrl+C stops everything):

```powershell
uv run python scripts/dev.py              # both UIs: API :8000, this UI :3737, Streamlit :8501
uv run python scripts/dev.py --ui web     # just this UI (and the API it needs)
uv run python scripts/dev.py --ui streamlit
```

First time only: run `npm install` in `web/` (npm's cache is on D:, see `.npmrc`). Then open http://localhost:3737.
- Port 3000 is taken by the local Langfuse container, and 3100 by WSL, hence 3737.
- Point the UI at another API with `JEV_API_URL`, and at another Streamlit with `NEXT_PUBLIC_STREAMLIT_URL`.

## Switching UIs

- **The nav toggle "New UI | Streamlit"** opens the same experiment in Streamlit (`:8501/?p=NN`). Its dot is green when Streamlit is running (checked on Streamlit's `/_stcore/health`). When it isn't, clicking shows the command to start it.
- **In Streamlit, "Open in the new UI ↗"** in the sidebar comes back to `/p/NN`. `?p=NN` selects the project, and the URL follows the sidebar, so links survive a reload. `WEB_UI_URL` in `config/settings.py` (env-overridable) says where the new UI lives.

## Dataset progress and downloads

- **Progress:** the Dataset tab shows the row running now, its text, rows done, elapsed time and an ETA. The API sends a `working` event before each row and a `row` event after it.
  - The stream carries `Cache-Control: no-transform`. Without it, Next's proxy gzips the response, and gzip holds every event until the run ends; that is why the counter used to sit at 0/24.
- **The Download tab** (4th tab) shows every system prompt the experiment sends: Jev questions with their criteria, LLM system prompts, tool lists and output schemas.
  - Identical calls are merged, with a "×N per run" count.
  - One button at the bottom downloads everything as a zip: an **Excel workbook** (sheets: Dataset, Examples, System prompts), `prompts.json`, the dataset as CSV and JSON, and the project's code and `about.md`.
  - A text link gets just the workbook.
- **How the prompts are captured:** many are built inside the code at call time, so `uv run python scripts/capture_prompts.py [NN]` runs each project's first example for real and records the JSON body of every request to OpenRouter, never the headers. It writes `projects/NN_*/prompts.json` (about $0.03 for all 24).
  - A test fails if any project lacks the file or if one contains a key-like string.
- **Endpoints:** `GET /api/projects/NN/prompts`, and `GET /api/projects/NN/download/{bundle.zip|workbook.xlsx|dataset.csv|data.json}`.

## What's where

| Path | What |
|---|---|
| `app/page.tsx` | Overview: 24-experiment accuracy-vs-cost scatter, headline numbers, the experiment table |
| `app/p/[nn]/page.tsx` | One experiment: description, With/Without Jev diagrams, the Run / Dataset / History tabs |
| `components/project/*` | `RunTab` (live example), `DatasetTab` (streamed full run), `HistoryTab` (saved runs, diff), `ReportView`, `VariantCard` |
| `components/charts.tsx` | recharts: log-scale cost scatter, value bars, threshold sweep |
| `components/Mermaid.tsx` | client-side mermaid, themed like the instrument panels |
| `app/globals.css` | design tokens (DESIGN.md §9) mapped into Tailwind v4 |
| `lib/types.ts` | mirrors `api/main.py` responses |

Import earlier script runs into History with `uv run python scripts/import_runs.py <folder> <date> <label>`.
