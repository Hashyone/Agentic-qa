import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from platform_core.api.app import create_app
from platform_core.intent.extraction import IntentExtractionError, IntentExtractionPayload
from platform_core.providers.generation import (
    TextGenerationError,
    TextGenerationResult,
)
from platform_core.storage.models import SourceRequestRow


@pytest.fixture(autouse=True)
def disable_implicit_provider(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def test_create_task_preserves_request_and_returns_versioned_intent() -> None:
    app = create_app("sqlite:///:memory:", initialize_schema=True)
    source_text = "  Build a tool that checks my requirements.\n"

    with TestClient(app) as client:
        response = client.post("/v1/tasks", json={"input": {"text": source_text}})

        assert response.status_code == 201
        created = response.json()
        task_id = created["task_id"]
        assert created["status"] == "received"

        task_response = client.get(f"/v1/tasks/{task_id}")
        intent_response = client.get(f"/v1/tasks/{task_id}/intent")

    assert task_response.status_code == 200
    assert task_response.json()["source_request"] == source_text
    assert intent_response.status_code == 200
    intent = intent_response.json()
    assert intent["task_id"] == task_id
    assert intent["version"] == 1
    assert intent["status"] == "draft"
    assert intent["source_request"]["text"] == source_text
    assert intent["content_hash"].startswith("sha256:")


def test_create_task_rejects_blank_text() -> None:
    app = create_app("sqlite:///:memory:", initialize_schema=True)

    with TestClient(app) as client:
        response = client.post("/v1/tasks", json={"input": {"text": "   "}})

    assert response.status_code == 422


def test_unknown_task_returns_not_found() -> None:
    app = create_app("sqlite:///:memory:", initialize_schema=True)

    with TestClient(app) as client:
        response = client.get("/v1/tasks/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404


def test_task_and_intent_persist_across_app_restart(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'platform.db'}"
    first_app = create_app(database_url, initialize_schema=True)
    with TestClient(first_app) as client:
        created = client.post(
            "/v1/tasks", json={"input": {"text": "Persist this request"}}
        ).json()
    first_app.state.engine.dispose()

    second_app = create_app(database_url)
    with TestClient(second_app) as client:
        task_response = client.get(f"/v1/tasks/{created['task_id']}")
        intent_response = client.get(f"/v1/tasks/{created['task_id']}/intent")

    assert task_response.status_code == 200
    assert task_response.json()["source_request"] == "Persist this request"
    assert intent_response.status_code == 200
    assert intent_response.json()["version"] == 1


def test_source_request_hash_mismatch_is_reported(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'tampered.db'}", initialize_schema=True)
    with TestClient(app) as client:
        created = client.post(
            "/v1/tasks", json={"input": {"text": "Original request"}}
        ).json()
        with app.state.session_factory.begin() as session:
            row = session.scalar(select(SourceRequestRow))
            assert row is not None
            row.raw_text = "Changed request"

        response = client.get(f"/v1/tasks/{created['task_id']}")

    assert response.status_code == 500
    assert response.json()["detail"] == "Stored source request failed integrity check"


def test_task_creation_uses_injected_intent_extractor() -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Build a timer",
                domain="software",
                task_type="application",
                requirements=(
                    {
                        "text": "Show elapsed time",
                        "category": "functionality",
                        "priority": "mandatory",
                        "provenance": "explicit",
                        "source_location": "source_request.text",
                        "confidence": 0.99,
                    },
                ),
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=Extractor(),
    )
    with TestClient(app) as client:
        created = client.post(
            "/v1/tasks",
            json={"input": {"text": "Build a timer that shows elapsed time"}},
        ).json()
        intent = client.get(f"/v1/tasks/{created['task_id']}/intent").json()

    assert intent["task"]["domain"] == "software"
    assert intent["requirements"][0]["requirement_id"] == "REQ-001"


def test_task_creation_uses_deepseek_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    response_body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "objective": "Build a timer",
                                "domain": "software",
                                "task_type": "application",
                            }
                        )
                    }
                }
            ]
        }
    ).encode("utf-8")
    monkeypatch.setattr(
        "platform_core.providers.deepseek.urlopen",
        lambda *args, **kwargs: BytesIO(response_body),
    )
    app = create_app("sqlite:///:memory:", initialize_schema=True)

    with TestClient(app) as client:
        created = client.post(
            "/v1/tasks", json={"input": {"text": "Build a timer"}}
        ).json()
        intent = client.get(f"/v1/tasks/{created['task_id']}/intent").json()

    assert intent["task"]["objective"] == "Build a timer"
    assert intent["task"]["domain"] == "software"


def test_clarification_answer_creates_immutable_intent_version() -> None:
    class AmbiguousExtractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Write a research paper",
                domain="academic",
                task_type="research_writing",
                ambiguities=("Which citation style should be used?",),
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=AmbiguousExtractor(),
    )
    with TestClient(app) as client:
        created = client.post(
            "/v1/tasks", json={"input": {"text": "Write a research paper"}}
        ).json()
        task_id = created["task_id"]
        clarification = client.get(
            f"/v1/tasks/{task_id}/clarifications"
        ).json()[0]
        response = client.post(
            f"/v1/tasks/{task_id}/clarifications",
            json={
                "clarification_id": clarification["clarification_id"],
                "answer": {"value": "APA"},
            },
        )
        old_intent = client.get(
            f"/v1/tasks/{task_id}/intent?version=1"
        ).json()
        new_intent = client.get(f"/v1/tasks/{task_id}/intent").json()

    assert response.status_code == 200
    assert response.json()["intent_version"] == 2
    assert response.json()["task_status"] == "intent_draft"
    assert response.json()["clarification"]["status"] == "answered"
    assert response.json()["clarification"]["intent_version"] == 1
    assert old_intent["status"] == "needs_clarification"
    assert old_intent["version"] == 1
    assert new_intent["version"] == 2
    assert new_intent["status"] == "draft"
    assert new_intent["ambiguities"] == []
    assert new_intent["requirements"][0]["provenance"] == "clarified"
    assert "APA" in new_intent["requirements"][0]["text"]


def test_intent_approval_requires_all_clarifications_resolved() -> None:
    class AmbiguousExtractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Write a research paper",
                domain="academic",
                task_type="research_writing",
                ambiguities=("Which citation style should be used?",),
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=AmbiguousExtractor(),
    )
    with TestClient(app) as client:
        task_id = client.post(
            "/v1/tasks", json={"input": {"text": "Write a research paper"}}
        ).json()["task_id"]
        blocked = client.post(f"/v1/tasks/{task_id}/intent/approve")
        clarification = client.get(
            f"/v1/tasks/{task_id}/clarifications"
        ).json()[0]
        client.post(
            f"/v1/tasks/{task_id}/clarifications",
            json={
                "clarification_id": clarification["clarification_id"],
                "answer": {"value": "APA"},
            },
        )
        approved = client.post(f"/v1/tasks/{task_id}/intent/approve")
        repeated_approval = client.post(f"/v1/tasks/{task_id}/intent/approve")

    assert blocked.status_code == 409
    assert approved.status_code == 200
    assert approved.json()["version"] == 3
    assert approved.json()["status"] == "approved"
    assert repeated_approval.json()["version"] == 3


def test_not_specified_resolves_clarification_without_adding_requirement() -> None:
    class AmbiguousExtractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Write a research paper",
                domain="academic",
                task_type="research_writing",
                ambiguities=("Which citation style should be used?",),
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=AmbiguousExtractor(),
    )
    with TestClient(app) as client:
        task_id = client.post(
            "/v1/tasks", json={"input": {"text": "Write a research paper"}}
        ).json()["task_id"]
        clarification_id = client.get(
            f"/v1/tasks/{task_id}/clarifications"
        ).json()[0]["clarification_id"]
        response = client.post(
            f"/v1/tasks/{task_id}/clarifications",
            json={
                "clarification_id": clarification_id,
                "answer": {"value": "not specified"},
            },
        )
        intent = client.get(f"/v1/tasks/{task_id}/intent").json()

    assert response.status_code == 200
    assert response.json()["clarification"]["status"] == "skipped"
    assert intent["requirements"] == []
    assert intent["ambiguities"] == []


def test_answered_clarification_cannot_be_submitted_twice() -> None:
    class AmbiguousExtractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Write a research paper",
                domain="academic",
                task_type="research_writing",
                ambiguities=("Which citation style should be used?",),
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=AmbiguousExtractor(),
    )
    with TestClient(app) as client:
        task_id = client.post(
            "/v1/tasks", json={"input": {"text": "Write a research paper"}}
        ).json()["task_id"]
        clarification_id = client.get(
            f"/v1/tasks/{task_id}/clarifications"
        ).json()[0]["clarification_id"]
        answer = {
            "clarification_id": clarification_id,
            "answer": {"value": "APA"},
        }
        client.post(f"/v1/tasks/{task_id}/clarifications", json=answer)
        repeated = client.post(f"/v1/tasks/{task_id}/clarifications", json=answer)

    assert repeated.status_code == 409


def test_extraction_failure_is_reported_without_creating_task() -> None:
    class FailedExtractor:
        def extract(self, source_request):
            raise IntentExtractionError("provider unavailable")

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=FailedExtractor(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/tasks", json={"input": {"text": "Build a timer"}}
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Intent extraction failed"


def test_assurance_requires_approval_and_persists_report_and_output() -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Prepare a report",
                domain="business",
                task_type="report_writing",
                requirements=(
                    {
                        "text": "Include a summary",
                        "category": "structure",
                        "priority": "mandatory",
                        "provenance": "explicit",
                        "source_location": "source_request.text",
                    },
                ),
                acceptance_criteria=(
                    {
                        "description": "Include a Summary section",
                        "requirement_indexes": (0,),
                        "verification_method": "section_present:Summary",
                        "critical": True,
                    },
                ),
                risk_profile={"critical_requirement_indexes": (0,)},
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=Extractor(),
    )
    with TestClient(app) as client:
        task_id = client.post(
            "/v1/tasks",
            json={"input": {"text": "Prepare a report with a summary"}},
        ).json()["task_id"]
        blocked = client.post(
            f"/v1/tasks/{task_id}/assurance",
            json={"output": "# Summary\nReport body"},
        )
        approved = client.post(f"/v1/tasks/{task_id}/intent/approve")
        created = client.post(
            f"/v1/tasks/{task_id}/assurance",
            json={"output": "# Summary\nReport body"},
        )
        report_response = client.get(f"/v1/tasks/{task_id}/assurance")
        output_id = created.json()["output_id"]
        output_response = client.get(
            f"/v1/tasks/{task_id}/outputs/{output_id}"
        )

    assert blocked.status_code == 409
    assert approved.status_code == 200
    assert created.status_code == 201
    assert created.json()["overall_status"] == "all_checks_passed"
    assert created.json()["mandatory_gates"][0]["status"] == "supported"
    assert report_response.status_code == 200
    assert report_response.json()["report_id"] == created.json()["report_id"]
    assert output_response.status_code == 200
    assert output_response.json()["text"] == "# Summary\nReport body"
    assert output_response.json()["intent_version"] == approved.json()["version"]


def test_software_test_plan_assurance_is_discoverable_and_persisted() -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Prepare a software test plan",
                domain="software",
                task_type="test_plan",
                requirements=(
                    {
                        "text": "Include the requested test-case table",
                        "category": "testing",
                        "priority": "mandatory",
                        "provenance": "explicit",
                        "source_location": "source_request.text",
                    },
                ),
                acceptance_criteria=(
                    {
                        "description": "Include named test-case columns and a case",
                        "requirement_indexes": (0,),
                        "verification_method": (
                            "software_test_case_table:Test ID|Requirement IDs|"
                            "Scenario|Steps|Expected Result"
                        ),
                        "critical": True,
                    },
                ),
                risk_profile={"critical_requirement_indexes": (0,)},
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=Extractor(),
    )
    with TestClient(app) as client:
        modules = client.get("/v1/assurance/modules")
        task_id = client.post(
            "/v1/tasks",
            json={"input": {"text": "Prepare a software test plan with columns"}},
        ).json()["task_id"]
        approved = client.post(f"/v1/tasks/{task_id}/intent/approve")
        created = client.post(
            f"/v1/tasks/{task_id}/assurance",
            json={
                "output": (
                    "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
                    "| --- | --- | --- | --- | --- |\n"
                    "| TC-1 | REQ-001 | Empty input | Submit without credentials | "
                    "Show validation error |"
                )
            },
        )
        persisted = client.get(f"/v1/tasks/{task_id}/assurance")

    assert modules.status_code == 200
    assert modules.json()[0]["module_id"] == "software-test-plan"
    assert modules.json()[0]["supported_task_types"] == ["test_plan"]
    assert approved.status_code == 200
    assert created.status_code == 201
    assert created.json()["overall_status"] == "partially_verified"
    assert created.json()["criterion_results"][0]["status"] == "partially_supported"
    assert created.json()["criterion_results"][0]["review_required"]
    assert persisted.json()["report_id"] == created.json()["report_id"]


def test_business_report_uses_generic_assurance_without_domain_module() -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Prepare a business report",
                domain="business",
                task_type="report_writing",
                requirements=(
                    {
                        "text": "Include a Summary section",
                        "category": "structure",
                        "priority": "mandatory",
                        "provenance": "explicit",
                        "source_location": "source_request.text",
                    },
                ),
                acceptance_criteria=(
                    {
                        "description": "Include a Summary heading",
                        "requirement_indexes": (0,),
                        "verification_method": "section_present:Summary",
                    },
                ),
            )

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=Extractor(),
    )
    with TestClient(app) as client:
        modules = client.get("/v1/assurance/modules").json()
        task_id = client.post(
            "/v1/tasks",
            json={"input": {"text": "Prepare a business report with a Summary section"}},
        ).json()["task_id"]
        approved = client.post(f"/v1/tasks/{task_id}/intent/approve")
        created = client.post(
            f"/v1/tasks/{task_id}/assurance",
            json={"output": "# Summary\nKey results and decisions."},
        )
        persisted = client.get(f"/v1/tasks/{task_id}/assurance")

    assert not any(module["module_id"].startswith("business-") for module in modules)
    assert approved.status_code == 200
    assert created.status_code == 201
    assert created.json()["overall_status"] == "all_checks_passed"
    assert created.json()["criterion_results"][0]["status"] == "supported"
    assert persisted.json()["report_id"] == created.json()["report_id"]


def test_calibrated_run_generates_assures_and_persists_results() -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Prepare a business report",
                domain="business",
                task_type="report_writing",
                requirements=(
                    {
                        "text": "Include a Summary section",
                        "category": "structure",
                        "priority": "mandatory",
                        "provenance": "explicit",
                        "source_location": "source_request.text",
                    },
                ),
                acceptance_criteria=(
                    {
                        "description": "Include a Summary heading",
                        "requirement_indexes": (0,),
                        "verification_method": "section_present:Summary",
                    },
                ),
            )

    class Generator:
        def __init__(self):
            self.prompts = []

        def generate(self, prompt_text):
            self.prompts.append(prompt_text)
            return TextGenerationResult(
                text="# Summary\nKey results and decisions.",
                provider="fake-provider",
                model="fake-model",
                elapsed_seconds=0.25,
                input_tokens=120,
                output_tokens=30,
                total_tokens=150,
                token_usage_complete=True,
            )

    generator = Generator()
    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=Extractor(),
        text_generator=generator,
    )
    with TestClient(app) as client:
        task_id = client.post(
            "/v1/tasks",
            json={"input": {"text": "Prepare a business report with a Summary section"}},
        ).json()["task_id"]
        calibration_blocked = client.post(f"/v1/tasks/{task_id}/calibration")
        blocked = client.post(f"/v1/tasks/{task_id}/runs")
        assert calibration_blocked.status_code == 409
        assert blocked.status_code == 409
        assert generator.prompts == []

        approved = client.post(f"/v1/tasks/{task_id}/intent/approve")
        calibration = client.post(f"/v1/tasks/{task_id}/calibration")
        assert calibration.status_code == 200
        assert generator.prompts == []
        created = client.post(f"/v1/tasks/{task_id}/runs")
        run_id = created.json()["run_id"]
        retrieved = client.get(f"/v1/tasks/{task_id}/runs/{run_id}")
        output_id = created.json()["output"]["output_id"]
        output = client.get(f"/v1/tasks/{task_id}/outputs/{output_id}")

    assert approved.status_code == 200
    assert created.status_code == 201
    result = created.json()
    assert result["status"] == "completed"
    assert result["calibration_version"] == "0.1.0"
    assert result["prompt_hash"] == calibration.json()["prompt_hash"]
    assert "Original request (verbatim)" in result["calibrated_prompt"]
    assert "[REQ-001] (mandatory) Include a Summary section" in result["calibrated_prompt"]
    assert result["prompt_hash"].startswith("sha256:")
    assert result["provider"] == "fake-provider"
    assert result["provider_usage"]["total_tokens"] == 150
    assert result["output"]["text"] == "# Summary\nKey results and decisions."
    assert result["assurance_report"]["overall_status"] == "all_checks_passed"
    assert retrieved.status_code == 200
    assert retrieved.json()["run_id"] == run_id
    assert output.status_code == 200
    assert output.json()["text"] == result["output"]["text"]
    assert generator.prompts == [result["calibrated_prompt"]]


def test_failed_generation_is_persisted_without_output_or_report() -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Write a short report",
                domain="business",
                task_type="report_writing",
            )

    class FailedGenerator:
        def generate(self, prompt_text):
            raise TextGenerationError("provider unavailable")

    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=Extractor(),
        text_generator=FailedGenerator(),
    )
    with TestClient(app) as client:
        task_id = client.post(
            "/v1/tasks", json={"input": {"text": "Write a short report"}}
        ).json()["task_id"]
        client.post(f"/v1/tasks/{task_id}/intent/approve")
        failed = client.post(f"/v1/tasks/{task_id}/runs")
        run_id = failed.json()["detail"]["run_id"]
        retrieved = client.get(f"/v1/tasks/{task_id}/runs/{run_id}")

    assert failed.status_code == 502
    assert retrieved.status_code == 200
    assert retrieved.json()["status"] == "failed"
    assert retrieved.json()["error_message"] == "Text generation failed"
    assert retrieved.json()["output"] is None
    assert retrieved.json()["assurance_report"] is None


def test_execution_run_survives_app_restart(tmp_path) -> None:
    class Extractor:
        def extract(self, source_request):
            return IntentExtractionPayload(
                objective="Prepare a report",
                domain="business",
                task_type="report_writing",
                requirements=(
                    {
                        "text": "Include a Summary section",
                        "category": "structure",
                        "priority": "mandatory",
                        "provenance": "explicit",
                    },
                ),
                acceptance_criteria=(
                    {
                        "description": "Include a Summary heading",
                        "requirement_indexes": (0,),
                        "verification_method": "section_present:Summary",
                    },
                ),
            )

    class Generator:
        def generate(self, prompt_text):
            return TextGenerationResult(
                text="# Summary\nPersisted result.",
                provider="fake-provider",
                model="fake-model",
                elapsed_seconds=0.1,
            )

    database_url = f"sqlite:///{tmp_path / 'execution.db'}"
    first_app = create_app(
        database_url,
        initialize_schema=True,
        intent_extractor=Extractor(),
        text_generator=Generator(),
    )
    with TestClient(first_app) as client:
        task_id = client.post(
            "/v1/tasks", json={"input": {"text": "Prepare a report"}}
        ).json()["task_id"]
        client.post(f"/v1/tasks/{task_id}/intent/approve")
        created = client.post(f"/v1/tasks/{task_id}/runs")
        run_id = created.json()["run_id"]

    second_app = create_app(database_url)
    with TestClient(second_app) as client:
        retrieved = client.get(f"/v1/tasks/{task_id}/runs/{run_id}")

    assert created.status_code == 201
    assert retrieved.status_code == 200
    assert retrieved.json()["status"] == "completed"
    assert retrieved.json()["output"]["text"] == "# Summary\nPersisted result."
    assert retrieved.json()["assurance_report"]["overall_status"] == "all_checks_passed"


def test_assurance_rejects_blank_output_and_unknown_tasks() -> None:
    app = create_app("sqlite:///:memory:", initialize_schema=True)
    with TestClient(app) as client:
        blank = client.post(
            "/v1/tasks/00000000-0000-0000-0000-000000000001/assurance",
            json={"output": "   "},
        )
        missing_task = client.get(
            "/v1/tasks/00000000-0000-0000-0000-000000000001/assurance"
        )

    assert blank.status_code == 422
    assert missing_task.status_code == 404
