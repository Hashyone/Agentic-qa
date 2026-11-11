import pytest
from pydantic import ValidationError

from platform_core.evaluation.experiment import (
    ExperimentalCondition,
    ExperimentObservation,
    VerifierConfusionCounts,
    compare_experiment_conditions,
)


def _observation(
    condition: ExperimentalCondition,
    *,
    accepted: bool,
    seconds: float,
    input_tokens: int | None,
    output_tokens: int | None,
    repetition: int = 1,
) -> ExperimentObservation:
    return ExperimentObservation(
        dataset_version="0.1.0",
        case_id="UAT-0001",
        domain="academic",
        difficulty="moderate",
        condition=condition,
        repetition=repetition,
        provider="test-provider",
        model="test-model",
        configuration_id="test-config",
        elapsed_seconds=seconds,
        elapsed_to_acceptable_seconds=seconds if accepted else None,
        user_active_seconds=seconds / 10,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        token_usage_complete=(
            input_tokens is not None and output_tokens is not None
        ),
        clarification_questions=1 if condition == ExperimentalCondition.FULL_PLATFORM else 0,
        clarification_turns=1 if condition == ExperimentalCondition.FULL_PLATFORM else 0,
        human_accepted=accepted,
        mandatory_criteria_total=2,
        mandatory_criteria_passed=2 if accepted else 1,
        adjudicated=True,
    )


def test_comparison_reports_paired_time_and_token_savings_only_for_accepted_runs():
    observations = (
        _observation(
            ExperimentalCondition.CONVENTIONAL_PROMPTING,
            accepted=True,
            seconds=100,
            input_tokens=800,
            output_tokens=200,
        ),
        _observation(
            ExperimentalCondition.PROMPT_OPTIMISATION,
            accepted=True,
            seconds=90,
            input_tokens=700,
            output_tokens=180,
        ),
        _observation(
            ExperimentalCondition.FULL_PLATFORM,
            accepted=True,
            seconds=70,
            input_tokens=600,
            output_tokens=150,
        ),
    )

    report = compare_experiment_conditions(observations)

    baseline_pair = report.paired_savings[0]
    optimizer_pair = report.paired_savings[1]
    assert baseline_pair.matched_pairs == 1
    assert baseline_pair.quality_accepted_pairs == 1
    assert baseline_pair.mean_seconds_saved == 30
    assert baseline_pair.mean_seconds_saved_percent == 30
    assert baseline_pair.mean_tokens_saved == 250
    assert baseline_pair.mean_tokens_saved_percent == 25
    assert baseline_pair.mean_user_active_seconds_saved == 3
    assert optimizer_pair.mean_seconds_saved == 20
    assert optimizer_pair.mean_tokens_saved == 130
    assert (
        report.condition_summaries[
            ExperimentalCondition.FULL_PLATFORM
        ].quality_success_rate
        == 1
    )
    assert report.by_domain["academic"][
        ExperimentalCondition.FULL_PLATFORM
    ].quality_success_rate == 1
    assert report.by_difficulty["moderate"][
        ExperimentalCondition.FULL_PLATFORM
    ].observation_count == 1


def test_faster_but_unaccepted_treatment_does_not_claim_savings():
    observations = (
        _observation(
            ExperimentalCondition.CONVENTIONAL_PROMPTING,
            accepted=True,
            seconds=100,
            input_tokens=800,
            output_tokens=200,
        ),
        _observation(
            ExperimentalCondition.FULL_PLATFORM,
            accepted=False,
            seconds=20,
            input_tokens=400,
            output_tokens=50,
        ),
    )

    report = compare_experiment_conditions(observations)
    comparison = report.paired_savings[0]

    assert comparison.matched_pairs == 1
    assert comparison.quality_accepted_pairs == 0
    assert comparison.mean_seconds_saved is None
    assert comparison.mean_tokens_saved is None
    assert (
        report.condition_summaries[
            ExperimentalCondition.FULL_PLATFORM
        ].human_acceptance_rate
        == 0
    )


def test_missing_token_counts_are_not_estimated_or_used_as_savings():
    observations = (
        _observation(
            ExperimentalCondition.CONVENTIONAL_PROMPTING,
            accepted=True,
            seconds=100,
            input_tokens=None,
            output_tokens=200,
        ),
        _observation(
            ExperimentalCondition.FULL_PLATFORM,
            accepted=True,
            seconds=80,
            input_tokens=600,
            output_tokens=150,
        ),
    )

    report = compare_experiment_conditions(observations)
    comparison = report.paired_savings[0]

    assert comparison.mean_seconds_saved == 20
    assert comparison.token_measured_quality_accepted_pairs == 0
    assert comparison.mean_tokens_saved is None
    assert (
        report.condition_summaries[
            ExperimentalCondition.CONVENTIONAL_PROMPTING
        ].token_usage_coverage
        == 0
    )


def test_token_counts_are_not_used_when_the_all_call_ledger_is_incomplete():
    row = _observation(
        ExperimentalCondition.FULL_PLATFORM,
        accepted=True,
        seconds=10,
        input_tokens=100,
        output_tokens=50,
    ).model_copy(update={"token_usage_complete": False})

    report = compare_experiment_conditions((row,))
    summary = report.condition_summaries[ExperimentalCondition.FULL_PLATFORM]

    assert row.total_tokens is None
    assert summary.token_usage_coverage == 0
    assert summary.mean_total_tokens is None


def test_human_acceptance_with_mandatory_criterion_failure_is_not_quality_success():
    row = _observation(
        ExperimentalCondition.FULL_PLATFORM,
        accepted=True,
        seconds=10,
        input_tokens=100,
        output_tokens=50,
    ).model_copy(update={"mandatory_criteria_passed": 1})

    report = compare_experiment_conditions((row,))
    summary = report.condition_summaries[ExperimentalCondition.FULL_PLATFORM]

    assert summary.human_acceptance_rate == 1
    assert summary.quality_success_rate == 0
    assert summary.mean_elapsed_to_acceptable_seconds is None


def test_observation_rejects_unadjudicated_acceptance_claim_and_duplicate_runs():
    with pytest.raises(ValidationError, match="exactly when adjudicated"):
        ExperimentObservation(
            case_id="UAT-0001",
            dataset_version="0.1.0",
            domain="academic",
            difficulty="moderate",
            condition=ExperimentalCondition.FULL_PLATFORM,
            repetition=1,
            elapsed_seconds=1,
            provider="test-provider",
            model="test-model",
            configuration_id="test-config",
            clarification_questions=0,
            clarification_turns=0,
            human_accepted=True,
            mandatory_criteria_total=0,
            mandatory_criteria_passed=0,
            adjudicated=False,
        )

    row = _observation(
        ExperimentalCondition.FULL_PLATFORM,
        accepted=True,
        seconds=1,
        input_tokens=1,
        output_tokens=1,
    )
    with pytest.raises(ValueError, match="duplicate observation"):
        compare_experiment_conditions((row, row))


def test_observation_rejects_acceptance_time_after_total_elapsed_time():
    with pytest.raises(ValidationError, match="cannot exceed total elapsed time"):
        ExperimentObservation(
            dataset_version="0.1.0",
            case_id="UAT-0001",
            domain="academic",
            difficulty="moderate",
            condition=ExperimentalCondition.FULL_PLATFORM,
            repetition=1,
            provider="test-provider",
            model="test-model",
            configuration_id="test-config",
            elapsed_seconds=5,
            elapsed_to_acceptable_seconds=6,
            clarification_questions=0,
            clarification_turns=0,
            human_accepted=True,
            mandatory_criteria_total=1,
            mandatory_criteria_passed=1,
            adjudicated=True,
        )


def test_comparison_reports_verifier_precision_and_recall_from_adjudicated_counts():
    row = _observation(
        ExperimentalCondition.FULL_PLATFORM,
        accepted=True,
        seconds=10,
        input_tokens=100,
        output_tokens=50,
    ).model_copy(
        update={
            "verifier_counts": VerifierConfusionCounts(
                true_positives=7,
                false_positives=2,
                false_negatives=1,
            )
        }
    )

    report = compare_experiment_conditions((row,))
    summary = report.condition_summaries[ExperimentalCondition.FULL_PLATFORM]

    assert summary.verifier_precision == pytest.approx(7 / 9)
    assert summary.verifier_recall == pytest.approx(7 / 8)
    assert summary.verifier_false_positives == 2
    assert summary.verifier_false_negatives == 1
