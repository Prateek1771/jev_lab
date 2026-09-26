"""Jev Lab: one Streamlit app, one page per numbered project folder."""

import json
from pathlib import Path

import streamlit as st

from config import settings
from core.projects import discover
from core.ui import render_about, render_batch, render_result

IDS = discover()   # {"01": module, ...}
PROJECTS = {m.TITLE: m for m in IDS.values()}
NN = {m.TITLE: nn for nn, m in IDS.items()}

st.set_page_config(page_title="Jev Lab", layout="wide")
st.title("Jev Lab")

# ?p=NN picks the project, so the web UI's toggle can open the same one here; the URL follows the radio back.
wanted = st.query_params.get("p")
title = st.sidebar.radio("Project", list(PROJECTS), index=list(IDS).index(wanted) if wanted in IDS else 0)
project, nn = PROJECTS[title], NN[title]
st.query_params["p"] = nn
st.sidebar.divider()
st.sidebar.link_button("Open in the new UI ↗", f"{settings.WEB_UI_URL}/p/{nn}", use_container_width=True)
st.sidebar.caption("The same project in the Next.js UI. Start both with `uv run python scripts/dev.py`.")
st.sidebar.caption(
    "**Unofficial.** Independent tests by Prateek Hitli ([prateekhitli.dev](https://prateekhitli.dev)), not affiliated with "
    "TypeSafe AI or Jev. Every run used his own OpenRouter API key, with OpenRouter as the provider for the Jev model."
)
st.header(project.TITLE)
st.caption(f"Jev primitive: {project.PRIMITIVE}")
render_about(Path(project.__file__).parent / "about.md")

single, dataset = st.tabs(["Single example", f"Dataset ({len(project.DATASET)} labeled)"])

with single:
    example = st.selectbox("Example", list(project.EXAMPLES))
    value = project.EXAMPLES[example]
    structured_input = isinstance(value, dict)   # projects whose input is more than one message (04+)
    text = st.text_area("Input (JSON)" if structured_input else "Input",
                        json.dumps(value, indent=2) if structured_input else value,
                        height=220 if structured_input else 120)

    if st.button("Run experiment", type="primary"):
        try:
            inp = json.loads(text) if structured_input else text
        except json.JSONDecodeError as e:
            st.error(f"Input is not valid JSON: {e}")   # show it; never send a half-edited input
        else:
            with st.spinner("Calling Jev and the baselines..."):
                try:
                    st.session_state["result"] = (project.TITLE, project.run_experiment(inp))
                except Exception as e:   # an upstream 5xx or a dropped connection: say so, don't crash the page
                    st.error(f"The run failed ({type(e).__name__}): {str(e).splitlines()[0][:200]}. "
                             "Nothing was saved; run it again.")

    # Streamlit reruns this whole file on every click. Results live in session_state
    # so touching a widget does not spend money calling the APIs again.
    saved = st.session_state.get("result")
    if saved and saved[0] == project.TITLE:
        render_result(saved[1])

with dataset:
    st.caption(f"Runs every row one at a time: {len(project.DATASET)} rows × every variant, all paid calls. "
               "Rows run sequentially so latency measures the model, not a traffic jam.")
    if st.button("Run dataset", type="primary"):
        bar = st.progress(0.0, text="starting")
        rows = []
        for i, item in enumerate(project.DATASET):
            row = {"text": item["text"], "expected": item["label"], "result": None, "error": None}
            try:
                row["result"] = project.run_experiment(item.get("input", item["text"]))
            except Exception as e:   # one failed row must not throw away the rows already paid for
                row["error"] = f"{type(e).__name__}: {e}"[:300]
            rows.append(row)
            bar.progress((i + 1) / len(project.DATASET), text=f"{i + 1}/{len(project.DATASET)}")
        st.session_state["batch"] = (project.TITLE, rows)

    saved = st.session_state.get("batch")
    if saved and saved[0] == project.TITLE:
        render_batch(saved[1], project.LABELS, getattr(project, "SWEEP", None), key=project.TITLE,
                     safety_spec=getattr(project, "SAFETY", None))
