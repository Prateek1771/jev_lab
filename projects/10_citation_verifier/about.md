Decides **whether an answer's citations hold up**: an answer cites help-centre sources in [brackets], as 08 and 09's
answers do, but does each cited source actually say that sentence? Code splits the answer into claims and catches
what needs no model: a sentence with no citation, or a citation id that was never retrieved. Jev then reads **each
(claim, cited source) pair on its own**, one Choice (supports, contradicts, not addressed), all pairs in parallel.
The worst claim decides the answer: **supported**, **contradicted** or **insufficient** evidence.
**Measured:** accuracy, contradictions caught, contradictions passed as supported, and good answers wrongly flagged.

## With Jev
```mermaid
flowchart TD
    A["question + answer + sources"] --> split["split node<br/>code: one claim per sentence,<br/>its [ids]"]
    split --> C{"code check"}
    C -->|"no citation"| U["insufficient: uncited"]
    C -->|"id not in sources"| H["insufficient: made-up citation"]
    C -->|"real citations"| P["Send × (claim, cited source), in parallel"]
    P --> jev_check["jev_check node<br/>ONE claim + ONE source per call:<br/>support (Choice)"]
    jev_check --> jev_verdict["jev_verdict node<br/>claim: any supports → supported,<br/>else contradicts → contradicted"]
    U --> jev_verdict
    H --> jev_verdict
    jev_verdict --> V["answer = its worst claim"]
```

## Without Jev
```mermaid
flowchart LR
    A["question + answer + sources"] --> split["split node<br/>same claims"]
    split --> llm_judge["llm_judge node<br/>fast LLM reads the whole answer<br/>and every source in ONE prompt"]
    split --> trust_citations["trust_citations node<br/>every sentence has [brackets]<br/>→ supported, $0"]
    llm_judge --> V1["supported / contradicted / insufficient"]
    trust_citations --> V2["supported / insufficient"]
```
