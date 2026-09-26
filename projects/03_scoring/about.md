Scores how **severe** a ticket is: **low, medium, or high**. Jev answers one **Score** question over three
ordered levels and returns a probability-weighted score (0–2) with a confidence. The label is the most likely level,
and the score feeds an "escalate if score ≥ t" sweep. The baselines pick a level in free text, or from an enum.
**Measured:** accuracy, latency, cost, and the escalation sweep.

## With Jev
```mermaid
flowchart LR
    T["ticket text"] --> jev["jev node"]
    jev --> S["Jev Score: severity<br/>low, medium, high (ordered)"]
    S --> L["label = most likely level"]
    S --> V["score 0..2 → escalation sweep"]
```

## Without Jev
```mermaid
flowchart LR
    T["ticket text"] --> baseline["baseline node<br/>fast LLM, plain prompt"]
    T --> structured["structured node<br/>fast LLM, enum low / medium / high"]
    baseline --> P["parse_label → level or invalid"]
    structured --> Q["level only, no score"]
```
