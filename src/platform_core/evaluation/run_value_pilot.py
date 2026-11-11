from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from pydantic import ValidationError

from platform_core.api.app import create_app
from platform_core.evaluation.api_cases import (
    APITestCaseSuite,
    execute_api_test_cases,
    parse_api_test_cases,
)
from platform_core.intent.extraction import (
    IntentExtractionError,
    IntentExtractionPayload,
)
from platform_core.intent.models import SourceRequest
from platform_core.providers.deepseek import DeepSeekIntentExtractor
from platform_core.providers.generation import DeepSeekTextGenerator


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROTOCOL = ROOT / "evaluation_data/pilots/api_task_creation_v0.1.json"
DEFAULT_OUTPUT = ROOT / "data/value_pilot_api_task_creation.json"


class TaskOnlyExtractor:
    def extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        return IntentExtractionPayload(
            objective="Accept a task",
            domain="software",
            task_type="task_creation",
        )


def run_value_pilot(protocol_path: Path, output_path: Path, *, seed: int) -> dict:
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for the value pilot")

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    conditions = ["baseline_a", "baseline_b", "treatment_c"]
    random.Random(seed).shuffle(conditions)
    started_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, dict[str, Any]] = {}
    for condition in conditions:
        if condition == "treatment_c":
            results[condition] = _run_platform_condition(
                protocol,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
        else:
            results[condition] = _run_direct_condition(
                protocol,
                condition=condition,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )

    report = {
        "pilot_id": protocol["pilot_id"],
        "dataset_version": protocol["dataset_version"],
        "oracle_version": protocol["oracle_version"],
        "target_id": protocol["target_id"],
        "provider": "deepseek",
        "model": model,
        "condition_order": conditions,
        "order_seed": seed,
        "started_at": started_at,
        "conditions": results,
        "exploratory_deltas": _exploratory_deltas(results),
        "limitations": [
            "Single-task feasibility run; not an estimate of population-level savings.",
            "Automated local API oracle used; human quality adjudication is still required.",
            "No autonomous agent loop was run, so agent iterations and loop reduction are not measured.",
            "User-active time and willingness to pay are not measured.",
            "Token totals are valid only when usage is complete for every provider call.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _run_direct_condition(
    protocol: dict,
    *,
    condition: str,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    started = perf_counter()
    provider_calls: list[dict[str, Any]] = []
    output_text = ""
    assurance_status = None
    quality_result = None
    error = None
    generator = DeepSeekTextGenerator(
        api_key=api_key, base_url=base_url, model=model
    )
    try:
        prompt = protocol["conditions"][f"{condition}_prompt"]
        generated = generator.generate(prompt)
        output_text = generated.text
        provider_calls.append(_usage_record("generation", generated))
        suite = parse_api_test_cases(output_text)
        link_check = _check_suite_contract(
            suite,
            protocol["expected_behaviors"],
            known_requirement_ids={
                behavior["oracle_requirement_id"]
                for behavior in protocol["expected_behaviors"]
            },
            require_oracle_ids=True,
        )
        execution = _execute_in_isolated_api(suite)
        quality_result = {
            "requirement_links_valid": link_check["valid"],
            "requirement_link_errors": link_check["errors"],
            **execution,
            "all_passed": link_check["valid"] and execution["all_passed"],
        }
    except (ValidationError, IntentExtractionError, ValueError) as caught:
        error = f"{type(caught).__name__}: {caught}"
    except Exception as caught:
        error = f"{type(caught).__name__}: {caught}"
    return {
        "elapsed_seconds": perf_counter() - started,
        "provider_calls": provider_calls,
        **_token_totals(provider_calls),
        "quality": quality_result,
        "generation_assurance_status": assurance_status,
        "output": output_text,
        "error": error,
        "agent_iterations": None,
        "human_accepted": None,
        "adjudicated": False,
    }


def _run_platform_condition(
    protocol: dict,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    started = perf_counter()
    extractor = DeepSeekIntentExtractor(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    generator = DeepSeekTextGenerator(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=extractor,
        text_generator=generator,
    )
    provider_calls: list[dict[str, Any]] = []
    output_text = ""
    assurance_status = None
    quality_result = None
    error = None
    with TestClient(app) as client:
        try:
            created = client.post(
                "/v1/tasks",
                json={"input": {"text": protocol["conditions"]["platform_request"]}},
            )
            created.raise_for_status()
            task_id = created.json()["task_id"]
            intent = client.get(f"/v1/tasks/{task_id}/intent").json()
            for clarification in client.get(
                f"/v1/tasks/{task_id}/clarifications"
            ).json():
                answer = client.post(
                    f"/v1/tasks/{task_id}/clarifications",
                    json={
                        "clarification_id": clarification["clarification_id"],
                        "answer": {"value": "not specified"},
                    },
                )
                answer.raise_for_status()
                intent = client.get(f"/v1/tasks/{task_id}/intent").json()
            approved = client.post(f"/v1/tasks/{task_id}/intent/approve")
            approved.raise_for_status()
            calibration = client.post(f"/v1/tasks/{task_id}/calibration")
            calibration.raise_for_status()
            run = client.post(f"/v1/tasks/{task_id}/runs")
            run.raise_for_status()
            run_data = run.json()
            output_text = run_data["output"]["text"]
            assurance_status = run_data["assurance_report"]["overall_status"]
            provider_calls.append(
                {
                    "purpose": "generation",
                    "provider": run_data["provider"],
                    "model": run_data["model"],
                    **(run_data["provider_usage"] or {}),
                }
            )
            suite = parse_api_test_cases(output_text)
            known_requirement_ids = {
                requirement["requirement_id"] for requirement in intent["requirements"]
            }
            link_check = _check_suite_contract(
                suite,
                protocol["expected_behaviors"],
                known_requirement_ids=known_requirement_ids,
                require_oracle_ids=False,
            )
            execution = _execute_in_isolated_api(suite)
            quality_result = {
                "requirement_links_valid": link_check["valid"],
                "requirement_link_errors": link_check["errors"],
                **execution,
                "all_passed": link_check["valid"] and execution["all_passed"],
            }
        except (ValidationError, IntentExtractionError, ValueError) as caught:
            error = f"{type(caught).__name__}: {caught}"
        except Exception as caught:
            error = f"{type(caught).__name__}: {caught}"

    provider_calls.insert(0, _usage_record("intent_extraction", extractor.last_usage))
    return {
        "elapsed_seconds": perf_counter() - started,
        "provider_calls": provider_calls,
        **_token_totals(provider_calls),
        "quality": quality_result,
        "generation_assurance_status": assurance_status,
        "output": output_text,
        "error": error,
        "agent_iterations": None,
        "human_accepted": None,
        "adjudicated": False,
    }


def _execute_in_isolated_api(suite: APITestCaseSuite) -> dict[str, Any]:
    app = create_app(
        "sqlite:///:memory:",
        initialize_schema=True,
        intent_extractor=TaskOnlyExtractor(),
    )
    with TestClient(app) as client:
        result = execute_api_test_cases(suite, client)
    return {
        "case_count": len(result.case_results),
        "passed_cases": result.passed_cases,
        "failed_cases": result.failed_cases,
        "all_passed": result.all_passed,
        "case_results": [item.model_dump(mode="json") for item in result.case_results],
    }


def _check_suite_contract(
    suite: APITestCaseSuite,
    expected_behaviors: list[dict[str, Any]],
    *,
    known_requirement_ids: set[str],
    require_oracle_ids: bool,
) -> dict[str, Any]:
    errors = []
    expected_by_input = {
        behavior["input_text"]: behavior for behavior in expected_behaviors
    }
    actual_inputs = [case.input_text for case in suite.cases]
    if len(actual_inputs) != len(expected_behaviors) or set(actual_inputs) != set(
        expected_by_input
    ):
        errors.append("generated cases do not match the frozen input cases")
    for case in suite.cases:
        behavior = expected_by_input.get(case.input_text)
        if behavior is None:
            errors.append(f"{case.case_id} uses an input outside the frozen oracle")
            continue
        unknown = set(case.requirement_ids) - known_requirement_ids
        if unknown:
            errors.append(
                f"{case.case_id} references unknown requirements: "
                + ", ".join(sorted(unknown))
            )
        if require_oracle_ids and set(case.requirement_ids) != {
            behavior["oracle_requirement_id"]
        }:
            errors.append(f"{case.case_id} does not link to its oracle requirement")
        for field in (
            "expected_status_code",
            "expected_task_status",
            "expected_source_request",
            "expected_error_detail",
        ):
            if getattr(case, field) != behavior.get(field):
                errors.append(
                    f"{case.case_id} has incorrect {field}: "
                    f"expected {behavior.get(field)!r}"
                )
    return {"valid": not errors, "errors": errors}


def _usage_record(purpose: str, usage: Any) -> dict[str, Any]:
    return {
        "purpose": purpose,
        "elapsed_seconds": usage.elapsed_seconds,
        "provider_requests": getattr(usage, "provider_requests", 1),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "token_usage_complete": usage.token_usage_complete,
    }


def _token_totals(calls: list[dict[str, Any]]) -> dict[str, Any]:
    complete = bool(calls) and all(call["token_usage_complete"] for call in calls)
    return {
        "provider_request_count": sum(
            call.get("provider_requests", 1) for call in calls
        ),
        "all_call_usage_complete": complete,
        "input_tokens": (
            sum(call["input_tokens"] or 0 for call in calls) if complete else None
        ),
        "output_tokens": (
            sum(call["output_tokens"] or 0 for call in calls) if complete else None
        ),
        "total_tokens": (
            sum(call["total_tokens"] or 0 for call in calls) if complete else None
        ),
    }


def _exploratory_deltas(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    treatment = results["treatment_c"]
    comparisons: dict[str, Any] = {}
    for baseline_name in ("baseline_a", "baseline_b"):
        baseline = results[baseline_name]
        comparable_quality = all(
            condition.get("error") is None
            and condition.get("quality") is not None
            and condition["quality"]["all_passed"]
            for condition in (baseline, treatment)
        )
        time_delta = (
            baseline["elapsed_seconds"] - treatment["elapsed_seconds"]
            if comparable_quality
            else None
        )
        token_comparable = (
            comparable_quality
            and baseline["all_call_usage_complete"]
            and treatment["all_call_usage_complete"]
        )
        token_delta = (
            baseline["total_tokens"] - treatment["total_tokens"]
            if token_comparable
            else None
        )
        comparisons[baseline_name] = {
            "both_passed_independent_oracle": comparable_quality,
            "time_delta_seconds_baseline_minus_platform": time_delta,
            "time_delta_percent_of_baseline": (
                100 * time_delta / baseline["elapsed_seconds"]
                if time_delta is not None and baseline["elapsed_seconds"] > 0
                else None
            ),
            "token_delta_baseline_minus_platform": token_delta,
            "token_delta_percent_of_baseline": (
                100 * token_delta / baseline["total_tokens"]
                if token_delta is not None and baseline["total_tokens"] > 0
                else None
            ),
            "sample_count": 1,
            "requires_human_adjudication": True,
        }
    return comparisons


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded A/B/C value feasibility pilot.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=17)
    arguments = parser.parse_args()
    report = run_value_pilot(arguments.protocol, arguments.output, seed=arguments.seed)
    print(json.dumps(report, indent=2))
    print(f"\nPilot report saved to {arguments.output}")


if __name__ == "__main__":
    main()