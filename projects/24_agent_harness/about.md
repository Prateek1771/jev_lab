The **Jev agent harness** (the readme's Level 9): the earlier projects' Jev pieces composed into one agent, each
**imported from its own project**, not rewritten.
- **06's tool router** picks the next tool, or stops.
- **07's gate** runs its hard rules on every proposed call, and its four judgments on every call with side effects
  (read-only tools are known in code and skip them): allow, confirm (the agent stops and asks), or block (the turn
  ends and the reply explains).
- **21's relevance filter** judges each item of a big tool output, so the reply only reads what it needs.
- **05's route** picks which model tier writes the reply, once the tools have run: on the request plus the evidence.

Against it: a **plain tool-calling agent** on the fast model, and the **same agent on the frontier model**. Both are
told the same policy in their prompt; only the harness enforces it.
**Measured:** pass rate (graded), cost per pass, rows where a forbidden call **ran**, tokens given to the reply.

## With Jev
```mermaid
flowchart TD
    U["user request"] --> agent["agent node (loops, ≤ 4 tools)<br/>06: Jev Choice: which tool, finish, or ask_user"]
    agent --> G{"07 gate on the call:<br/>hard rules; 4 judgments if it has side effects"}
    G -->|block| B["stop: BLOCKED"]
    G -->|confirm| C["stop: ask the user to confirm"]
    G -->|allow| T["run the tool"]
    T --> F{"more than 8 items?"}
    F -->|yes| N["21: one Noul per item, in parallel<br/>keep only what the request needs"] --> agent
    F -->|no| agent
    agent -->|finish / ask_user| route["route node<br/>05: difficulty + stakes of the reply,<br/>given the evidence → tier"]
    C --> route
    B --> route
    route --> answer["answer node<br/>the routed tier writes the reply"]
```

## Without Jev
```mermaid
flowchart TD
    U["user request + policy in the prompt"] --> plain_agent["plain_agent node<br/>fast LLM, native tool calling"]
    U --> frontier_agent["frontier_agent node<br/>frontier LLM, native tool calling"]
    plain_agent -->|every call runs, whole outputs| plain_agent
    frontier_agent -->|every call runs, whole outputs| frontier_agent
    plain_agent --> R1["reply"]
    frontier_agent --> R2["reply"]
```
