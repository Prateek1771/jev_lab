"""Every project's dataset.json must be usable before anyone pays to run it."""

import importlib
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PROJECTS = [p.name for p in sorted((ROOT / "projects").glob("[0-9][0-9]_*")) if (p / "experiment.py").exists()]


@pytest.mark.parametrize("name", PROJECTS)
def test_dataset_matches_labels(name):
    m = importlib.import_module(f"projects.{name}.experiment")
    labels = [row["label"] for row in m.DATASET]
    assert set(labels) <= set(m.LABELS), f"typo'd or unknown labels: {set(labels) - set(m.LABELS)}"
    counts = Counter(labels)
    assert all(counts[l] >= 2 for l in m.LABELS), f"every label needs examples: {counts}"
    texts = [row["text"].strip() for row in m.DATASET]
    assert all(texts) and len(texts) == len(set(texts)), "empty or duplicate example"


@pytest.mark.parametrize("name", PROJECTS)
def test_about_has_both_diagrams_and_every_graph_node(name):
    """The page's wiring diagrams must match the real graph: rename a node, forget the diagram, fail here."""
    from core.ui import parse_about
    description, diagrams = parse_about((ROOT / "projects" / name / "about.md").read_text(encoding="utf-8"))
    assert description and [t for t, _ in diagrams] == ["With Jev", "Without Jev"]
    text = " ".join(body for _, body in diagrams)
    graph = importlib.import_module(f"projects.{name}.experiment").GRAPH.get_graph()
    missing = [n for n in graph.nodes if not n.startswith("__") and not re.search(rf"\b{n}\[", text)]
    assert not missing, f"graph nodes not drawn in about.md: {missing}"


@pytest.mark.parametrize("name", PROJECTS)
def test_rubrics_say_what_is_required(name):
    """Graded projects: every rubric starts with "Required:" and lists only what the task asks for. The real
    smoke test failed a correct 08 answer because its rubric also demanded a detail the question never asked."""
    m = importlib.import_module(f"projects.{name}.experiment")
    rubrics = [r["input"]["rubric"] for r in m.DATASET if isinstance(r.get("input"), dict) and "rubric" in r["input"]]
    rubrics += [e["rubric"] for e in m.EXAMPLES.values() if isinstance(e, dict) and "rubric" in e]
    assert all(r.startswith("Required: ") for r in rubrics), [r for r in rubrics if not r.startswith("Required: ")]


@pytest.mark.parametrize("name", PROJECTS)
def test_every_variant_has_a_display_title(name):
    """Found by clicking through 09 with Puppeteer: its columns were headed 'llm_rank' and 'retriever_order'.
    Every variant (Run-typed State key, or NODES entry), and needs a human title in core/ui.TITLES."""
    import typing
    from core.run import Run
    from core.ui import TITLES
    m = importlib.import_module(f"projects.{name}.experiment")
    # Run-typed State keys, plus NODES for projects whose agents keep dict progress in State (06),
    # or VARIANTS where the graph also has nodes that aren't variants (24: route, agent, answer)
    variants = {k for k, t in typing.get_type_hints(m.State).items() if t is Run} | set(
        getattr(m, "VARIANTS", None) or getattr(m, "NODES", {}))
    assert variants and not [v for v in variants if v not in TITLES], [v for v in variants if v not in TITLES]
