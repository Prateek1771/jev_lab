Decides whether an **edge an LLM extracted from a document** (subject, relation, object) may go into the
**knowledge graph**. Code first checks that both entities appear in the document (an invented entity is rejected
for free). Then one Jev **Choice** reads the document and the edge's meaning in words, and answers **supports**,
**contradicts** or **not_stated**. The traps are the ones that poison graphs: a **reversed direction**, a **past
fact** stored as current ("previously", "before that"), a **declined offer**, a **rumour**, a **wrong relation**.
The edge is stored only when P(supports) ≥ 0.5 (a threshold sweep shows the tradeoff). Against it: **storing every extracted edge**, and the **LLM checking its own
extraction**.
**Measured:** accuracy, bad edges stored, good edges rejected.

## With Jev
```mermaid
flowchart TD
    E["document + extracted edge<br/>(subject, relation, object)"] --> jev["jev node"]
    jev --> C{"code: both entities<br/>in the document?"}
    C -->|no| X["reject, no call<br/>(invented entity)"]
    C -->|yes| J["ONE Jev Choice on the edge's meaning:<br/>supports · contradicts · not_stated"]
    J --> P{"P(supports) ≥ 0.5?"}
    P -->|yes| G["store the edge in the graph"]
    P -->|no| R["reject"]
```

## Without Jev
```mermaid
flowchart TD
    E["document + extracted edge"] --> store_all["store_all node<br/>every edge is stored, $0"]
    E --> llm_self_check["llm_self_check node<br/>fast LLM: is my extraction valid?"]
    store_all --> G1["graph fills with reversed,<br/>past and rumoured edges"]
    llm_self_check --> G2["valid / invalid"]
```
