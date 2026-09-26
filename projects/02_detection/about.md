Detects whether a customer message is **urgent**. Jev answers one **Noul** (a true/false statement) and
returns P(urgent). Code turns that into a label with a threshold you tune on the Dataset tab (the sweep), so the
cut-off is a business decision, not the model's. The baselines answer yes/no in free text, or forced into two labels.
**Measured:** accuracy, latency, cost, and the threshold sweep.

## With Jev
```mermaid
flowchart LR
    M["message"] --> jev["jev node"]
    jev --> N["Jev Noul: time-sensitive?<br/>returns P(true)"]
    N --> TH{"P ≥ THRESHOLD?<br/>code, tuned by the sweep"}
    TH -->|yes| U["urgent"]
    TH -->|no| NU["not_urgent"]
```

## Without Jev
```mermaid
flowchart LR
    M["message"] --> baseline["baseline node<br/>fast LLM: yes or no?"]
    M --> structured["structured node<br/>fast LLM, enum urgent / not_urgent"]
    baseline --> P["parse yes/no<br/>no probability, nothing to tune"]
    structured --> S["label only"]
```
