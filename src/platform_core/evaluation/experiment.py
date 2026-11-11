from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExperimentalCondition(StrEnum):
    CONVENTIONAL_PROMPTING = "baseline_a"
    PROMPT_OPTIMISATION = "baseline_b"
    FULL_PLATFORM = "treatment_c"


class VerifierConfusionCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)


class ExperimentObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    condition: ExperimentalCondition
    repetition: int = Field(ge=1)
    provider: str = Field(min_length=1, description="Primary provider for the run.")
    model: str = Field(min_length=1, description="Primary model for the run.")
    configuration_id: str = Field(
        min_length=1, description="Identifier for the run's frozen configuration."
    )
    elapsed_seconds: float = Field(ge=0)
    elapsed_to_acceptable_seconds: float | None = Field(default=None, ge=0)
    user_active_seconds: float | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Input tokens summed across all provider calls in this run.",
    )
    output_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Output tokens summed across all provider calls in this run.",
    )
    token_usage_complete: bool = False
    clarification_questions: int = Field(ge=0)
    clarification_turns: int = Field(ge=0)
    human_accepted: bool | None = None
    mandatory_criteria_total: int = Field(ge=0)
    mandatory_criteria_passed: int = Field(ge=0)
    verifier_counts: VerifierConfusionCounts | None = None
    adjudicated: bool

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.mandatory_criteria_passed > self.mandatory_criteria_total:
            raise ValueError("passed mandatory criteria cannot exceed total criteria")
        if self.adjudicated != (self.human_accepted is not None):
            raise ValueError("human_accepted must be present exactly when adjudicated")
        if self.human_accepted and self.elapsed_to_acceptable_seconds is None:
            raise ValueError("accepted output needs elapsed time to acceptance")
        if not self.human_accepted and self.elapsed_to_acceptable_seconds is not None:
            raise ValueError("unaccepted output cannot have elapsed time to acceptance")
        if (
            self.elapsed_to_acceptable_seconds is not None
            and self.elapsed_to_acceptable_seconds > self.elapsed_seconds
        ):
            raise ValueError("time to acceptance cannot exceed total elapsed time")
        if self.token_usage_complete and (
            self.input_tokens is None or self.output_tokens is None
        ):
            raise ValueError("complete token usage needs both input and output totals")
        return self

    @property
    def total_tokens(self) -> int | None:
        if (
            not self.token_usage_complete
            or self.input_tokens is None
            or self.output_tokens is None
        ):
            return None
        return self.input_tokens + self.output_tokens


class ConditionSummary(BaseModel):
    observation_count: int
    providers: tuple[str, ...]
    models: tuple[str, ...]
    configuration_ids: tuple[str, ...]
    adjudicated_count: int
    human_accepted_count: int
    human_acceptance_rate: float | None
    quality_accepted_count: int
    quality_success_rate: float | None
    mean_elapsed_seconds: float | None
    mean_elapsed_to_acceptable_seconds: float | None
    mean_user_active_seconds: float | None
    user_active_time_coverage: float
    mean_input_tokens: float | None
    mean_output_tokens: float | None
    mean_total_tokens: float | None
    token_usage_coverage: float
    mean_clarification_questions: float | None
    mean_clarification_turns: float | None
    mandatory_criterion_pass_rate: float | None
    verifier_evaluated_count: int
    verifier_true_positives: int
    verifier_false_positives: int
    verifier_false_negatives: int
    verifier_precision: float | None
    verifier_recall: float | None


class PairedSavings(BaseModel):
    comparison: str
    matched_pairs: int
    quality_accepted_pairs: int
    token_measured_quality_accepted_pairs: int
    mean_seconds_saved: float | None
    mean_seconds_saved_percent: float | None
    mean_user_active_seconds_saved: float | None
    mean_tokens_saved: float | None
    mean_tokens_saved_percent: float | None


class ExperimentComparison(BaseModel):
    evaluation_kind: str = "descriptive_paired_comparison"
    condition_summaries: dict[ExperimentalCondition, ConditionSummary]
    by_domain: dict[str, dict[ExperimentalCondition, ConditionSummary]]
    by_difficulty: dict[str, dict[ExperimentalCondition, ConditionSummary]]
    paired_savings: tuple[PairedSavings, ...]
    limitations: tuple[str, ...]


def compare_experiment_conditions(
    observations: tuple[ExperimentObservation, ...],
) -> ExperimentComparison:
    _validate_unique_repetitions(observations)
    domains = sorted({item.domain for item in observations})
    difficulties = sorted({item.difficulty for item in observations})
    summaries = {
        condition: _summarize(
            tuple(item for item in observations if item.condition == condition)
        )
        for condition in ExperimentalCondition
    }
    by_domain = {
        domain: {
            condition: _summarize(
                tuple(
                    item
                    for item in observations
                    if item.domain == domain and item.condition == condition
                )
            )
            for condition in ExperimentalCondition
        }
        for domain in domains
    }
    by_difficulty = {
        difficulty: {
            condition: _summarize(
                tuple(
                    item
                    for item in observations
                    if item.difficulty == difficulty and item.condition == condition
                )
            )
            for condition in ExperimentalCondition
        }
        for difficulty in difficulties
    }
    savings = tuple(
        _paired_savings(
            observations,
            baseline=baseline,
            treatment=ExperimentalCondition.FULL_PLATFORM,
        )
        for baseline in (
            ExperimentalCondition.CONVENTIONAL_PROMPTING,
            ExperimentalCondition.PROMPT_OPTIMISATION,
        )
    )
    return ExperimentComparison(
        condition_summaries=summaries,
        by_domain=by_domain,
        by_difficulty=by_difficulty,
        paired_savings=savings,
        limitations=(
            "Descriptive comparisons only; no confidence intervals or significance "
            "tests are calculated.",
            "Time and token savings are compared only for matched runs whose "
            "outputs were human-adjudicated as accepted.",
            "Elapsed seconds are task wall-clock duration; user-active seconds "
            "are separately recorded and may be unavailable.",
            "Acceptance rates use only adjudicated observations; report the "
            "adjudicated count and do not infer missing labels.",
            "Token usage is unavailable when either input or output tokens are "
            "missing or the all-call usage ledger is incomplete; no token "
            "estimates are substituted.",
            "Comparisons do not establish causal savings unless conditions use "
            "equivalent cases, repetitions, provider configurations, tools, and "
            "reference material.",
        ),
    )


def _validate_unique_repetitions(
    observations: tuple[ExperimentObservation, ...],
) -> None:
    keys = [(item.case_id, item.condition, item.repetition) for item in observations]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate observation for case, condition, and repetition")
    if len({item.dataset_version for item in observations}) > 1:
        raise ValueError("one comparison cannot mix dataset versions")
    by_case: dict[str, set[tuple[str, str]]] = {}
    for item in observations:
        by_case.setdefault(item.case_id, set()).add((item.domain, item.difficulty))
    if any(len(metadata) > 1 for metadata in by_case.values()):
        raise ValueError("case domain and difficulty must match across conditions")


def _summarize(
    observations: tuple[ExperimentObservation, ...],
) -> ConditionSummary:
    adjudicated = tuple(item for item in observations if item.adjudicated)
    human_accepted = tuple(item for item in adjudicated if item.human_accepted)
    quality_accepted = tuple(item for item in human_accepted if _quality_accepted(item))
    token_measured = tuple(item for item in observations if item.total_tokens is not None)
    criteria_total = sum(item.mandatory_criteria_total for item in observations)
    criteria_passed = sum(item.mandatory_criteria_passed for item in observations)
    return ConditionSummary(
        observation_count=len(observations),
        providers=tuple(sorted({item.provider for item in observations})),
        models=tuple(sorted({item.model for item in observations})),
        configuration_ids=tuple(
            sorted({item.configuration_id for item in observations})
        ),
        adjudicated_count=len(adjudicated),
        human_accepted_count=len(human_accepted),
        human_acceptance_rate=(
            len(human_accepted) / len(adjudicated) if adjudicated else None
        ),
        quality_accepted_count=len(quality_accepted),
        quality_success_rate=(
            len(quality_accepted) / len(adjudicated) if adjudicated else None
        ),
        mean_elapsed_seconds=_mean(item.elapsed_seconds for item in observations),
        mean_elapsed_to_acceptable_seconds=_mean(
            item.elapsed_to_acceptable_seconds for item in quality_accepted
        ),
        mean_user_active_seconds=_mean(
            item.user_active_seconds for item in observations
        ),
        user_active_time_coverage=(
            sum(item.user_active_seconds is not None for item in observations)
            / len(observations)
            if observations
            else 0
        ),
        mean_input_tokens=_mean(
            item.input_tokens for item in token_measured
        ),
        mean_output_tokens=_mean(
            item.output_tokens for item in token_measured
        ),
        mean_total_tokens=_mean(item.total_tokens for item in token_measured),
        token_usage_coverage=(
            len(token_measured) / len(observations) if observations else 0
        ),
        mean_clarification_questions=_mean(
            item.clarification_questions for item in observations
        ),
        mean_clarification_turns=_mean(
            item.clarification_turns for item in observations
        ),
        mandatory_criterion_pass_rate=(
            criteria_passed / criteria_total if criteria_total else None
        ),
        verifier_evaluated_count=sum(
            item.verifier_counts is not None for item in observations
        ),
        verifier_true_positives=sum(
            item.verifier_counts.true_positives
            for item in observations
            if item.verifier_counts is not None
        ),
        verifier_false_positives=sum(
            item.verifier_counts.false_positives
            for item in observations
            if item.verifier_counts is not None
        ),
        verifier_false_negatives=sum(
            item.verifier_counts.false_negatives
            for item in observations
            if item.verifier_counts is not None
        ),
        verifier_precision=_ratio(
            sum(
                item.verifier_counts.true_positives
                for item in observations
                if item.verifier_counts is not None
            ),
            sum(
                item.verifier_counts.true_positives
                + item.verifier_counts.false_positives
                for item in observations
                if item.verifier_counts is not None
            ),
            any(item.verifier_counts is not None for item in observations),
        ),
        verifier_recall=_ratio(
            sum(
                item.verifier_counts.true_positives
                for item in observations
                if item.verifier_counts is not None
            ),
            sum(
                item.verifier_counts.true_positives
                + item.verifier_counts.false_negatives
                for item in observations
                if item.verifier_counts is not None
            ),
            any(item.verifier_counts is not None for item in observations),
        ),
    )


def _paired_savings(
    observations: tuple[ExperimentObservation, ...],
    *,
    baseline: ExperimentalCondition,
    treatment: ExperimentalCondition,
) -> PairedSavings:
    by_key = {
        (item.case_id, item.repetition, item.condition): item
        for item in observations
    }
    pairs = tuple(
        (left, right)
        for (case_id, repetition, condition), left in by_key.items()
        if condition == baseline
        and (right := by_key.get((case_id, repetition, treatment))) is not None
    )
    accepted_pairs = tuple(
        (left, right)
        for left, right in pairs
        if left.adjudicated
        and right.adjudicated
        and left.human_accepted
        and right.human_accepted
        and _quality_accepted(left)
        and _quality_accepted(right)
    )
    token_pairs = tuple(
        (left, right)
        for left, right in accepted_pairs
        if left.total_tokens is not None and right.total_tokens is not None
    )
    seconds_saved = tuple(
        left.elapsed_to_acceptable_seconds - right.elapsed_to_acceptable_seconds
        for left, right in accepted_pairs
        if left.elapsed_to_acceptable_seconds is not None
        and right.elapsed_to_acceptable_seconds is not None
    )
    seconds_percent = tuple(
        100
        * (left.elapsed_to_acceptable_seconds - right.elapsed_to_acceptable_seconds)
        / left.elapsed_to_acceptable_seconds
        for left, right in accepted_pairs
        if left.elapsed_to_acceptable_seconds is not None
        and right.elapsed_to_acceptable_seconds is not None
        and left.elapsed_to_acceptable_seconds > 0
    )
    active_seconds_saved = tuple(
        left.user_active_seconds - right.user_active_seconds
        for left, right in accepted_pairs
        if left.user_active_seconds is not None
        and right.user_active_seconds is not None
    )
    tokens_saved = tuple(
        left.total_tokens - right.total_tokens
        for left, right in token_pairs
        if left.total_tokens is not None and right.total_tokens is not None
    )
    tokens_percent = tuple(
        100 * (left.total_tokens - right.total_tokens) / left.total_tokens
        for left, right in token_pairs
        if left.total_tokens is not None
        and right.total_tokens is not None
        and left.total_tokens > 0
    )
    return PairedSavings(
        comparison=f"{baseline.value}_vs_{treatment.value}",
        matched_pairs=len(pairs),
        quality_accepted_pairs=len(accepted_pairs),
        token_measured_quality_accepted_pairs=len(token_pairs),
        mean_seconds_saved=_mean(seconds_saved),
        mean_seconds_saved_percent=_mean(seconds_percent),
        mean_user_active_seconds_saved=_mean(active_seconds_saved),
        mean_tokens_saved=_mean(tokens_saved),
        mean_tokens_saved_percent=_mean(tokens_percent),
    )


def _mean(values) -> float | None:
    measured = tuple(value for value in values if value is not None)
    return sum(measured) / len(measured) if measured else None


def _ratio(numerator: int, denominator: int, was_evaluated: bool) -> float | None:
    if not was_evaluated or denominator == 0:
        return None
    return numerator / denominator


def _quality_accepted(observation: ExperimentObservation) -> bool:
    return (
        observation.mandatory_criteria_total > 0
        and observation.mandatory_criteria_passed
        == observation.mandatory_criteria_total
    )
