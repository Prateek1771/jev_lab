Turns a support ticket into **one action**: refund automatically, refund after confirmation, deny by
policy, route to a team, or hand to a human. Jev answers three questions in **one call**: intent (Choice), policy
support (Noul) and churn risk (Score). Counting and dates are computed in code, a pure policy decides, and the
graph's conditional edge is the only way to reach each action node. The baselines read the policy in prose and pick
the action themselves. **Measured:** accuracy and cost, plus proof that an auto-refund can only happen on its edge.

## With Jev
```mermaid
flowchart LR
    I["ticket + order facts"] --> jev_ask["jev_ask node"]
    jev_ask --> Q["ONE Jev call<br/>intent (Choice) · policy_supports_refund (Noul) · churn_risk (Score)"]
    jev_ask --> F["facts_from: has_order · prior refunds · return window<br/>computed in code, not Jev"]
    Q --> P{"policy.choose<br/>first match returns"}
    F --> P
    P -->|refund_auto| refund_auto["refund_auto<br/>start_refund_flow:auto"]
    P -->|refund_confirm| refund_confirm["refund_confirm<br/>start_refund_flow:confirm"]
    P -->|block| block["block<br/>reply:refund_policy"]
    P -->|route_queue| route_queue["route_queue<br/>route to the team queue"]
    P -->|human| human["human<br/>escalate:human_agent"]
```

## Without Jev
```mermaid
flowchart LR
    I["ticket + the same facts, as JSON"] --> baseline["baseline node<br/>fast LLM reads the policy in prose"]
    I --> structured["structured node<br/>same prompt, enum of 5 actions"]
    baseline --> A["one action name, parsed"]
    structured --> B["one action name"]
    A -.-> X["no band, no actions list:<br/>the caller must trust the name"]
    B -.-> X
```
