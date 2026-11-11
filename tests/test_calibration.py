from datetime import datetime, timezone
from uuid import uuid4

import pytest

from platform_core.calibration import CalibrationError, PromptCalibrator
from platform_core.intent.extraction import (
    IntentExtractionPayload,
    IntentExtractionService,
)
from platform_core.intent.models import (
    IntentRecord,
    IntentStatus,
    SourceRequest,
    hash_intent_record,
)


class StaticExtractor:
    def __init__(self, payload: IntentExtractionPayload) -> None:
        self.payload = payload

    def extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        return self.payload


def _intent(status: IntentStatus) -> IntentRecord:
    payload = IntentExtractionPayload(
        objective="Prepare a login test plan",
        domain="software",
        task_type="test_plan",
        deliverables=("Markdown test-case table",),
        requirements=(
            {
                "text": "Cover empty credentials",
                "category": "functionality",
                "priority": "mandatory",
                "provenance": "explicit",
            },
            {
                "text": "Use the requested table columns",
                "category": "format",
                "priority": "mandatory",
                "provenance": "explicit",
            },
        ),
        acceptance_criteria=(
            {
                "description": "Include complete, requirement-linked test cases",
                "requirement_indexes": (0, 1),
                "verification_method": (
                    "software_test_case_table:Test ID|Requirement IDs|Scenario|Steps|Expected Result"
                ),
            },
        ),
    )
    intent = IntentExtractionService(StaticExtractor(payload)).extract(
        uuid4(),
        SourceRequest(
            text="Prepare a test plan for empty login credentials.",
            received_at=datetime.now(timezone.utc),
        ),
    )
    candidate = intent.model_copy(
        update={"status": status, "content_hash": "sha256:" + ("0" * 64)}
    )
    return IntentRecord.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "content_hash": hash_intent_record(candidate),
        }
    )


def test_calibration_preserves_approved_requirements_and_traceability() -> None:
    intent = _intent(IntentStatus.APPROVED)

    calibrated = PromptCalibrator().calibrate(intent)

    assert calibrated.task_id == intent.task_id
    assert calibrated.intent_version == intent.version
    assert calibrated.intent_hash == intent.content_hash
    assert calibrated.requirement_ids == ("REQ-001", "REQ-002")
    assert calibrated.mandatory_requirement_ids == ("REQ-001", "REQ-002")
    assert "Original request (verbatim):\nPrepare a test plan" in calibrated.prompt_text
    assert "[REQ-001] (mandatory) Cover empty credentials" in calibrated.prompt_text
    assert "[AC-001] requirements REQ-001, REQ-002" in calibrated.prompt_text
    assert calibrated.prompt_hash.startswith("sha256:")


def test_calibration_rejects_unapproved_intent() -> None:
    with pytest.raises(CalibrationError, match="approved Intent Record"):
        PromptCalibrator().calibrate(_intent(IntentStatus.DRAFT))