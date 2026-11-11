from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from platform_core.evaluation.intent_dataset import (
    AdjudicationStatus,
    DatasetNotReadyError,
    EvaluationCategory,
    EvaluationRunMetadata,
    evaluate_intent_dataset,
    load_development_dataset,
    require_dataset_readiness,
    dataset_readiness_blockers,
    requirement_precision_recall,
)
from platform_core.evaluation import run_intent
from platform_core.intent.extraction import (
    ExtractedAcceptanceCriterion,
    ExtractionTelemetry,
    IntentExtractionError,
    IntentExtractionPayload,
    IntentExtractionService,
)
from platform_core.intent.models import (
    IntentStatus,
    SourceRequest,
)


class StaticExtractor:
    def __init__(self, result: IntentExtractionPayload | dict) -> None:
        self.result = result

    def extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        return self.result


def test_development_dataset_is_valid_and_spans_initial_domains() -> None:
    dataset = load_development_dataset()

    assert len(dataset.cases) == 20
    assert {case.domain for case in dataset.cases} >= {
        "academic",
        "software",
        "creative",
        "business",
    }
    assert {case.case_id for case in dataset.cases} == {
        f"UAT-{index:04d}" for index in range(1, 21)
    }
    assert dataset.adjudication_status == AdjudicationStatus.NOT_ADJUDICATED
    assert all(case.test_categories for case in dataset.cases)
    assert EvaluationCategory.CITATION_TRAP in {
        category for case in dataset.cases for category in case.test_categories
    }


def test_current_development_set_is_blocked_from_release_benchmarking() -> None:
    dataset = load_development_dataset()

    blockers = dataset_readiness_blockers(dataset)

    assert "release evaluation requires a holdout split" in blockers
    assert "dataset cases have not been adjudicated" in blockers
    assert any("citation-trap cases require ground-truth sources" in b for b in blockers)
    assert any("lack expected Intent Record acceptance criteria" in b for b in blockers)
    with pytest.raises(DatasetNotReadyError, match="holdout split"):
        require_dataset_readiness(dataset)


def test_dataset_evaluation_returns_exact_metrics_and_keeps_diagnostic_limits() -> None:
    dataset = load_development_dataset()

    class CaseExtractor:
        last_usage = ExtractionTelemetry(
            elapsed_seconds=0.02,
            provider_requests=1,
            input_tokens=100,
            output_tokens=25,
            total_tokens=125,
            token_usage_complete=True,
        )

        def extract(self, source_request):
            case = next(
                item for item in dataset.cases if item.user_prompt == source_request.text
            )
            return case.expected_intent

    report = evaluate_intent_dataset(
        dataset,
        CaseExtractor(),
        run_metadata=EvaluationRunMetadata(
            provider="test",
            model="static-fixture",
            adapter_version="test",
            prompt_version="test",
        ),
        now=datetime(2026, 11, 10, tzinfo=timezone.utc),
    )

    assert report.case_count == 20
    assert report.successful_cases == 20
    assert report.failed_cases == 0
    assert report.total_extraction_seconds >= 0
    assert report.mean_extraction_seconds >= 0
    assert report.total_provider_requests == 20
    assert report.complete_token_usage_cases == 20
    assert report.input_tokens == 2000
    assert report.output_tokens == 500
    assert report.total_tokens == 2500
    assert report.adjudication_status == AdjudicationStatus.NOT_ADJUDICATED
    assert all(rate == 1 for rate in report.exact_match_rates.values())
    assert report.requirement_exact_micro.precision == 1
    assert report.requirement_exact_micro.recall == 1
    assert set(report.by_domain) >= {"academic", "software", "creative", "business"}
    assert set(report.by_difficulty) == {"easy", "moderate"}
    assert "control" in report.by_category
    assert report.dataset_readiness_blockers == dataset_readiness_blockers(dataset)
    assert any("not human-adjudicated" in limit for limit in report.limitations)


def test_evaluation_report_counts_extraction_failures_explicitly() -> None:
    dataset = load_development_dataset()

    class FailedExtractor:
        last_usage = ExtractionTelemetry(
            elapsed_seconds=0.03,
            provider_requests=1,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            token_usage_complete=False,
        )

        def extract(self, source_request):
            raise IntentExtractionError("provider failed")

    report = evaluate_intent_dataset(
        dataset,
        FailedExtractor(),
        run_metadata=EvaluationRunMetadata(
            provider="test",
            model="failure-fixture",
            adapter_version="test",
            prompt_version="test",
        ),
    )

    assert report.case_count == 20
    assert report.successful_cases == 0
    assert report.failed_cases == 20
    assert report.complete_token_usage_cases == 0
    assert report.input_tokens is None
    assert report.output_tokens is None
    assert report.total_tokens is None
    assert all(
        result.failure_kind == "intent_extraction_error"
        for result in report.case_results
    )


def test_live_evaluation_command_requires_provider_credentials(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(run_intent, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit, match="DEEPSEEK_API_KEY is required"):
        run_intent.main()


def test_extraction_service_preserves_original_and_assigns_stable_links() -> None:
    payload = IntentExtractionPayload(
        objective="Build a tool",
        domain="software",
        task_type="development",
        requirements=(
            {
                "text": "Include a test suite",
                "category": "testing",
                "priority": "mandatory",
                "provenance": "explicit",
                "source_location": "source_request.text",
                "confidence": 0.99,
            },
        ),
        acceptance_criteria=(
            ExtractedAcceptanceCriterion(
                description="The test suite passes", requirement_indexes=(0,)
            ),
        ),
        risk_profile={"critical_requirement_indexes": (0,)},
    )
    original_text = "  Build a tool and include a test suite.  "
    source = SourceRequest(
        text=original_text,
        received_at=datetime.now(timezone.utc),
    )
    task_id = uuid4()

    record = IntentExtractionService(StaticExtractor(payload)).extract(task_id, source)

    assert record.source_request.text == original_text
    assert record.task_id == task_id
    assert record.requirements[0].requirement_id == "REQ-001"
    assert record.acceptance_criteria[0].requirement_ids == ("REQ-001",)
    assert record.risk_profile.critical_requirement_ids == ("REQ-001",)
    assert record.status == IntentStatus.DRAFT


def test_ambiguities_require_user_input_status() -> None:
    payload = IntentExtractionPayload(
        objective="Write a report",
        domain="business",
        task_type="report",
        ambiguities=("audience is unspecified",),
    )
    record = IntentExtractionService(StaticExtractor(payload)).extract(
        uuid4(),
        SourceRequest(text="Write a report", received_at=datetime.now(timezone.utc)),
    )

    assert record.status == IntentStatus.NEEDS_CLARIFICATION


def test_invalid_extractor_payload_fails_explicitly() -> None:
    with pytest.raises(IntentExtractionError, match="invalid payload"):
        IntentExtractionService(
            StaticExtractor({"objective": "missing the required domain"})
        ).extract(
            uuid4(),
            SourceRequest(text="Do something", received_at=datetime.now(timezone.utc)),
        )


def test_blank_task_fields_fail_as_extraction_errors() -> None:
    with pytest.raises(IntentExtractionError, match="invalid payload"):
        IntentExtractionService(
            StaticExtractor(
                {
                    "objective": " ",
                    "domain": "software",
                    "task_type": "development",
                }
            )
        ).extract(
            uuid4(),
            SourceRequest(text="Build a tool", received_at=datetime.now(timezone.utc)),
        )


def test_source_location_must_use_a_source_request_path() -> None:
    with pytest.raises(ValidationError, match="source request path"):
        IntentExtractionPayload(
            objective="Build a tool",
            domain="software",
            task_type="development",
            requirements=(
                {
                    "text": "Include tests",
                    "category": "testing",
                    "priority": "mandatory",
                    "provenance": "explicit",
                    "source_location": "Include tests",
                },
            ),
        )


def test_inferred_mandatory_requirement_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot be mandatory"):
        IntentExtractionPayload(
            objective="Write a report",
            domain="business",
            task_type="report",
            requirements=(
                {
                    "text": "Use a formal tone",
                    "category": "style",
                    "priority": "mandatory",
                    "provenance": "inferred",
                    "confidence": 0.7,
                },
            ),
        )


def test_requirement_precision_and_recall_are_explicit() -> None:
    expected = IntentExtractionPayload(
        objective="Write",
        domain="productivity",
        task_type="writing",
        requirements=(
            {
                "text": "Keep it short",
                "category": "style",
                "priority": "mandatory",
                "provenance": "explicit",
            },
            {
                "text": "Include a summary",
                "category": "format",
                "priority": "mandatory",
                "provenance": "explicit",
            },
        ),
    )
    actual = IntentExtractionPayload(
        objective="Write",
        domain="productivity",
        task_type="writing",
        requirements=(
            {
                "text": "  KEEP it short ",
                "category": "style",
                "priority": "mandatory",
                "provenance": "explicit",
            },
            {
                "text": "Add an introduction",
                "category": "content",
                "priority": "preferred",
                "provenance": "explicit",
            },
        ),
    )

    assert requirement_precision_recall(expected, actual) == (0.5, 0.5)


def test_requirement_metric_counts_duplicates_instead_of_collapsing_them() -> None:
    expected = IntentExtractionPayload(
        objective="Write",
        domain="productivity",
        task_type="writing",
        requirements=(
            {
                "text": "Include a summary",
                "category": "format",
                "priority": "mandatory",
                "provenance": "explicit",
            },
        ),
    )
    actual = IntentExtractionPayload(
        objective="Write",
        domain="productivity",
        task_type="writing",
        requirements=(
            {
                "text": "Include a summary",
                "category": "format",
                "priority": "mandatory",
                "provenance": "explicit",
            },
            {
                "text": "Include a summary",
                "category": "format",
                "priority": "mandatory",
                "provenance": "explicit",
            },
        ),
    )

    assert requirement_precision_recall(expected, actual) == (0.5, 1)
