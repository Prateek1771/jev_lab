Detects whether a message carries **a real person's personal data or a real secret** (password, API key), so it
can be redacted before it reaches an LLM. Code does what regexes are good at: finding email-, phone-, card- (Luhn-checked), SSN- and key-shaped strings,
and masking them. Whether a match is really a person's data (a customer's email or `support@`, a real card or
Stripe's test card) and whether there is PII no regex can see (a name with a home address and a diagnosis, an
email spelled out in words) is judgment: **one Jev Noul**, with a threshold tuned by the sweep.
**Measured:** accuracy, PII missed, clean text flagged, and the threshold sweep.

## With Jev
```mermaid
flowchart TD
    T["text"] --> jev["jev node"]
    jev --> N["Jev Noul: personal data<br/>or a real secret? P(true)"]
    N --> TH{"P ≥ THRESHOLD?"}
    TH -->|no| C["clean → LLM as is"]
    TH -->|yes| R["code: mask regex spans<br/>no span? redact by hand"]
    R --> L["redacted text → LLM"]
```

## Without Jev
```mermaid
flowchart LR
    T["text"] --> regex["regex node<br/>email, phone, Luhn card,<br/>SSN, key, 'password is', $0"]
    T --> structured["structured node<br/>fast LLM, enum pii / clean"]
    regex --> P["any match → pii<br/>shape, not meaning"]
    structured --> S["label only, nothing to tune"]
```
