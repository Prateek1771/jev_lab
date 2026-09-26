Reviews **a code change against the team's four rules**, the things `ruff` and `eslint` can't see: an **auth
bypass**, **sensitive data** in logs or responses, a **layering** break (a route querying the database directly),
and a **hard-coded secret**. Jev answers one Noul per rule, all four in one call, because they judge the same code.
Against it: **semgrep-style static checks** ($0: patterns for decorators, log calls, queries in routes, key
literals) and an **LLM reviewer** that lists the rules it thinks are broken. Every row has gold violations.
**Measured:** accuracy (any rule broken?), bad changes passed, clean changes flagged, and per-rule precision and
recall.

## With Jev
```mermaid
flowchart TD
    I["path + code"] --> jev["jev node"]
    jev --> F["ONE Jev call, four Nouls:<br/>auth_bypass · sensitive_exposure<br/>layering · hardcoded_secret"]
    F --> TH{"each P ≥ THRESHOLD?"}
    TH --> V["violations → flag / clean<br/>precision and recall vs gold"]
```

## Without Jev
```mermaid
flowchart LR
    I["path + code"] --> static_checks["static_checks node<br/>decorator missing? log(password)?<br/>query in routes/? key literal? · $0"]
    I --> llm_reviewer["llm_reviewer node<br/>fast LLM lists broken rules<br/>(enum array)"]
    static_checks --> V1["patterns, not meaning"]
    llm_reviewer --> V2["violations"]
```
