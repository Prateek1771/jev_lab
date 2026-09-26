An **agent** that loops: pick the next tool (or stop), write its arguments, run it, look at the result.
Jev picks from a closed list (6 tools, plus finish and ask_user) and reports a confidence. An LLM writes the
arguments, and only for the chosen tool. The tools are offline fakes, and every loop stops at 4 tool calls. The label
is the **whole trajectory** (e.g. `database > calculator`). **Traced:** every loop turn and every model call, with
its cost, in Langfuse.

## With Jev
```mermaid
flowchart LR
    R["request"] --> jev["jev node (loops)"]
    jev --> P["Jev Choice: next step<br/>6 tools · finish · ask_user"]
    P --> G{"policy.next_step<br/>confidence below 0.45 → ask_user"}
    G -->|tool| W["LLM writes the args<br/>that tool's schema only"]
    W --> X["run_tool → observation"]
    X -->|loop, max 4 calls| jev
    G -->|finish or ask_user| E["trajectory label"]
```

## Without Jev
```mermaid
flowchart LR
    R["request"] --> llm_selector["llm_selector node (loops)<br/>fast LLM picks from the same enum"]
    R --> tool_calling["tool_calling node (loops)<br/>native bind_tools: tool + args in one message"]
    llm_selector --> W["same LLM arg writer → run_tool"]
    W -->|loop, max 4| llm_selector
    tool_calling --> X["run_tool → ToolMessage"]
    X -->|loop, max 4| tool_calling
```
