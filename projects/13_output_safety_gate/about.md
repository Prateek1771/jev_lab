Checks **the assistant's reply before the customer sees it**, a pre-output policy layer. Jev asks three different
questions in one call, each with criteria: does the reply **harm** (unsafe tips, dosing, disabling safety gear),
**leak** data the user isn't entitled to (another customer's address, internal notes, keys), or **break the
company policy** (which is in the state)? Code blocks the reply if any flag reaches the threshold. The replies are
fixed, so only the gate is measured. Against it: **no gate**, and an **LLM judge** given the same three rules.
**Measured:** accuracy, bad replies released, good replies blocked, and the threshold sweep on the highest flag.

## With Jev
```mermaid
flowchart TD
    I["user + question + reply<br/>+ company policy"] --> jev["jev node"]
    jev --> F["ONE Jev call, three Nouls:<br/>harmful · leaks_data · breaks_policy"]
    F --> TH{"any flag ≥ THRESHOLD?<br/>code"}
    TH -->|yes| B["block: reply never reaches the user"]
    TH -->|no| R["release to the user"]
```

## Without Jev
```mermaid
flowchart LR
    I["user + question + reply"] --> no_gate["no_gate node<br/>every reply ships, $0"]
    I --> llm_gate["llm_gate node<br/>fast LLM, same three rules,<br/>enum block / release"]
    no_gate --> U["user"]
    llm_gate --> U2["user, if released"]
```
