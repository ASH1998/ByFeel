from __future__ import annotations

from types import SimpleNamespace

from byfeel.gemini import ByFeelModelRouter, GeminiStructuredClient
from byfeel.models import ProbeReport, ProbeStatus, Procedure


class FakeModels:
    def __init__(self) -> None:
        self.config = None

    def generate_content(self, *, model, contents, config):
        del model, contents
        self.config = config
        return SimpleNamespace(
            parsed=None,
            text=(
                '{"id":"contract","title":"Contract","domain":"test",'
                '"learner_goal":"Validate JSON schema","steps":['
                '{"step_id":"step-1","order":1,"action":"Check",'
                '"confidence":1}]}'
            ),
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=5,
                thoughts_token_count=2,
                total_token_count=17,
            ),
        )


def test_gemini_uses_json_schema_path_and_validates_response(monkeypatch) -> None:
    models = FakeModels()
    monkeypatch.setattr(
        "byfeel.gemini.genai.Client",
        lambda api_key: SimpleNamespace(models=models),
    )
    client = GeminiStructuredClient(api_key="test-key", model="fake-model")
    result = client.generate(system="test", prompt="test", schema=Procedure)

    assert result.id == "contract"
    assert models.config.response_schema is None
    assert models.config.response_json_schema["additionalProperties"] is False
    assert client.usage == [
        {
            "prompt_tokens": 10,
            "output_tokens": 5,
            "thinking_tokens": 2,
            "total_tokens": 17,
        }
    ]


class RoutingFake:
    def __init__(self, model: str) -> None:
        self.model = model
        self.usage: list[dict[str, int]] = []
        self.schemas: list[type] = []

    def generate(self, *, system: str, prompt: str, schema: type):
        del system, prompt
        self.schemas.append(schema)
        if schema is ProbeReport:
            return ProbeReport(status=ProbeStatus.UNBLOCKED, summary="No blocker")
        return Procedure.model_validate(
            {
                "id": "routed",
                "title": "Routed",
                "domain": "test",
                "learner_goal": "Verify model routing",
                "steps": [
                    {
                        "step_id": "step-1",
                        "order": 1,
                        "action": "Route",
                        "confidence": 1,
                    }
                ],
            }
        )


def test_model_router_reserves_main_model_for_blinded_probe() -> None:
    main = RoutingFake("gemini-3.6-flash")
    lite = RoutingFake("gemini-3.5-flash-lite")
    router = ByFeelModelRouter(main=main, lite=lite)

    router.generate(system="extract", prompt="demo", schema=Procedure)
    router.generate(system="probe", prompt="artifact", schema=ProbeReport)

    assert lite.schemas == [Procedure]
    assert main.schemas == [ProbeReport]
    assert router.model == "main=gemini-3.6-flash,lite=gemini-3.5-flash-lite"
