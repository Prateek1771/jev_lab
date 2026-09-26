Picks **which model answers a task**: fast, balanced, or frontier. Jev judges difficulty (Score) and
risk (Noul) in one call, code maps them to a tier (every doubt routes up), and only that model answers. Every
answer, from every variant, is graded by one Jev Noul against a rubric the answering models never see.
**Measured:** pass rate and **cost per passing answer** (routing + answering; grading is kept apart).

## With Jev
```mermaid
flowchart LR
    T["task"] --> jev["jev node"]
    jev --> Q["ONE Jev call<br/>difficulty (Score) · high_risk (Noul)"]
    Q --> R{"router.tier_for<br/>unsure or risky → frontier"}
    R -->|fast, balanced or frontier| A["the chosen model answers"]
    A --> G["Jev grader (Noul)<br/>task + rubric + answer"]
    G --> Q2["quality · passes at 0.5"]
```

## Without Jev
```mermaid
flowchart LR
    T["task"] --> llm_router["llm_router node<br/>fast LLM picks a tier (enum)"]
    T --> frontier["frontier node<br/>always claude-sonnet-5"]
    llm_router --> A1["the chosen model answers"]
    frontier --> A2["the frontier model answers"]
    A1 --> G["same Jev grader + rubric"]
    A2 --> G
```
