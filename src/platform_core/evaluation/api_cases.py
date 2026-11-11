from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from platform_core.intent.models import FrozenModel


class APITestCase(FrozenModel):
    case_id: str = Field(min_length=1)
    requirement_ids: tuple[str, ...] = Field(min_length=1)
    scenario: str = Field(min_length=1)
    operation: Literal["create_task"]
    input_text: str
    expected_status_code: Literal[201, 422]
    expected_task_status: Literal["received", "needs_user_input"] | None = None
    expected_source_request: str | None = None
    expected_error_detail: Literal["input.text must not be blank"] | None = None

    @model_validator(mode="after")
    def validate_expected_result(self) -> APITestCase:
        if self.expected_status_code == 201:
            if self.expected_task_status is None or self.expected_source_request is None:
                raise ValueError(
                    "successful task creation needs expected task status and source text"
                )
            if self.expected_error_detail is not None:
                raise ValueError("successful task creation cannot expect an error")
        elif self.expected_error_detail is None:
            raise ValueError("rejected task creation needs the expected error detail")
        elif self.expected_task_status is not None or self.expected_source_request is not None:
            raise ValueError("rejected task creation cannot expect a created task")
        return self


class APITestCaseSuite(FrozenModel):
    cases: tuple[APITestCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> APITestCaseSuite:
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)):
            raise ValueError("test case IDs must be unique")
        return self


class APITestCaseResult(FrozenModel):
    case_id: str
    passed: bool
    expected_status_code: Literal[201, 422]
    expected_task_status: Literal["received", "needs_user_input"] | None = None
    expected_source_request: str | None = None
    expected_error_detail: Literal["input.text must not be blank"] | None = None
    actual_status_code: int
    actual_task_status: str | None = None
    actual_source_request: str | None = None
    actual_error_detail: str | None = None
    failure_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def pass_status_matches_outcomes(self) -> APITestCaseResult:
        if self.expected_status_code == 201:
            outcomes_match = (
                self.actual_status_code == 201
                and self.actual_task_status == self.expected_task_status
                and self.actual_source_request == self.expected_source_request
            )
        else:
            outcomes_match = (
                self.actual_status_code == 422
                and self.actual_error_detail == self.expected_error_detail
            )
        if self.passed != outcomes_match:
            raise ValueError("passed status does not match expected and actual outcomes")
        return self


class APITestSuiteResult(FrozenModel):
    case_results: tuple[APITestCaseResult, ...]
    passed_cases: int
    failed_cases: int
    all_passed: bool

    @model_validator(mode="after")
    def counts_match_results(self) -> APITestSuiteResult:
        passed = sum(result.passed for result in self.case_results)
        failed = len(self.case_results) - passed
        if self.passed_cases != passed or self.failed_cases != failed:
            raise ValueError("suite counts do not match individual case results")
        if self.all_passed != (bool(self.case_results) and failed == 0):
            raise ValueError("all_passed does not match individual case results")
        return self


class APICaseEvaluationSubmission(FrozenModel):
    target_id: Literal["local_task_api"]
    oracle_version: str = Field(min_length=1)
    suite_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    result: APITestSuiteResult


class APICaseEvaluationRecord(FrozenModel):
    evaluation_id: UUID
    task_id: UUID
    run_id: UUID
    target_id: Literal["local_task_api"]
    oracle_version: str
    suite_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    result: APITestSuiteResult
    created_at: datetime


class APIResponse(Protocol):
    status_code: int

    def json(self) -> dict: ...


class TaskAPIClient(Protocol):
    def post(self, url: str, *, json: dict) -> APIResponse: ...

    def get(self, url: str) -> APIResponse: ...


def parse_api_test_cases(output: str) -> APITestCaseSuite:
    return APITestCaseSuite.model_validate_json(output)


def execute_api_test_cases(
    suite: APITestCaseSuite,
    client: TaskAPIClient,
) -> APITestSuiteResult:
    results = tuple(_execute_case(case, client) for case in suite.cases)
    passed = sum(result.passed for result in results)
    return APITestSuiteResult(
        case_results=results,
        passed_cases=passed,
        failed_cases=len(results) - passed,
        all_passed=passed == len(results),
    )


def _execute_case(case: APITestCase, client: TaskAPIClient) -> APITestCaseResult:
    response = client.post(
        "/v1/tasks",
        json={"input": {"text": case.input_text}},
    )
    failures: list[str] = []
    actual_task_status = None
    actual_source_request = None
    actual_error_detail = None

    if response.status_code != case.expected_status_code:
        failures.append(
            f"expected HTTP {case.expected_status_code}, got {response.status_code}"
        )
    elif response.status_code == 201:
        created = response.json()
        actual_task_status = created.get("status")
        task_id = created.get("task_id")
        if actual_task_status != case.expected_task_status:
            failures.append(
                f"expected task status {case.expected_task_status}, "
                f"got {actual_task_status}"
            )
        if not task_id:
            failures.append("successful response omitted task_id")
        else:
            task_response = client.get(f"/v1/tasks/{task_id}")
            if task_response.status_code != 200:
                failures.append(
                    f"expected task retrieval HTTP 200, got {task_response.status_code}"
                )
            else:
                actual_source_request = task_response.json().get("source_request")
                if actual_source_request != case.expected_source_request:
                    failures.append(
                        "retrieved source request did not match the expected text"
                    )
    elif response.status_code == 422:
        actual_error_detail = response.json().get("detail")
        if actual_error_detail != case.expected_error_detail:
            failures.append(
                f"expected error {case.expected_error_detail}, got {actual_error_detail}"
            )

    return APITestCaseResult(
        case_id=case.case_id,
        passed=not failures,
        expected_status_code=case.expected_status_code,
        expected_task_status=case.expected_task_status,
        expected_source_request=case.expected_source_request,
        expected_error_detail=case.expected_error_detail,
        actual_status_code=response.status_code,
        actual_task_status=actual_task_status,
        actual_source_request=actual_source_request,
        actual_error_detail=actual_error_detail,
        failure_reasons=tuple(failures),
    )