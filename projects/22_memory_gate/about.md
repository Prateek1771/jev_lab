Decides whether what the user just said should become **long-term memory**, so the assistant's memory holds
lasting facts and not noise. Jev answers four questions in one call: is it **durable** (still true and useful in a
month), is it **about the user** themself, is it **already known** (given the stored memories; a change to a
stored fact counts as new), and does it contain a **secret**? Code stores it only if all four say so; secret-shaped
strings (project 12's detectors) are refused before any call. Against it: **storing everything**, and an **LLM
asked "should I remember this?"**.
**Measured:** accuracy, junk stored, facts lost.

## With Jev
```mermaid
flowchart TD
    M["message + stored memories"] --> jev["jev node"]
    jev --> S{"code: secret-shaped?<br/>(12's detectors)"}
    S -->|yes| X["skip, no call"]
    S -->|no| F["ONE Jev call, four Nouls:<br/>durable · about_user · already_known · secret"]
    F --> D{"durable and about the user,<br/>not known, not secret?"}
    D -->|yes| W["store (or update)"]
    D -->|no| K["skip"]
```

## Without Jev
```mermaid
flowchart LR
    M["message + memories"] --> store_everything["store_everything node<br/>every message is stored, $0"]
    M --> structured["structured node<br/>fast LLM: store or skip?"]
    store_everything --> W1["memory grows with noise"]
    structured --> W2["store / skip"]
```
