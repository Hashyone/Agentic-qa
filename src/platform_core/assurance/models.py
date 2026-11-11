from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from platform_core.intent.models import FrozenModel, RequirementPriority


class VerificationStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class OverallAssuranceStatus(StrEnum):
    ALL_CHECKS_PASSED = "all_checks_passed"
    PARTIALLY_VERIFIED = "partially_verified"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    UNVERIFIED = "unverified"


class ClaimSummary(FrozenModel):
    supported: int = 0
    contradicted: int = 0
    partially_supported: int = 0
    unverified: int = 0


class CriterionResult(FrozenModel):
    criterion_id: str
    requirement_ids: tuple[str, ...]
    status: VerificationStatus
    method: str | None
    explanation: str
    evidence_ids: tuple[UUID, ...] = ()
    review_required: bool = False
    critical: bool = False


class RequirementResult(FrozenModel):
    requirement_id: str
    priority: RequirementPriority
    criterion_ids: tuple[str, ...]
    status: VerificationStatus
    explanation: str
    review_required: bool = False
    critical: bool = False


class AssuranceReport(FrozenModel):
    report_id: UUID
    task_id: UUID
    intent_version: int = Field(ge=1)
    output_id: UUID
    overall_status: OverallAssuranceStatus
    quality_assessment: str | None = None
    mandatory_gates: tuple[RequirementResult, ...] = ()
    requirement_results: tuple[RequirementResult, ...] = ()
    criterion_results: tuple[CriterionResult, ...] = ()
    claim_summary: ClaimSummary = Field(default_factory=ClaimSummary)
    limitations: tuple[str, ...] = ()
    human_review_items: tuple[str, ...] = ()
    created_at: datetime


class CreateAssuranceRequest(FrozenModel):
    output: str = Field(min_length=1)

    @field_validator("output")
    @classmethod
    def output_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("output must not be blank")
        return value


class OutputResponse(FrozenModel):
    output_id: UUID
    task_id: UUID
    intent_version: int
    text: str
    content_hash: str
    created_at: datetime
