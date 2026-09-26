Decides **which retrieved chunks the answer may use**. A plain word-overlap retriever returns the top 6 chunks
from a 20-chunk help centre, noisy on purpose: a stale 2019 policy, a blog post, an injected instruction, internal
salaries. Jev judges **each chunk on its own** (useful, injection, sensitive: three Nouls), all in parallel, and a
policy keeps at most 4. The same model then answers from what was kept, and Jev grades every answer against a rubric.
**Measured:** pass rate, cost per passing answer, answer vs NO_ANSWER, and retrieval precision and recall.

## With Jev
```mermaid
flowchart TD
    Q["question"] --> retrieve["retrieve node<br/>top 6 by word overlap"]
    retrieve -->|"Send × 6, in parallel"| jev_judge["jev_judge node<br/>ONE chunk per call:<br/>useful · injection · sensitive (Noul)"]
    jev_judge --> jev_answer["jev_answer node"]
    jev_answer --> K{"policy.keep<br/>injection or sensitive → drop<br/>useful ≥ 0.5 → keep, max 4"}
    K -->|none kept| N["NO_ANSWER, no LLM call"]
    K -->|kept chunks| A["LLM answers from those chunks only"]
    A --> G["Jev grader + rubric"]
    N --> G
```

## Without Jev
```mermaid
flowchart LR
    Q["question"] --> retrieve["retrieve node<br/>same 6 chunks"]
    retrieve --> llm_filter["llm_filter node<br/>fast LLM sees ALL 6 in one prompt,<br/>returns the ids to keep"]
    retrieve --> all_chunks["all_chunks node<br/>plain RAG: keep all 6"]
    llm_filter --> A1["same LLM answers"]
    all_chunks --> A2["same LLM answers"]
    A1 --> G["same Jev grader + rubric"]
    A2 --> G
```
