Detects **prompt injection**: text that tries to take control of the AI assistant reading it. The text comes with
its **source**, because that changes the answer: a user may give the assistant instructions, but a retrieved page,
email or tool result may not. Jev answers one **Noul** and returns P(injection); code blocks at a threshold you tune
with the sweep. Against it: the phrase **deny-list** most filters start with ($0), and an **LLM classifier**, which
has to read the very text that may be attacking it.
**Measured:** accuracy, injections missed, safe inputs blocked, and the threshold sweep.

## With Jev
```mermaid
flowchart TD
    I["source + text"] --> jev["jev node"]
    jev --> N["Jev Noul: tries to take control<br/>of the assistant? P(true)"]
    N --> TH{"P ≥ THRESHOLD?<br/>code, tuned by the sweep"}
    TH -->|yes| B["injection: block"]
    TH -->|no| A["safe: continue"]
```

## Without Jev
```mermaid
flowchart LR
    I["source + text"] --> pattern_filter["pattern_filter node<br/>regex deny-list, $0"]
    I --> structured["structured node<br/>fast LLM, enum injection / safe<br/>(reads the attack as a prompt)"]
    pattern_filter --> P["words, not meaning"]
    structured --> S["label only, nothing to tune"]
```
