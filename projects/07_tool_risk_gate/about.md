Decides whether a **proposed tool call may run**: allow, confirm (ask a person), or block. Hard rules in
code run first (unbounded delete, `rm -rf /`, `curl | sh`, secret paths) and cost nothing. Otherwise Jev answers
four separate questions in one call, and a pure policy decides. The gate sees the goal and the call, never the
proposing model's reasons. **Measured:** unsafe calls blocked, **unsafe calls allowed (must be 0)**, and safe calls stopped.

## With Jev
```mermaid
flowchart LR
    C["goal + proposed call"] --> jev["jev node"]
    jev --> H{"rules.hard_block<br/>checks structure, not substrings"}
    H -->|hit| B["block · no Jev call · $0"]
    H -->|no hit| Q["ONE Jev call<br/>in_scope · reversible · leaks_sensitive (Noul)<br/>severity (Score)"]
    Q --> P{"policy.decide<br/>block rules first"}
    P --> D["allow / confirm / block<br/>+ reason + actions"]
```

## Without Jev
```mermaid
flowchart LR
    C["goal + proposed call, same view"] --> baseline["baseline node<br/>fast LLM reads the policy, answers in text"]
    C --> structured["structured node<br/>same prompt, enum allow / confirm / block"]
    baseline --> A["label, parsed · no hard rules"]
    structured --> S["label · no hard rules"]
```
