from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequirementPriority(StrEnum):
    MANDATORY = "mandatory"
    PREFERRED = "preferred"
    OPTIONAL = "optional"


class RequirementProvenance(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    ASSUMED = "assumed"
    CLARIFIED = "clarified"


class IntentStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_CLARIFICATION = "needs_clarification"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNCLASSIFIED = "unclassified"


class SourceRequest(FrozenModel):
    text: str
    attachments: tuple[str, ...] = ()
    received_at: datetime

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source request must not be blank")
        return value

    @field_validator("received_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        return value


class TaskDescription(FrozenModel):
    objective: str
    domain: str
    task_type: str
    deliverables: tuple[str, ...] = ()

    @field_validator("objective", "domain", "task_type")
    @classmethod
    def values_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task fields must not be blank")
        return value


class IntentContext(FrozenModel):
    description: str | None = None
    audience: str | None = None
    jurisdiction: str | None = None
    geographic_scope: tuple[str, ...] = ()
    time_period: str | None = None
    reference_materials: tuple[str, ...] = ()


class Requirement(FrozenModel):
    requirement_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    category: str = Field(min_length=1)
    priority: RequirementPriority
    provenance: RequirementProvenance
    source_location: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("text", "category")
    @classmethod
    def values_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def inferred_and_assumed_require_confidence(self) -> Self:
        if self.provenance in {
            RequirementProvenance.INFERRED,
            RequirementProvenance.ASSUMED,
        } and self.confidence is None:
            raise ValueError("inferred and assumed requirements need confidence")
        return self


class AcceptanceCriterion(FrozenModel):
    criterion_id: str = Field(min_length=1)
    requirement_ids: tuple[str, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    verification_method: str | None = None
    critical: bool = False


class RiskProfile(FrozenModel):
    level: RiskLevel = RiskLevel.UNCLASSIFIED
    critical_requirement_ids: tuple[str, ...] = ()


class IntentRecord(FrozenModel):
    intent_id: UUID
    task_id: UUID
    version: int = Field(ge=1)
    source_request: SourceRequest
    task: TaskDescription
    context: IntentContext = Field(default_factory=IntentContext)
    requirements: tuple[Requirement, ...] = ()
    quality_criteria: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    clarification_ids: tuple[UUID, ...] = ()
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = ()
    risk_profile: RiskProfile = Field(default_factory=RiskProfile)
    status: IntentStatus = IntentStatus.DRAFT
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_requirement_references(self) -> Self:
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirement IDs must be unique within an Intent Record")

        known_ids = set(requirement_ids)
        criterion_ids = [item.criterion_id for item in self.acceptance_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("acceptance criterion IDs must be unique")
        for criterion in self.acceptance_criteria:
            if not set(criterion.requirement_ids) <= known_ids:
                raise ValueError(
                    f"{criterion.criterion_id} references an unknown requirement"
                )

        mandatory_ids = {
            item.requirement_id
            for item in self.requirements
            if item.priority == RequirementPriority.MANDATORY
        }
        if not set(self.risk_profile.critical_requirement_ids) <= mandatory_ids:
            raise ValueError("critical requirements must exist and be mandatory")
        return self

    @model_validator(mode="after")
    def validate_content_hash(self) -> Self:
        if self.content_hash != hash_intent_record(self):
            raise ValueError("content_hash does not match the Intent Record")
        return self

    @classmethod
    def create_initial_draft(
        cls, task_id: UUID, source_request: SourceRequest
    ) -> Self:
        record_data = {
            "intent_id": uuid4(),
            "task_id": task_id,
            "version": 1,
            "source_request": source_request,
            "task": TaskDescription(
                objective=source_request.text,
                domain="unclassified",
                task_type="unclassified",
            ),
        }
        candidate = cls.model_construct(
            **record_data,
            content_hash="sha256:" + ("0" * 64),
        )
        return cls.model_validate(
            {
                **record_data,
                "content_hash": hash_intent_record(candidate),
            }
        )


def hash_intent_record(record: IntentRecord) -> str:
    canonical = json.dumps(
        record.model_dump(mode="json", exclude={"content_hash"}),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_source_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
