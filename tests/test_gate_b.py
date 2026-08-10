from __future__ import annotations

import json

import pytest
from byfeel.cli import build_parser, run_gate_b_metrics
from byfeel.gate_b import GateBEvaluationSet, calculate_gate_b_metrics
from pydantic import ValidationError


def evaluation_payload() -> dict:
    return {
        "results": [
            {
                "case_id": "ready-correct",
                "expected_state": "ready",
                "predicted_state": "ready",
                "decision": "advance",
                "confidence": 0.95,
            },
            {
                "case_id": "not-ready-correct",
                "expected_state": "not_ready",
                "predicted_state": "not_ready",
                "decision": "block",
                "confidence": 0.9,
            },
            {
                "case_id": "wrong-false-advance",
                "expected_state": "incorrect_or_overshot",
                "predicted_state": "ready",
                "decision": "advance",
                "confidence": 0.92,
            },
            {
                "case_id": "uncertain-abstain",
                "expected_state": "ready",
                "predicted_state": None,
                "decision": "human_confirmation",
                "confidence": 0.5,
            },
        ]
    }


def test_gate_b_metrics_include_confusion_abstention_and_false_advance() -> None:
    metrics = calculate_gate_b_metrics(GateBEvaluationSet.model_validate(evaluation_payload()))

    assert metrics.case_count == 4
    assert metrics.evaluated_count == 3
    assert metrics.abstention_rate == 0.25
    assert metrics.evaluated_accuracy == pytest.approx(2 / 3)
    assert metrics.confusion_matrix["incorrect_or_overshot"]["ready"] == 1
    assert metrics.per_class["ready"].precision == 0.5
    assert metrics.per_class["not_ready"].recall == 1
    assert metrics.demo_critical_false_positive_advance_case_ids == ["wrong-false-advance"]


def test_gate_b_evaluation_rejects_duplicate_case_ids() -> None:
    payload = evaluation_payload()
    payload["results"].append(payload["results"][0])

    with pytest.raises(ValidationError, match="case IDs must be unique"):
        GateBEvaluationSet.model_validate(payload)


def test_gate_b_metrics_cli_writes_result(tmp_path) -> None:
    results = tmp_path / "results.json"
    output = tmp_path / "metrics.json"
    results.write_text(json.dumps(evaluation_payload()), encoding="utf-8")
    args = build_parser().parse_args(
        ["gate-b-metrics", "--results", str(results), "--output", str(output)]
    )

    assert run_gate_b_metrics(args) == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["case_count"] == 4
    assert saved["demo_critical_false_positive_advance_count"] == 1
