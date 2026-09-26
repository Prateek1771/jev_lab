Filters a **big tool output** before an agent's LLM reads it (context pollution). A GitHub issues list (30 issues)
or a CI log (26 lines) is split into items in code, and Jev judges **each item on its own**, all in parallel:
is this item needed to answer the question? Only the kept items reach the answer. Against it: **sending the whole
output**, an **LLM that summarizes first**, and a **keyword filter** (grep, $0). The same model answers in every
variant, and Jev's grader scores every answer. Traced.
**Measured:** pass rate, cost per passing answer, **tokens given to the answer**, and item precision and recall.

## With Jev
```mermaid
flowchart TD
    Q["question + tool output"] --> load["load node<br/>code: split into items"]
    load -->|"Send × items, in parallel"| jev_judge["jev_judge node<br/>ONE item per call:<br/>needed? (Noul)"]
    jev_judge --> jev_answer["jev_answer node<br/>keep P ≥ 0.5, answer from them"]
    jev_answer --> G["Jev grader + rubric<br/>precision / recall vs gold items"]
```

## Without Jev
```mermaid
flowchart LR
    Q["question + tool output"] --> load["load node"]
    load --> everything["everything node<br/>all items to the answer"]
    load --> keyword_filter["keyword_filter node<br/>items sharing a word, $0"]
    load --> llm_summary["llm_summary node<br/>LLM summarizes all items,<br/>answer reads the summary"]
    everything --> G["same answer model · same grader"]
    keyword_filter --> G
    llm_summary --> G
```
