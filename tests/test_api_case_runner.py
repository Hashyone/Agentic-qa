import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from platform_core.api.app import create_app
from platform_core.evaluation.api_cases import (
    APICaseEvaluationSubmission,
    APITestCaseSuite,
    execute_api_test_cases,
    parse_api_test_cases,
)
from platform_core.intent.extraction import IntentExtractionPayload
from platform_core.intent.models import SourceRequest, hash_source_text
from platform_core.providers.generation import TextGenerationResult


class StaticExtractor:
    def extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        return IntentExtractionPayload(
            objective="Accept a task",
            domain="software",
            task_type="task_creation",
        )


def _suite(expected_success_text: str) -> APITestCaseSuite:
    return APITestCaseSuite(
        cases=(
            {
                "case_id": "TASK-VALID-001",
                "requirement_ids": ["REQ-001"],
                "scenario": "A nonblank request is accepted and preserved",
                "operation": "create_task",
                "input_text": "Create a test task",
                "expected_status_code": 201,
                "expected_task_status": "received",
                "expected_source_request": expected_success_text,
            },
            {
                "case_id": "TASK-BLANK-001",
                "requirement_ids": ["REQ-002"],
                "scenario": "A whitespace-only request is rejected",
                "operation": "create_task",
                "input_text": "   ",
                "expected_status_code": 422,
                "expected_error_detail": "input.text must not be blank",
            },
        )
    )


def test_generated_api_cases_execute_against_isolated_real_api() -> None:
    suite = _suite("Create a test task")
    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=StaticExtractor(),
    )

    with TestClient(app) as client:
        result = execute_api_test_cases(suite, client)

    assert result.all_passed
    assert result.passed_cases == 2
    assert result.failed_cases == 0
    assert result.case_results[0].actual_status_code == 201
    assert result.case_results[0].actual_source_request == "Create a test task"
    assert result.case_results[1].actual_status_code == 422
    assert result.case_results[1].actual_error_detail == "input.text must not be blank"


def test_incorrect_expected_result_is_rejected_by_real_api_execution() -> None:
    suite = _suite("A different expected request")
    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=StaticExtractor(),
    )

    with TestClient(app) as client:
        result = execute_api_test_cases(suite, client)

    assert not result.all_passed
    assert result.passed_cases == 1
    assert result.failed_cases == 1
    assert result.case_results[0].failure_reasons == (
        "retrieved source request did not match the expected text",
    )


def test_parser_rejects_non_allowlisted_operations_and_paths() -> None:
    with pytest.raises(ValidationError):
        parse_api_test_cases(
            json.dumps(
                {
                    "cases": [
                        {
                            "case_id": "TASK-001",
                            "requirement_ids": ["REQ-001"],
                            "scenario": "Try an arbitrary operation",
                            "operation": "delete_all",
                            "input_text": "x",
                            "expected_status_code": 201,
                            "expected_task_status": "received",
                            "expected_source_request": "x",
                            "path": "https://example.invalid",
                        }
                    ]
                }
            )
        )


def test_case_execution_record_is_tied_to_generated_output_and_survives_restart(
    tmp_path,
) -> None:
    suite_output = json.dumps(
        {
            "cases": [
                {
                    "case_id": "TASK-VALID-001",
                    "requirement_ids": ["REQ-001"],
                    "scenario": "A nonblank request is accepted and preserved",
                    "operation": "create_task",
                    "input_text": "Create a persisted test task",
                    "expected_status_code": 201,
                    "expected_task_status": "received",
                    "expected_source_request": "Create a persisted test task",
                    "expected_error_detail": None,
                }
            ]
        }
    )

    class Generator:
        def generate(self, prompt_text: str) -> TextGenerationResult:
            return TextGenerationResult(
                text=suite_output,
                provider="fake-provider",
                model="fake-model",
                elapsed_seconds=0.1,
            )

    workflow_app = create_app(
        f"sqlite:///{tmp_path / 'case-evaluations.db'}",
        initialize_schema=True,
        intent_extractor=StaticExtractor(),
        text_generator=Generator(),
    )
    with TestClient(workflow_app) as workflow:
        task_id = workflow.post(
            "/v1/tasks", json={"input": {"text": "Create a test suite"}}
        ).json()["task_id"]
        workflow.post(f"/v1/tasks/{task_id}/intent/approve")
        run = workflow.post(f"/v1/tasks/{task_id}/runs").json()
        suite = parse_api_test_cases(run["output"]["text"])

        target_app = create_app(
            "sqlite:///:memory:",
            initialize_schema=True,
            intent_extractor=StaticExtractor(),
        )
        with TestClient(target_app) as target:
            result = execute_api_test_cases(suite, target)
        assert result.all_passed

        submission = APICaseEvaluationSubmission(
            target_id="local_task_api",
            oracle_version="task-create-contract-v1",
            suite_hash=hash_source_text(run["output"]["text"]),
            result=result,
        )
        mismatched_result = result.model_copy(
            update={
                "case_results": (
                    result.case_results[0].model_copy(update={"case_id": "OTHER-CASE"}),
                )
            }
        )
        rejected = workflow.post(
            f"/v1/tasks/{task_id}/runs/{run['run_id']}/case-evaluations",
            json=submission.model_copy(update={"result": mismatched_result}).model_dump(
                mode="json"
            ),
        )
        assert rejected.status_code == 409

        saved = workflow.post(
            f"/v1/tasks/{task_id}/runs/{run['run_id']}/case-evaluations",
            json=submission.model_dump(mode="json"),
        )
        assert saved.status_code == 201
        evaluation_id = saved.json()["evaluation_id"]

    reopened_app = create_app(f"sqlite:///{tmp_path / 'case-evaluations.db'}")
    with TestClient(reopened_app) as reopened:
        retrieved = reopened.get(
            f"/v1/tasks/{task_id}/runs/{run['run_id']}/case-evaluations"
        )

    assert retrieved.status_code == 200
    assert len(retrieved.json()) == 1
    assert retrieved.json()[0]["evaluation_id"] == evaluation_id
    assert retrieved.json()[0]["suite_hash"] == hash_source_text(suite_output)
    assert retrieved.json()[0]["result"]["all_passed"]