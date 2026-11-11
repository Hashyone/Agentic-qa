from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from platform_core.intent.models import (
    AcceptanceCriterion,
    IntentRecord,
    Requirement,
    RequirementPriority,
    RequirementProvenance,
    RiskLevel,
    RiskProfile,
    SourceRequest,
)


def test_initial_draft_preserves_source_and_hashes_record() -> None:
    original = "  Build a small tool.\n"
    source = SourceRequest(text=original, received_at=datetime.now(timezone.utc))

    record = IntentRecord.create_initial_draft(uuid4(), source)

    assert record.source_request.text == original
    assert record.task.objective == original
    assert record.version == 1
    assert record.content_hash.startswith("sha256:")
    assert record.requirements == ()

    with pytest.raises(ValidationError, match="content_hash does not match"):
        IntentRecord.model_validate(
            {**record.model_dump(mode="json"), "content_hash": "sha256:" + "0" * 64}
        )


def test_source_request_rejects_blank_text_without_normalizing_valid_text() -> None:
    with pytest.raises(ValidationError):
        SourceRequest(text=" \n ", received_at=datetime.now(timezone.utc))

    source = SourceRequest(text="  keep whitespace  ", received_at=datetime.now(timezone.utc))
    assert source.text == "  keep whitespace  "


@pytest.mark.parametrize(
    "provenance",
    [RequirementProvenance.INFERRED, RequirementProvenance.ASSUMED],
)
def test_inferred_and_assumed_require_confidence(
    provenance: RequirementProvenance,
) -> None:
    with pytest.raises(ValidationError, match="need confidence"):
        Requirement(
            requirement_id="REQ-1",
            text="Use a concise format",
            category="style",
            priority=RequirementPriority.PREFERRED,
            provenance=provenance,
        )


def test_requirement_ids_and_criterion_references_are_validated() -> None:
    requirement = Requirement(
        requirement_id="REQ-1",
        text="Include tests",
        category="functionality",
        priority=RequirementPriority.MANDATORY,
        provenance=RequirementProvenance.EXPLICIT,
    )
    source = SourceRequest(text="Build a tool", received_at=datetime.now(timezone.utc))
    record_data = {
        "intent_id": uuid4(),
        "task_id": uuid4(),
        "version": 1,
        "source_request": source,
        "task": {"objective": "Build a tool", "domain": "software", "task_type": "build"},
        "content_hash": "sha256:" + "0" * 64,
    }

    with pytest.raises(ValidationError, match="unknown requirement"):
        IntentRecord(
            **record_data,
            requirements=(requirement,),
            acceptance_criteria=(
                AcceptanceCriterion(
                    criterion_id="AC-1",
                    requirement_ids=("REQ-2",),
                    description="Tests exist",
                ),
            ),
        )

    with pytest.raises(ValidationError, match="unique"):
        IntentRecord(
            **record_data,
            requirements=(requirement, requirement),
        )


def test_critical_requirements_must_be_mandatory() -> None:
    requirement = Requirement(
        requirement_id="REQ-1",
        text="Use a concise format",
        category="style",
        priority=RequirementPriority.PREFERRED,
        provenance=RequirementProvenance.EXPLICIT,
    )
    source = SourceRequest(text="Build a tool", received_at=datetime.now(timezone.utc))

    with pytest.raises(ValidationError, match="must exist and be mandatory"):
        IntentRecord(
            intent_id=uuid4(),
            task_id=uuid4(),
            version=1,
            source_request=source,
            task={
                "objective": "Build a tool",
                "domain": "software",
                "task_type": "build",
            },
            requirements=(requirement,),
            risk_profile=RiskProfile(
                level=RiskLevel.CRITICAL, critical_requirement_ids=("REQ-1",)
            ),
            content_hash="sha256:" + "0" * 64,
        )

    assert requirement.requirement_id == "REQ-1"
