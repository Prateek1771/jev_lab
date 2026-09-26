Decides **what order the retrieved chunks go in**, because only the top 3 reach the answer. A word-overlap
retriever returns 10 chunks from a 30-chunk help centre, with overview and FAQ pages that repeat the question's words
but don't answer it. Jev gives **each chunk its own relevance Score** (irrelevant, background, directly answers),
all 10 calls in parallel, and the chunks are sorted by it. The same model answers from the top 3, and Jev grades it.
**Measured:** nDCG@3 and MRR against gold relevance grades, plus pass rate and cost per passing answer.

## With Jev
```mermaid
flowchart TD
    Q["question"] --> retrieve["retrieve node<br/>top 10 by word overlap"]
    retrieve -->|"Send × 10, in parallel"| jev_score["jev_score node<br/>ONE chunk per call:<br/>relevance (Score, 3 levels)"]
    jev_score --> jev_answer["jev_answer node"]
    jev_answer --> S{"ranking.jev_order<br/>score high → low<br/>ties: retriever order"}
    S --> T["top 3 → LLM answers"]
    T --> G["Jev grader + rubric<br/>nDCG@3 · MRR vs gold"]
```

## Without Jev
```mermaid
flowchart LR
    Q["question"] --> retrieve["retrieve node<br/>same 10 chunks"]
    retrieve --> llm_rank["llm_rank node<br/>fast LLM orders ALL 10<br/>in one prompt"]
    retrieve --> retriever_order["retriever_order node<br/>keep the word-overlap order"]
    llm_rank --> A1["top 3 → same LLM answers"]
    retriever_order --> A2["top 3 → same LLM answers"]
    A1 --> G["same grader · nDCG@3 · MRR"]
    A2 --> G
```
