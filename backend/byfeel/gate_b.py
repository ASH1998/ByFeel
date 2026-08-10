"""Local Gate B result models and deterministic metric calculation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import CheckpointDecision, VisualCheckpointState


class GateBCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    expected_state: VisualCheckpointState
    predicted_state: VisualCheckpointState | None = None
    decision: CheckpointDecision
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def prediction_matches_decision_shape(self) -> GateBCaseResult:
        abstained = self.decision in {
            CheckpointDecision.RETRY_SNAPSHOT,
            CheckpointDecision.HUMAN_CONFIRMATION,
        }
        if not abstained and self.predicted_state is None:
            raise ValueError("a non-abstaining result requires predicted_state")
        return self


class GateBEvaluationSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[GateBCaseResult] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> GateBEvaluationSet:
        case_ids = [result.case_id for result in self.results]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Gate B case IDs must be unique")
        return self


class GateBClassMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support: int = Field(ge=0)
    predicted_count: int = Field(ge=0)
    true_positive: int = Field(ge=0)
    precision: float | None
    recall: float | None


class GateBMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_count: int = Field(ge=1)
    evaluated_count: int = Field(ge=0)
    abstention_count: int = Field(ge=0)
    abstention_rate: float = Field(ge=0, le=1)
    evaluated_accuracy: float | None = Field(default=None, ge=0, le=1)
    confusion_matrix: dict[str, dict[str, int]]
    per_class: dict[str, GateBClassMetrics]
    demo_critical_false_positive_advance_count: int = Field(ge=0)
    demo_critical_false_positive_advance_case_ids: list[str]


def calculate_gate_b_metrics(evaluation: GateBEvaluationSet) -> GateBMetrics:
    states = list(VisualCheckpointState)
    predicted_columns = [state.value for state in states] + ["abstain"]
    confusion = {
        expected.value: {predicted: 0 for predicted in predicted_columns} for expected in states
    }
    abstentions = 0
    correct = 0
    false_advances: list[str] = []

    for result in evaluation.results:
        abstained = result.decision in {
            CheckpointDecision.RETRY_SNAPSHOT,
            CheckpointDecision.HUMAN_CONFIRMATION,
        }
        predicted = (
            "abstain"
            if abstained or result.predicted_state is None
            else result.predicted_state.value
        )
        confusion[result.expected_state.value][predicted] += 1
        if predicted == "abstain":
            abstentions += 1
        elif result.predicted_state == result.expected_state:
            correct += 1
        if (
            result.decision == CheckpointDecision.ADVANCE
            and result.expected_state != VisualCheckpointState.READY
        ):
            false_advances.append(result.case_id)

    per_class: dict[str, GateBClassMetrics] = {}
    for state in states:
        value = state.value
        support = sum(confusion[value].values())
        predicted_count = sum(confusion[expected.value][value] for expected in states)
        true_positive = confusion[value][value]
        per_class[value] = GateBClassMetrics(
            support=support,
            predicted_count=predicted_count,
            true_positive=true_positive,
            precision=(true_positive / predicted_count if predicted_count else None),
            recall=(true_positive / support if support else None),
        )

    case_count = len(evaluation.results)
    evaluated_count = case_count - abstentions
    return GateBMetrics(
        case_count=case_count,
        evaluated_count=evaluated_count,
        abstention_count=abstentions,
        abstention_rate=abstentions / case_count,
        evaluated_accuracy=(correct / evaluated_count if evaluated_count else None),
        confusion_matrix=confusion,
        per_class=per_class,
        demo_critical_false_positive_advance_count=len(false_advances),
        demo_critical_false_positive_advance_case_ids=false_advances,
    )
