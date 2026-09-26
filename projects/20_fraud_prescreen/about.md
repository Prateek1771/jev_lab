Pre-screens **synthetic card transactions**: **allow**, **review**, or **investigate**. Code computes the facts
(amount vs the customer's usual, new device, abroad without a travel notice, transactions in the last hour,
address changed today). Jev reads the transaction and those facts and gives a **risk Score** (low, medium, high),
and code bands it. The **ladder** is the readme's cost idea: Jev screens everything, and only the transactions it
doesn't call low go to the expensive **frontier model**. Against them: a **rules engine** on the same facts ($0),
and the **frontier model on every transaction**. Traced.
**Measured:** accuracy, fraud allowed, good customers stopped, share sent to the frontier, and cost per
transaction.

## With Jev
```mermaid
flowchart TD
    T["transaction"] --> F["code: facts<br/>amount vs usual · new device · abroad<br/>velocity · address changed"]
    F --> jev["jev node: risk Score 0–2<br/>→ allow / review / investigate"]
    F --> ladder["ladder node: same Jev Score"]
    ladder --> L{"risk < 0.6?"}
    L -->|yes| A["allow, no frontier call"]
    L -->|no| FR["frontier model decides"]
```

## Without Jev
```mermaid
flowchart LR
    T["transaction + facts"] --> rules_engine["rules_engine node<br/>velocity ≥ 5 · new device + abroad + $500<br/>5x usual · abroad · new device · $0"]
    T --> frontier_all["frontier_all node<br/>frontier model on<br/>every transaction"]
    rules_engine --> O1["allow / review / investigate"]
    frontier_all --> O2["allow / review / investigate"]
```
