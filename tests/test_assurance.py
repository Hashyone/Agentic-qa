from datetime import datetime, timezone
from uuid import uuid4

from platform_core.assurance.engine import AssuranceEngine
from platform_core.assurance.models import (
    OverallAssuranceStatus,
    VerificationStatus,
)
from platform_core.intent.extraction import (
    IntentExtractionPayload,
    IntentExtractionService,
)
from platform_core.intent.models import SourceRequest


class StaticExtractor:
    def __init__(self, payload: IntentExtractionPayload) -> None:
        self.payload = payload

    def extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        return self.payload


def _intent(
    verification_method: str | None,
    *,
    domain: str = "business",
    task_type: str = "report_writing",
    requirements: tuple[dict, ...] | None = None,
):
    payload = IntentExtractionPayload(
        objective="Prepare a report",
        domain=domain,
        task_type=task_type,
        requirements=requirements or (
            {
                "text": "Include a summary",
                "category": "structure",
                "priority": "mandatory",
                "provenance": "explicit",
            },
        ),
        acceptance_criteria=(
            {
                "description": "Include a Summary section",
                "requirement_indexes": (0,),
                "verification_method": verification_method,
                "critical": True,
            },
        ),
        risk_profile={"critical_requirement_indexes": (0,)},
    )
    return IntentExtractionService(StaticExtractor(payload)).extract(
        uuid4(),
        SourceRequest(text="Prepare a report with a summary", received_at=datetime.now(timezone.utc)),
    )


def test_deterministic_heading_check_passes_critical_requirement() -> None:
    report = AssuranceEngine().evaluate(
        _intent("section_present:Summary"),
        "# Summary\nHere is the report.",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.ALL_CHECKS_PASSED
    assert report.criterion_results[0].status == VerificationStatus.SUPPORTED
    assert report.mandatory_gates[0].status == VerificationStatus.SUPPORTED
    assert report.mandatory_gates[0].critical
    assert "does not establish semantic correctness" in report.limitations[0]


def test_missing_critical_heading_prevents_all_checks_passed() -> None:
    report = AssuranceEngine().evaluate(
        _intent("section_present:Summary"),
        "# Overview\nHere is the report.",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.PARTIALLY_VERIFIED
    assert report.criterion_results[0].status == VerificationStatus.CONTRADICTED
    assert report.mandatory_gates[0].status == VerificationStatus.CONTRADICTED


def test_unknown_check_is_explicitly_sent_for_human_review() -> None:
    report = AssuranceEngine().evaluate(
        _intent("semantic_quality"),
        "A concise report.",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.REQUIRES_HUMAN_REVIEW
    assert report.criterion_results[0].status == VerificationStatus.UNAVAILABLE
    assert report.criterion_results[0].review_required
    assert report.human_review_items


def test_software_test_plan_module_checks_requested_table_headers_and_rows() -> None:
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="software",
            task_type="test_plan",
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Empty input | Submit without credentials | "
        "Show validation error |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.PARTIALLY_VERIFIED
    assert report.criterion_results[0].status == VerificationStatus.PARTIALLY_SUPPORTED
    assert report.criterion_results[0].review_required
    assert report.human_review_items
    assert "semantically correct" in report.criterion_results[0].explanation


def test_software_test_plan_module_contradicts_missing_requested_table() -> None:
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="software",
            task_type="test_plan",
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Actual Result |\n"
        "| --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Empty input | Submit without credentials | Error |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.PARTIALLY_VERIFIED
    assert report.criterion_results[0].status == VerificationStatus.CONTRADICTED


def test_software_test_plan_rejects_uncovered_mandatory_requirement() -> None:
    requirements = (
        {
            "text": "Include a summary",
            "category": "structure",
            "priority": "mandatory",
            "provenance": "explicit",
        },
        {
            "text": "Include the test for an empty password",
            "category": "functionality",
            "priority": "mandatory",
            "provenance": "explicit",
        },
    )
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="software",
            task_type="test_plan",
            requirements=requirements,
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Empty input | Submit without password | Show error |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.criterion_results[0].status == VerificationStatus.CONTRADICTED
    assert "REQ-002" in report.criterion_results[0].explanation


def test_software_test_plan_does_not_treat_format_as_behavior_coverage() -> None:
    requirements = (
        {
            "text": "When both credentials are empty, show validation errors",
            "category": "functionality",
            "priority": "mandatory",
            "provenance": "explicit",
        },
        {
            "text": "Present the cases in a Markdown table with the named columns",
            "category": "format",
            "priority": "mandatory",
            "provenance": "explicit",
        },
    )
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Requirement IDs|Scenario|Steps|Expected Result",
            domain="software",
            task_type="test_plan",
            requirements=requirements,
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Both credentials empty | Submit the form | Show both errors |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.criterion_results[0].status == VerificationStatus.PARTIALLY_SUPPORTED
    assert report.overall_status == OverallAssuranceStatus.PARTIALLY_VERIFIED


def test_software_test_plan_rejects_unknown_requirement_ids() -> None:
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="software",
            task_type="test_plan",
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-999 | Empty input | Submit without credentials | Show error |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.criterion_results[0].status == VerificationStatus.CONTRADICTED
    assert "REQ-999" in report.criterion_results[0].explanation


def test_software_test_plan_rejects_duplicate_test_ids() -> None:
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="software",
            task_type="test_plan",
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Empty input | Submit without credentials | Show error |\n"
        "| TC-1 | REQ-001 | Valid input | Submit valid credentials | Show dashboard |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.criterion_results[0].status == VerificationStatus.CONTRADICTED
    assert "duplicated" in report.criterion_results[0].explanation


def test_software_test_plan_rejects_incomplete_test_case_fields() -> None:
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="software",
            task_type="test_plan",
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Empty input | | Show error |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.criterion_results[0].status == VerificationStatus.CONTRADICTED
    assert "missing a required field" in report.criterion_results[0].explanation


def test_domain_check_is_unavailable_outside_its_declared_task_scope() -> None:
    report = AssuranceEngine().evaluate(
        _intent(
            "software_test_case_table:Test ID|Scenario|Expected Result",
            domain="business",
            task_type="report_writing",
        ),
        "| Test ID | Requirement IDs | Scenario | Steps | Expected Result |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TC-1 | REQ-001 | Empty input | Submit without credentials | Error |",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.REQUIRES_HUMAN_REVIEW
    assert report.criterion_results[0].status == VerificationStatus.UNAVAILABLE
    assert "unavailable" in report.criterion_results[0].explanation


def test_case_existence_is_not_verified_by_including_a_citation() -> None:
    payload = IntentExtractionPayload(
        objective="Draft heads of argument",
        domain="legal",
        task_type="legal_writing",
        requirements=(
            {
                "text": "Use real, verifiable South African cases",
                "category": "legal_authorities",
                "priority": "mandatory",
                "provenance": "explicit",
            },
        ),
        acceptance_criteria=(
            {
                "description": (
                    "Verify that each cited case exists and supports the proposition"
                ),
                "requirement_indexes": (0,),
                "verification_method": "case_existence_and_support",
                "critical": True,
            },
        ),
        risk_profile={"critical_requirement_indexes": (0,)},
    )
    intent = IntentExtractionService(StaticExtractor(payload)).extract(
        uuid4(),
        SourceRequest(
            text="Draft heads of argument using real South African cases",
            received_at=datetime.now(timezone.utc),
        ),
    )
    report = AssuranceEngine().evaluate(
        intent,
        "Kruger v Coetzee 1966 (2) SA 428 (A).",
        output_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert report.overall_status == OverallAssuranceStatus.REQUIRES_HUMAN_REVIEW
    assert report.criterion_results[0].status == VerificationStatus.UNAVAILABLE
    assert report.mandatory_gates[0].status == VerificationStatus.UNAVAILABLE
    assert "each cited case exists" in report.criterion_results[0].explanation
