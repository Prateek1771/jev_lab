A **customer support agent, end to end**: triage, route, look up the facts, answer. Jev triages in **one call**
with three questions: the **intent** (billing, orders, tech), whether the message **needs a human** (a legal
threat, an injury, a threat to leave, a security incident, however calmly written), and **urgency** (priority).
Code routes: a human if needed, otherwise the right specialist. The specialist answers from the looked-up order
facts, and Jev's grader scores every answer against a rubric. Against it: **one LLM agent** that picks the route
and writes the answer in a single prompt. Traced.
**Measured:** route accuracy, answers passing the grader, cost per passing answer.

## With Jev
```mermaid
flowchart TD
    M["message + looked-up facts"] --> jev["jev node"]
    jev --> T["ONE Jev call: intent (Choice),<br/>needs_human (Noul), urgency (Noul)"]
    T --> E{"code: needs_human ≥ 0.5?"}
    E -->|yes| H["human agent"]
    E -->|no| S["specialist for the intent:<br/>billing · orders · tech"]
    S --> A["answer from policy + facts"]
    A --> G["Jev grader + rubric"]
```

## Without Jev
```mermaid
flowchart LR
    M["message + looked-up facts"] --> single_agent["single_agent node<br/>one LLM prompt: route<br/>(billing / orders / tech / human)<br/>+ the answer"]
    single_agent --> G["same grader + rubric"]
```
