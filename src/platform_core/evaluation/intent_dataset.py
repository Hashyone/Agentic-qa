from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from platform_core.intent.extraction import (
    ExtractedRequirement,
    ExtractionTelemetry,
    IntentExtractionError,
    IntentExtractionPayload,
    IntentExtractionService,
    IntentExtractor,
)
from platform_core.intent.models import IntentRecord, Requirement, SourceRequest, utc_now

DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "evaluation_data"
    / "development"
    / "intent_cases.json"
)


class EvaluationCategory(StrEnum):
    CONTROL = "control"
    VAGUE_REQUEST = "vague_request"
    MISSING_CONTEXT = "missing_context"
    CONTRADICTORY_INSTRUCTIONS = "contradictory_instructions"
    HIDDEN_CONSTRAINTS = "hidden_constraints"
    FALSE_PREMISE = "false_premise"
    CITATION_TRAP = "citation_trap"
    NUMERICAL_TRAP = "numerical_trap"
    REQUIREMENT_CONFLICT = "requirement_conflict"
    PROMPT_INJECTION = "prompt_injection"
    MULTIMODAL_INCONSISTENCY = "multimodal_inconsistency"
    ADVERSARIAL_PHRASING = "adversarial_phrasing"
    OVER_SPECIFICATION = "over_specification"


class AdjudicationStatus(StrEnum):
    NOT_ADJUDICATED = "not_adjudicated"
    ADJUDICATED = "adjudicated"


class IntentCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^UAT-\d{4}$")
    dataset_version: str
    domain: str
    task_type: str
    difficulty: str
    user_prompt: str = Field(min_length=1)
    test_categories: tuple[EvaluationCategory, ...] = Field(min_length=1)
    context_assets: tuple[str, ...] = ()
    planted_issues: tuple[str, ...] = ()
    expected_intent: IntentExtractionPayload
    acceptable_clarifications: tuple[str, ...] = ()
    unsafe_assumptions: tuple[str, ...] = ()
    acceptance_tests: tuple[str, ...] = ()
    ground_truth_sources: tuple[str, ...] = ()
    adjudication_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def metadata_matches_expected_intent(self) -> IntentCase:
        if self.expected_intent.domain != self.domain:
            raise ValueError("case domain must match expected_intent.domain")
        if self.expected_intent.task_type != self.task_type:
            raise ValueError("case task_type must match expected_intent.task_type")
        return self


class IntentDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    split: str
    author_role: str = Field(min_length=1)
    reviewer_roles: tuple[str, ...] = ()
    adjudication_status: AdjudicationStatus
    cases: tuple[IntentCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def adjudication_requires_reviewers(self) -> IntentDataset:
        if (
            self.adjudication_status == AdjudicationStatus.ADJUDICATED
            and not self.reviewer_roles
        ):
            raise ValueError("an adjudicated dataset must record reviewer roles")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("case IDs must be unique within a dataset")
        if any(case.dataset_version != self.dataset_version for case in self.cases):
            raise ValueError("case dataset_version must match the dataset version")
        return self


def load_development_dataset() -> IntentDataset:
    return IntentDataset.model_validate_json(DATASET_PATH.read_text(encoding="utf-8"))


class MetricPair(BaseModel):
    precision: float
    recall: float
    true_positives: int = 0
    predicted: int = 0
    expected: int = 0


class IntentCaseEvaluation(BaseModel):
    case_id: str
    domain: str
    difficulty: str
    test_categories: tuple[EvaluationCategory, ...]
    extraction_succeeded: bool
    elapsed_seconds: float = Field(ge=0)
    provider_usage: ExtractionTelemetry | None = None
    exact_matches: dict[str, bool] = Field(default_factory=dict)
    requirement_exact_match: MetricPair | None = None
    ambiguity_exact_match: MetricPair | None = None
    failure_kind: str | None = None
    actual_intent: IntentExtractionPayload | None = None


class EvaluationRunMetadata(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)


class IntentEvaluationReport(BaseModel):
    dataset_version: str
    split: str
    adjudication_status: AdjudicationStatus
    run_metadata: EvaluationRunMetadata
    evaluation_kind: str = "dataset_diagnostic"
    case_count: int
    successful_cases: int
    failed_cases: int
    total_extraction_seconds: float
    mean_extraction_seconds: float
    total_provider_requests: int
    complete_token_usage_cases: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    exact_match_rates: dict[str, float]
    requirement_exact_micro: MetricPair
    requirement_exact_macro: MetricPair
    ambiguity_exact_micro: MetricPair
    ambiguity_exact_macro: MetricPair
    by_domain: dict[str, dict[str, float]]
    by_difficulty: dict[str, dict[str, float]]
    by_category: dict[str, dict[str, float]]
    dataset_readiness_blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    case_results: tuple[IntentCaseEvaluation, ...]


class DatasetNotReadyError(ValueError):
    pass


def require_dataset_readiness(dataset: IntentDataset) -> None:
    blockers = dataset_readiness_blockers(dataset)
    if blockers:
        raise DatasetNotReadyError("; ".join(blockers))


def dataset_readiness_blockers(dataset: IntentDataset) -> tuple[str, ...]:
    blockers: list[str] = []
    if dataset.split != "holdout":
        blockers.append("release evaluation requires a holdout split")
    if dataset.adjudication_status != AdjudicationStatus.ADJUDICATED:
        blockers.append("dataset cases have not been adjudicated")
    if not dataset.reviewer_roles:
        blockers.append("reviewer roles are not recorded")
    if any(not case.acceptance_tests for case in dataset.cases):
        blockers.append("one or more cases lack acceptance tests")
    if any(not case.expected_intent.acceptance_criteria for case in dataset.cases):
        blockers.append(
            "one or more cases lack expected Intent Record acceptance criteria"
        )
    observed_categories = {
        category for case in dataset.cases for category in case.test_categories
    }
    missing_categories = set(EvaluationCategory) - {
        EvaluationCategory.CONTROL
    } - observed_categories
    if missing_categories:
        blockers.append(
            "failure-mode coverage is missing: "
            + ", ".join(sorted(category.value for category in missing_categories))
        )
    if any(
        EvaluationCategory.CITATION_TRAP in case.test_categories
        and not case.ground_truth_sources
        for case in dataset.cases
    ):
        blockers.append("citation-trap cases require ground-truth sources")
    if any(case.domain == "legal" for case in dataset.cases) and not any(
        "legal" in role.casefold() for role in dataset.reviewer_roles
    ):
        blockers.append("legal cases require a qualified legal reviewer role")
    return tuple(blockers)


def evaluate_intent_dataset(
    dataset: IntentDataset,
    extractor: IntentExtractor,
    *,
    run_metadata: EvaluationRunMetadata,
    now: datetime | None = None,
) -> IntentEvaluationReport:
    evaluated_at = now or utc_now()
    case_results: list[IntentCaseEvaluation] = []
    for case in dataset.cases:
        source_request = SourceRequest(text=case.user_prompt, received_at=evaluated_at)
        started = perf_counter()
        try:
            intent = IntentExtractionService(extractor).extract(
                uuid4(), source_request
            )
        except IntentExtractionError:
            case_results.append(
                IntentCaseEvaluation(
                    case_id=case.case_id,
                    domain=case.domain,
                    difficulty=case.difficulty,
                    test_categories=case.test_categories,
                    extraction_succeeded=False,
                    elapsed_seconds=perf_counter() - started,
                    provider_usage=_extractor_usage(extractor),
                    failure_kind="intent_extraction_error",
                )
            )
            continue
        actual = _payload_from_record(intent)
        case_results.append(
            _evaluate_case(
                case,
                actual,
                elapsed_seconds=perf_counter() - started,
                provider_usage=_extractor_usage(extractor),
            )
        )
    return _build_report(dataset, tuple(case_results), run_metadata)


def requirement_precision_recall(
    expected: IntentExtractionPayload, actual: IntentExtractionPayload
) -> tuple[float, float]:
    metrics = _requirement_metrics(expected, actual)
    return metrics.precision, metrics.recall


def _evaluate_case(
    case: IntentCase,
    actual: IntentExtractionPayload,
    *,
    elapsed_seconds: float,
    provider_usage: ExtractionTelemetry | None,
) -> IntentCaseEvaluation:
    expected = case.expected_intent
    requirement_metrics = _requirement_metrics(expected, actual)
    ambiguity_metrics = _sequence_metrics(expected.ambiguities, actual.ambiguities)
    exact_matches = {
        "objective": _normalize(expected.objective) == _normalize(actual.objective),
        "domain": _normalize(expected.domain) == _normalize(actual.domain),
        "task_type": _normalize(expected.task_type) == _normalize(actual.task_type),
        "deliverables": _normalized_multiset(expected.deliverables)
        == _normalized_multiset(actual.deliverables),
        "context": _normalize_json(expected.context.model_dump(mode="json"))
        == _normalize_json(actual.context.model_dump(mode="json")),
        "quality_criteria": _normalized_multiset(expected.quality_criteria)
        == _normalized_multiset(actual.quality_criteria),
        "evidence_requirements": _normalized_multiset(expected.evidence_requirements)
        == _normalized_multiset(actual.evidence_requirements),
        "exclusions": _normalized_multiset(expected.exclusions)
        == _normalized_multiset(actual.exclusions),
        "requirements": requirement_metrics.precision == 1
        and requirement_metrics.recall == 1,
        "ambiguities": ambiguity_metrics.precision == 1
        and ambiguity_metrics.recall == 1,
        "assumptions": _normalized_multiset(expected.assumptions)
        == _normalized_multiset(actual.assumptions),
        "acceptance_criteria": _criterion_signatures(expected)
        == _criterion_signatures(actual),
        "risk_profile": (
            expected.risk_profile.level,
            expected.risk_profile.critical_requirement_indexes,
        )
        == (
            actual.risk_profile.level,
            actual.risk_profile.critical_requirement_indexes,
        ),
    }
    return IntentCaseEvaluation(
        case_id=case.case_id,
        domain=case.domain,
        difficulty=case.difficulty,
        test_categories=case.test_categories,
        extraction_succeeded=True,
        elapsed_seconds=elapsed_seconds,
        provider_usage=provider_usage,
        exact_matches=exact_matches,
        requirement_exact_match=requirement_metrics,
        ambiguity_exact_match=ambiguity_metrics,
        actual_intent=actual,
    )


def _build_report(
    dataset: IntentDataset,
    results: tuple[IntentCaseEvaluation, ...],
    run_metadata: EvaluationRunMetadata,
) -> IntentEvaluationReport:
    successful = tuple(result for result in results if result.extraction_succeeded)
    metric_names = (
        successful[0].exact_matches.keys() if successful else ()
    )
    exact_match_rates = {
        name: sum(result.exact_matches[name] for result in successful)
        / len(successful)
        for name in metric_names
    }
    requirement_metrics = tuple(
        result.requirement_exact_match
        for result in successful
        if result.requirement_exact_match is not None
    )
    ambiguity_metrics = tuple(
        result.ambiguity_exact_match
        for result in successful
        if result.ambiguity_exact_match is not None
    )
    domains = sorted({result.domain for result in results})
    difficulties = sorted({result.difficulty for result in results})
    return IntentEvaluationReport(
        dataset_version=dataset.dataset_version,
        split=dataset.split,
        adjudication_status=dataset.adjudication_status,
        run_metadata=run_metadata,
        case_count=len(results),
        successful_cases=len(successful),
        failed_cases=len(results) - len(successful),
        total_extraction_seconds=sum(result.elapsed_seconds for result in results),
        mean_extraction_seconds=(
            sum(result.elapsed_seconds for result in results) / len(results)
            if results
            else 0
        ),
        total_provider_requests=sum(
            result.provider_usage.provider_requests
            for result in results
            if result.provider_usage is not None
        ),
        complete_token_usage_cases=sum(
            result.provider_usage is not None
            and result.provider_usage.token_usage_complete
            for result in results
        ),
        input_tokens=_sum_token_field(results, "input_tokens"),
        output_tokens=_sum_token_field(results, "output_tokens"),
        total_tokens=_sum_token_field(results, "total_tokens"),
        exact_match_rates=exact_match_rates,
        requirement_exact_micro=_aggregate_metrics(requirement_metrics),
        requirement_exact_macro=_mean_metrics(requirement_metrics),
        ambiguity_exact_micro=_aggregate_metrics(ambiguity_metrics),
        ambiguity_exact_macro=_mean_metrics(ambiguity_metrics),
        by_domain={
            domain: _group_exact_match_rates(results, domain=domain)
            for domain in domains
        },
        by_difficulty={
            difficulty: _group_exact_match_rates(results, difficulty=difficulty)
            for difficulty in difficulties
        },
        by_category={
            category.value: _group_exact_match_rates(results, category=category)
            for category in sorted(
                {
                    category
                    for result in results
                    for category in result.test_categories
                },
                key=lambda item: item.value,
            )
        },
        dataset_readiness_blockers=dataset_readiness_blockers(dataset),
        limitations=(
            "This is a diagnostic report, not a pre-registered comparative "
            "benchmark or release evidence.",
            "This evaluator does not run baseline comparisons, repeated trials, "
            "human adjudication, or confidence-interval analysis.",
            "Requirement matches require strict normalized text and exact "
            "category, priority, provenance, and source-location agreement; "
            "ambiguity matches use strict normalized text, so paraphrases can "
            "be counted as mismatches.",
            *(
                ("Dataset expected intents are not human-adjudicated.",)
                if dataset.adjudication_status == AdjudicationStatus.NOT_ADJUDICATED
                else ()
            ),
            *(
                (f"Dataset split is {dataset.split}, not a hidden holdout.",)
                if dataset.split != "holdout"
                else ()
            ),
            "Exact match does not establish semantic correctness or calibrated "
            "confidence.",
        ),
        case_results=results,
    )


def _group_exact_match_rates(
    results: tuple[IntentCaseEvaluation, ...],
    *,
    domain: str | None = None,
    difficulty: str | None = None,
    category: EvaluationCategory | None = None,
) -> dict[str, float]:
    group = tuple(
        result
        for result in results
        if result.extraction_succeeded
        and (domain is None or result.domain == domain)
        and (difficulty is None or result.difficulty == difficulty)
        and (category is None or category in result.test_categories)
    )
    if not group:
        return {}
    metric_names = group[0].exact_matches.keys()
    result = {
        name: sum(result.exact_matches[name] for result in group) / len(group)
        for name in metric_names
    }
    requirement_metrics = _aggregate_metrics(
        tuple(
            item.requirement_exact_match
            for item in group
            if item.requirement_exact_match is not None
        )
    )
    ambiguity_metrics = _aggregate_metrics(
        tuple(
            item.ambiguity_exact_match
            for item in group
            if item.ambiguity_exact_match is not None
        )
    )
    result.update(
        requirement_precision_micro=requirement_metrics.precision,
        requirement_recall_micro=requirement_metrics.recall,
        ambiguity_precision_micro=ambiguity_metrics.precision,
        ambiguity_recall_micro=ambiguity_metrics.recall,
    )
    return result


def _requirement_metrics(
    expected: IntentExtractionPayload, actual: IntentExtractionPayload
) -> MetricPair:
    expected_requirements = Counter(
        _requirement_signature(item) for item in expected.requirements
    )
    actual_requirements = Counter(
        _requirement_signature(item) for item in actual.requirements
    )
    true_positives = sum((expected_requirements & actual_requirements).values())
    return _metric_pair(
        true_positives, sum(actual_requirements.values()), sum(expected_requirements.values())
    )


def _sequence_metrics(expected: tuple[str, ...], actual: tuple[str, ...]) -> MetricPair:
    expected_values = Counter(_normalize(item) for item in expected)
    actual_values = Counter(_normalize(item) for item in actual)
    true_positives = sum((expected_values & actual_values).values())
    return _metric_pair(
        true_positives, sum(actual_values.values()), sum(expected_values.values())
    )


def _metric_pair(true_positives: int, predicted: int, expected: int) -> MetricPair:
    precision = true_positives / predicted if predicted else (1.0 if not expected else 0.0)
    recall = true_positives / expected if expected else (1.0 if not predicted else 0.0)
    return MetricPair(precision=precision, recall=recall)


def _aggregate_metrics(metrics: tuple[MetricPair, ...]) -> MetricPair:
    if not metrics:
        return MetricPair(precision=0, recall=0)
    true_positives = sum(item.true_positives for item in metrics)
    predicted = sum(item.predicted for item in metrics)
    expected = sum(item.expected for item in metrics)
    return MetricPair(
        precision=true_positives / predicted if predicted else (1.0 if not expected else 0.0),
        recall=true_positives / expected if expected else (1.0 if not predicted else 0.0),
        true_positives=true_positives,
        predicted=predicted,
        expected=expected,
    )


def _mean_metrics(metrics: tuple[MetricPair, ...]) -> MetricPair:
    if not metrics:
        return MetricPair(precision=0, recall=0)
    return MetricPair(
        precision=sum(item.precision for item in metrics) / len(metrics),
        recall=sum(item.recall for item in metrics) / len(metrics),
        true_positives=sum(item.true_positives for item in metrics),
        predicted=sum(item.predicted for item in metrics),
        expected=sum(item.expected for item in metrics),
    )


def _requirement_signature(
    requirement: ExtractedRequirement | Requirement,
) -> tuple[str, str, str, str, str]:
    return (
        _normalize(requirement.text),
        _normalize(requirement.category),
        requirement.priority.value,
        requirement.provenance.value,
        _normalize(requirement.source_location or ""),
    )


def _criterion_signatures(
    payload: IntentExtractionPayload,
) -> tuple[tuple[str, tuple[int, ...], str, bool], ...]:
    return tuple(
        sorted(
            (
                _normalize(criterion.description),
                tuple(sorted(criterion.requirement_indexes)),
                _normalize(criterion.verification_method or ""),
                criterion.critical,
            )
            for criterion in payload.acceptance_criteria
        )
    )


def _payload_from_record(record: IntentRecord) -> IntentExtractionPayload:
    return IntentExtractionPayload(
        objective=record.task.objective,
        domain=record.task.domain,
        task_type=record.task.task_type,
        deliverables=record.task.deliverables,
        context=record.context,
        requirements=tuple(
            {
                "text": item.text,
                "category": item.category,
                "priority": item.priority,
                "provenance": item.provenance,
                "source_location": item.source_location,
                "confidence": item.confidence,
            }
            for item in record.requirements
        ),
        quality_criteria=record.quality_criteria,
        evidence_requirements=record.evidence_requirements,
        exclusions=record.exclusions,
        ambiguities=record.ambiguities,
        assumptions=record.assumptions,
        acceptance_criteria=tuple(
            {
                "description": item.description,
                "requirement_indexes": tuple(
                    index
                    for index, requirement in enumerate(record.requirements)
                    if requirement.requirement_id in item.requirement_ids
                ),
                "verification_method": item.verification_method,
                "critical": item.critical,
            }
            for item in record.acceptance_criteria
        ),
        risk_profile={
            "level": record.risk_profile.level,
            "critical_requirement_indexes": tuple(
                index
                for index, requirement in enumerate(record.requirements)
                if requirement.requirement_id
                in record.risk_profile.critical_requirement_ids
            ),
        },
    )


def _normalized_multiset(values: tuple[str, ...]) -> Counter[str]:
    return Counter(_normalize(value) for value in values)


def _normalize_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _extractor_usage(extractor: IntentExtractor) -> ExtractionTelemetry | None:
    usage = getattr(extractor, "last_usage", None)
    return usage if isinstance(usage, ExtractionTelemetry) else None


def _sum_token_field(
    results: tuple[IntentCaseEvaluation, ...], field: str
) -> int | None:
    complete_usage = tuple(
        result.provider_usage
        for result in results
        if result.provider_usage is not None
        and result.provider_usage.token_usage_complete
    )
    if not complete_usage:
        return None
    if any(getattr(usage, field) is None for usage in complete_usage):
        return None
    return sum(int(getattr(usage, field)) for usage in complete_usage)
