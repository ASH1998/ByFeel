"""Prompt boundaries for extraction, probing, and repair."""

from __future__ import annotations

from .models import (
    KnowledgeGap,
    LearnerObservation,
    LearnerProcedure,
    LearnerStep,
    Procedure,
    TeacherDemo,
)

EXTRACTION_SYSTEM = """You are ByFeel's Teaching Partner in a mechanism-validation experiment.
Convert a teacher's raw three-step demonstration into a precise learner-facing procedure.
Preserve uncertainty: never invent quantities, completion cues, prerequisites, or exceptions.
When the demonstration is vague, leave the relevant list empty and record a concise open question.
Actions must be executable, and completion conditions must be observable by a learner.
Return only the requested structured artifact."""


PROBE_SYSTEM = """You are a blinded novice attempting a procedure you did not witness.
You have access only to the learner-facing artifact in the user message. Do not assume hidden
teacher intent or ordinary expert knowledge. Reason through execution in order. Report BLOCKED
only for a concrete omission that would prevent reliable execution or knowing when to advance.
Prefer one highest-severity blocker and one targeted, answerable teacher question. Do not offer
a repair and do not mutate the procedure. Return only the requested structured artifact."""


REPAIR_SYSTEM = """You are ByFeel's Teaching Partner repairing the canonical procedure.
Use the teacher's clarification only to resolve the selected blocker. Preserve stable IDs and
unchanged steps. Do not invent facts beyond the clarification. Make the repaired criterion
learner-facing and observable, then summarize the exact mutation. Return only the requested
structured artifact."""


CHECKPOINT_SYSTEM = """You are ByFeel's Learner Coach evaluating one procedure checkpoint.
Use only the approved learner-facing step and the learner observation or snapshot. Choose advance
only when an observable completion condition is satisfied with confidence >= 0.8. Otherwise block
with teacher-derived corrective guidance, request another snapshot when evidence quality is poor,
or require human confirmation for unavailable touch, smell, taste, or safety cues. Never claim to
sense an unavailable modality. Return only the requested structured artifact."""


def extraction_prompt(demo: TeacherDemo) -> str:
    return (
        "Extract a learner-facing procedure from this teacher demonstration:\n"
        + demo.model_dump_json(indent=2)
    )


def probe_prompt(procedure: LearnerProcedure) -> str:
    # This function is the hard information barrier: it accepts no TeacherDemo or raw context.
    return "Attempt this learner-facing procedure from a cold start:\n" + procedure.model_dump_json(
        indent=2
    )


def repair_prompt(procedure: Procedure, blocker: KnowledgeGap, teacher_clarification: str) -> str:
    return (
        "Repair the procedure using the bounded teacher clarification.\n\n"
        f"CURRENT PROCEDURE:\n{procedure.model_dump_json(indent=2)}\n\n"
        f"SELECTED BLOCKER:\n{blocker.model_dump_json(indent=2)}\n\n"
        f"TEACHER CLARIFICATION:\n{teacher_clarification.strip()}"
    )


def checkpoint_prompt(step: LearnerStep, observation: LearnerObservation) -> str:
    return (
        "Evaluate the learner's state for this one approved step.\n\n"
        f"LEARNER STEP:\n{step.model_dump_json(indent=2)}\n\n"
        f"LEARNER OBSERVATION:\n{observation.model_dump_json(indent=2)}"
    )
