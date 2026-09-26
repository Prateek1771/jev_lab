Decides whether a **coding agent** may run a shell or git command: **allow**, **confirm** (ask the human), or
**block**. Code blocks the few commands no goal can justify (`rm -rf /`, piping a download into a shell, a fork
bomb) with no model call. Everything else gets **one Jev Choice** that sees the agent's goal and branch, because
`rm -rf node_modules` is fine for a clean reinstall and `git push origin +main` is not fine for a typo. An "allow"
Jev isn't sure about goes to the human. Against it: a **prefix permission list** like the ones coding agents ship
with, and an **LLM classifier**.
**Measured:** accuracy, dangerous commands allowed, safe commands stopped.

## With Jev
```mermaid
flowchart TD
    I["goal + branch + command"] --> jev["jev node"]
    jev --> H{"code: hard rule?<br/>rm -rf / · curl | sh · mkfs · fork bomb"}
    H -->|yes| B["block, no call"]
    H -->|no| C["ONE Jev Choice:<br/>allow / confirm / block"]
    C --> U{"allow with<br/>confidence < 0.6?"}
    U -->|yes| Q["confirm: ask the human"]
    U -->|no| D["Jev's choice"]
```

## Without Jev
```mermaid
flowchart LR
    I["command"] --> permission_list["permission_list node<br/>deny substrings, allow prefixes,<br/>else ask · $0"]
    I --> structured["structured node<br/>fast LLM, enum allow / confirm / block"]
    permission_list --> P["words, not goals"]
    structured --> S["label only"]
```
