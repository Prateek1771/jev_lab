Qualifies an inbound **sales lead**: **sales now**, **nurture**, or **disqualify**. Code checks the facts it can
(company size against the profile's 50 to 2,000 employees; fewer than 10 is out). Jev answers two Scores in one
call: **ICP fit** (industry, buyer, pain, disqualifiers such as a competitor or a student) and **purchase intent**
(browsing, exploring, actively buying). Code turns the two scores into a CRM route. Against it: **points-based lead
scoring** ($0: points for a VP title, industry words, size, "demo" or "pricing"), and an **LLM classifier** given
the same profile.
**Measured:** route accuracy, and where each variant sends the tricky leads.

## With Jev
```mermaid
flowchart TD
    L["lead: company, employees, title, email, message"] --> jev["jev node"]
    jev --> S["ONE Jev call, two Scores:<br/>ICP fit (0–2) · purchase intent (0–2)"]
    S --> R{"code"}
    R -->|"< 10 employees, or fit < 0.5"| D["disqualify"]
    R -->|"fit ≥ 1.5, intent ≥ 1.5, 50–2,000 employees"| N["sales now"]
    R -->|otherwise| U["nurture"]
```

## Without Jev
```mermaid
flowchart LR
    L["lead"] --> points["points node<br/>+25 VP title · +20 industry word<br/>+15 size · +30 demo/pricing<br/>−40 free email · $0"]
    L --> structured["structured node<br/>fast LLM, same profile,<br/>enum of 3 routes"]
    points --> P["≥ 70 sales now · ≥ 35 nurture"]
    structured --> S2["route"]
```
