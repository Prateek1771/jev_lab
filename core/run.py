"""The UI's input contract. The only thing a project imports from core/."""

from dataclasses import dataclass, field


@dataclass
class Run:
    variant: str                  # key in Result.runs: "jev" | "baseline" | "structured" | ...
    model: str
    label: str | None             # None = the model answered outside the schema
    confidence: float | None      # Jev Choice/Score report one; Noul and chat LLMs do not
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None        # None = provider did not report it
    raw: dict = field(default_factory=dict)
    probability: float | None = None  # Noul: P(statement is true). Not a confidence.
    score: float | None = None        # Score: probability-weighted position, 0 .. levels-1
    quality: float | None = None      # graded free-text answers (05+): the grader's P(answer is correct)

    @property
    def valid(self) -> bool:
        return self.label is not None


@dataclass
class Result:
    runs: dict[str, Run]          # every variant of one experiment, keyed by Run.variant, in display order
    trace_url: str | None = None  # set only by projects that trace (multi-step agents, 06+)
    trace_id: str | None = None

    @classmethod
    def of(cls, *runs: Run) -> "Result":
        return cls({r.variant: r for r in runs})
