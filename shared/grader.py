"""The Jev grader, the same for every graded project (05, 08, ...) and every variant in them.
Rubrics are written as "Required: ... Must not: ...": the real smoke test showed a rubric that lists more
than the question asks for (08: "30 days" was right, but the rubric also wanted the payment method) makes
the grader fail correct answers. Only what the task actually asks for goes under Required."""

from shared.openrouter import decide_traced

GRADE = {"correct": {
    "type": "noul",
    "instructions": "answer does task correctly: it meets every Required point in rubric and breaks no Must not point",
    "criteria": {"true": "Every Required point is met and no Must not point is broken; extra correct detail is fine",
                 "false": "A Required point is missing or wrong, a Must not point is broken, or the answer is cut off"},
}}


def grade(task: str, rubric: str, answer: str) -> dict:
    """P(true) is the quality; a judgment, not ground truth. The rubric reaches ONLY this call."""
    a, meta = decide_traced("jev.grade", {"task": task, "rubric": rubric, "answer": answer}, GRADE)
    return {"quality": float(a["correct"]["noul"])} | meta
