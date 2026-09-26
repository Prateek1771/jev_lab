Turns **uncertainty into a control signal**. A support agent has proposed an action (a refund, a label, a credit);
before it runs, a decision gets a confidence, and the confidence picks the path: **≥ 0.9 runs automatically**,
**0.6–0.9 goes to a stronger reviewer** (the frontier model), **< 0.6 goes to a human**. Jev gives the verdict as a
Choice (approve / reject) with the policy in its state, and its **confidence** sets the band. Against it: the same
bands driven by the **LLM's self-reported confidence**, and **reviewing every action** with the frontier model.
**Measured:** wrong actions executed (must be 0), good actions run automatically, share sent to review and to a
human, and cost.

## With Jev
```mermaid
flowchart TD
    I["policy + case + proposed action"] --> jev["jev node"]
    jev --> C["Jev Choice: approve / reject<br/>+ confidence"]
    C --> B{"confidence?"}
    B -->|"≥ 0.9"| A["run Jev's verdict automatically"]
    B -->|"0.6 – 0.9"| R["frontier model reviews → approve / reject"]
    B -->|"< 0.6"| H["human"]
```

## Without Jev
```mermaid
flowchart LR
    I["case + proposed action"] --> llm_self_confidence["llm_self_confidence node<br/>fast LLM: verdict + 'how sure, 0-1'<br/>same bands, same reviewer"]
    I --> always_review["always_review node<br/>frontier model reviews<br/>every action"]
    llm_self_confidence --> O1["auto / review / human"]
    always_review --> O2["approve / reject"]
```
