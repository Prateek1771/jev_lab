Routes a request to **one of four agents** (research, coding, finance, support), then picks **which of that agent's
three tools** the request needs. Jev makes two small decisions: a Choice over the agents, then a Choice over
only that agent's tools, with the chosen agent in its state. Against it: an **LLM router** choosing agent/tool from
the whole tree in one call, and the **one flat agent** approach, where all 12 tools are bound to a single model at
once. The requests are full of words that belong to another agent ("refund" in a code question, "invoice" as a code
symbol). Traced: two Jev generations per request.
**Measured:** agent accuracy (the label), agent + tool accuracy, tokens and cost.

## With Jev
```mermaid
flowchart TD
    R["request"] --> jev["jev node"]
    jev --> A["Jev Choice 1: which agent?<br/>research · coding · finance · support"]
    A --> T["Jev Choice 2: which of THAT agent's<br/>3 tools? (state: request + agent)"]
    T --> O["agent → tool"]
```

## Without Jev
```mermaid
flowchart LR
    R["request"] --> llm_agent_router["llm_agent_router node<br/>fast LLM picks agent/tool<br/>from all 12 pairs, one call"]
    R --> flat_agent["flat_agent node<br/>one LLM, all 12 tools bound,<br/>native tool calling"]
    llm_agent_router --> O1["agent/tool"]
    flat_agent --> O2["first tool called → its agent"]
```
