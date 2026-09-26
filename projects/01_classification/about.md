Routes a support ticket to one team: **billing, technical, account, sales, or other**.
Jev answers one **Choice** question and returns the team with a confidence. The baselines ask a fast LLM the same
question twice: once in free text (then parsed), once forced into the five labels.
**Measured:** accuracy, latency and cost per ticket. Look at Jev's confidence on the tickets it gets wrong.

## With Jev
```mermaid
flowchart LR
    T["ticket text"] --> jev["jev node"]
    jev --> Q["Jev Choice: team<br/>billing · technical · account · sales · other"]
    Q --> R["label + confidence + probabilities"]
```

## Without Jev
```mermaid
flowchart LR
    T["ticket text"] --> baseline["baseline node<br/>fast LLM, plain prompt"]
    T --> structured["structured node<br/>fast LLM, JSON enum of 5 teams"]
    baseline --> P["parse_label on free text<br/>no match = invalid"]
    structured --> S["label from the schema<br/>no confidence"]
```
