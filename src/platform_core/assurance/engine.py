from __future__ import annotations

import json
import re
from datetime import datetime
from uuid import UUID, uuid4

from platform_core.assurance.domain_modules import (
    DEFAULT_DOMAIN_MODULES,
    DomainAssuranceModule,
)
from platform_core.assurance.models import (
    AssuranceReport,
    CriterionResult,
    OverallAssuranceStatus,
    RequirementResult,
    VerificationStatus,
)
from platform_core.intent.models import (
    IntentRecord,
    Requirement,
    RequirementPriority,
)


LIMITATION = (
    "Only explicitly supported deterministic checks are evaluated; "
    "this report does not establish semantic correctness or factual accuracy."
)


class AssuranceEngine:
    def __init__(
        self,
        domain_modules: tuple[DomainAssuranceModule, ...] = DEFAULT_DOMAIN_MODULES,
    ) -> None:
        self._domain_modules = domain_modules

    def evaluate(
        self,
        intent: IntentRecord,
        output: str,
        *,
        output_id: UUID,
        created_at: datetime,
    ) -> AssuranceReport:
        critical_ids = set(intent.risk_profile.critical_requirement_ids)
        criterion_results = tuple(
            self._evaluate_criterion(
                intent,
                criterion.criterion_id,
                criterion.requirement_ids,
                criterion.description,
                criterion.verification_method,
                output,
                criterion.critical
                or bool(critical_ids.intersection(criterion.requirement_ids)),
            )
            for criterion in intent.acceptance_criteria
        )
        requirement_results = tuple(
            self._evaluate_requirement(
                requirement,
                criterion_results,
                requirement.requirement_id in critical_ids,
            )
            for requirement in intent.requirements
        )
        mandatory_gates = tuple(
            result
            for result in requirement_results
            if result.priority == RequirementPriority.MANDATORY
        )

        review_items = tuple(
            f"{result.criterion_id}: {result.explanation}"
            for result in criterion_results
            if result.review_required
        ) + tuple(
            f"{result.requirement_id}: {result.explanation}"
            for result in requirement_results
            if result.review_required and not result.criterion_ids
        )
        status = self._overall_status(requirement_results)
        return AssuranceReport(
            report_id=uuid4(),
            task_id=intent.task_id,
            intent_version=intent.version,
            output_id=output_id,
            overall_status=status,
            mandatory_gates=mandatory_gates,
            requirement_results=requirement_results,
            criterion_results=criterion_results,
            limitations=(LIMITATION,),
            human_review_items=review_items,
            created_at=created_at,
        )

    def _evaluate_criterion(
        self,
        intent: IntentRecord,
        criterion_id: str,
        requirement_ids: tuple[str, ...],
        description: str,
        method: str | None,
        output: str,
        critical: bool,
    ) -> CriterionResult:
        result = next(
            (
                module_result
                for module in self._domain_modules
                if (module_result := module.evaluate(intent, method or "", output))
                is not None
            ),
            None,
        )
        if result is not None:
            status, explanation = result.status, result.explanation
            review_required = result.review_required
        else:
            status, explanation = _run_deterministic_check(method, output)
            review_required = False
        if status is None:
            status = VerificationStatus.UNAVAILABLE
            review_required = True
            explanation = (
                "No supported deterministic check is available for this criterion "
                f"({description}; method: {method or 'not specified'})."
            )
        return CriterionResult(
            criterion_id=criterion_id,
            requirement_ids=requirement_ids,
            status=status,
            method=method,
            explanation=explanation,
            review_required=review_required
            or status
            in {
                VerificationStatus.REQUIRES_HUMAN_REVIEW,
                VerificationStatus.UNAVAILABLE,
            },
            critical=critical,
        )

    @staticmethod
    def _evaluate_requirement(
        requirement: Requirement,
        criterion_results: tuple[CriterionResult, ...],
        critical: bool,
    ) -> RequirementResult:
        related = tuple(
            result
            for result in criterion_results
            if requirement.requirement_id in result.requirement_ids
        )
        if not related:
            status = VerificationStatus.UNAVAILABLE
            explanation = "No acceptance criterion is linked to this requirement."
        elif any(item.status == VerificationStatus.CONTRADICTED for item in related):
            status = VerificationStatus.CONTRADICTED
            explanation = "At least one linked acceptance criterion was contradicted."
        elif any(
            item.status == VerificationStatus.REQUIRES_HUMAN_REVIEW
            for item in related
        ):
            status = VerificationStatus.REQUIRES_HUMAN_REVIEW
            explanation = "At least one linked criterion requires human review."
        elif any(item.status == VerificationStatus.UNAVAILABLE for item in related):
            status = VerificationStatus.UNAVAILABLE
            explanation = "At least one linked criterion is unavailable."
        elif any(
            item.status == VerificationStatus.PARTIALLY_SUPPORTED for item in related
        ):
            status = VerificationStatus.PARTIALLY_SUPPORTED
            explanation = "At least one linked criterion is only partially supported."
        elif all(item.status == VerificationStatus.SUPPORTED for item in related):
            status = VerificationStatus.SUPPORTED
            explanation = "All linked deterministic acceptance checks passed."
        else:
            status = VerificationStatus.UNVERIFIED
            explanation = "The linked acceptance criteria were not fully verified."
        return RequirementResult(
            requirement_id=requirement.requirement_id,
            priority=requirement.priority,
            criterion_ids=tuple(item.criterion_id for item in related),
            status=status,
            explanation=explanation,
            review_required=any(item.review_required for item in related)
            or status
            in {
                VerificationStatus.REQUIRES_HUMAN_REVIEW,
                VerificationStatus.UNAVAILABLE,
            },
            critical=critical,
        )

    @staticmethod
    def _overall_status(
        requirement_results: tuple[RequirementResult, ...],
    ) -> OverallAssuranceStatus:
        if not requirement_results:
            return OverallAssuranceStatus.UNVERIFIED
        if all(
            result.status == VerificationStatus.SUPPORTED
            for result in requirement_results
        ):
            return OverallAssuranceStatus.ALL_CHECKS_PASSED
        if all(
            result.status
            in {
                VerificationStatus.REQUIRES_HUMAN_REVIEW,
                VerificationStatus.UNAVAILABLE,
            }
            for result in requirement_results
        ):
            return OverallAssuranceStatus.REQUIRES_HUMAN_REVIEW
        return OverallAssuranceStatus.PARTIALLY_VERIFIED


def _run_deterministic_check(
    method: str | None, output: str
) -> tuple[VerificationStatus | None, str]:
    if method is None:
        return None, ""
    if method.startswith("contains_text:"):
        expected = " ".join(method.removeprefix("contains_text:").casefold().split())
        if not expected:
            return None, ""
        normalized_output = " ".join(output.casefold().split())
        found = expected in normalized_output
        return (
            VerificationStatus.SUPPORTED if found else VerificationStatus.CONTRADICTED,
            "The exact normalized text is present in the output."
            if found
            else "The exact normalized text is absent from the output.",
        )
    if method.startswith("section_present:"):
        expected = " ".join(method.removeprefix("section_present:").casefold().split())
        if not expected:
            return None, ""
        headings = {
            " ".join(re.sub(r"^#{1,6}\s*", "", line).strip().casefold().split())
            for line in output.splitlines()
            if re.match(r"^\s*#{1,6}\s+\S", line)
        }
        found = expected in headings
        return (
            VerificationStatus.SUPPORTED if found else VerificationStatus.CONTRADICTED,
            "The requested Markdown heading is present."
            if found
            else "The requested Markdown heading is absent.",
        )
    if method == "valid_json":
        try:
            json.loads(output)
        except json.JSONDecodeError:
            return VerificationStatus.CONTRADICTED, "The output is not valid JSON."
        return VerificationStatus.SUPPORTED, "The output is valid JSON."
    return None, ""
