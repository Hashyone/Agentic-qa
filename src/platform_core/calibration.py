from __future__ import annotations

import hashlib
from uuid import UUID

from pydantic import Field

from platform_core.intent.models import (
    FrozenModel,
    IntentRecord,
    IntentStatus,
    RequirementPriority,
)


CALIBRATION_VERSION = "0.1.0"


class CalibrationError(ValueError):
    pass


class CalibratedPrompt(FrozenModel):
    task_id: UUID
    intent_version: int = Field(ge=1)
    intent_hash: str
    calibration_version: str
    prompt_text: str = Field(min_length=1)
    prompt_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requirement_ids: tuple[str, ...]
    mandatory_requirement_ids: tuple[str, ...]


class PromptCalibrator:
    def calibrate(self, intent: IntentRecord) -> CalibratedPrompt:
        if intent.status != IntentStatus.APPROVED:
            raise CalibrationError("Only an approved Intent Record can be calibrated")

        requirements = tuple(
            f"- [{requirement.requirement_id}] ({requirement.priority.value}) "
            f"{requirement.text}"
            for requirement in intent.requirements
        )
        criteria = tuple(
            f"- [{criterion.criterion_id}] requirements "
            f"{', '.join(criterion.requirement_ids)}: {criterion.description}"
            + (
                f" (verification method: {criterion.verification_method})"
                if criterion.verification_method
                else ""
            )
            for criterion in intent.acceptance_criteria
        )
        deliverables = "\n".join(f"- {item}" for item in intent.task.deliverables)
        exclusions = "\n".join(f"- {item}" for item in intent.exclusions)
        evidence = "\n".join(f"- {item}" for item in intent.evidence_requirements)
        quality = "\n".join(f"- {item}" for item in intent.quality_criteria)
        assumptions = "\n".join(f"- {item}" for item in intent.assumptions)
        context_items = tuple(
            (label, value)
            for label, value in (
                ("Description", intent.context.description),
                ("Audience", intent.context.audience),
                ("Jurisdiction", intent.context.jurisdiction),
                ("Geographic scope", ", ".join(intent.context.geographic_scope)),
                ("Time period", intent.context.time_period),
                ("Reference materials", ", ".join(intent.context.reference_materials)),
                ("Attachments", ", ".join(intent.source_request.attachments)),
            )
            if value
        )
        prompt_text = "\n".join(
            (
                "Complete the user's task using the approved requirements below.",
                "Preserve the original request and do not omit mandatory requirements.",
                "Do not claim that checks, tests, or external research were performed unless they were.",
                "",
                "Original request (verbatim):",
                intent.source_request.text,
                "",
                f"Objective: {intent.task.objective}",
                f"Domain: {intent.task.domain}",
                f"Task type: {intent.task.task_type}",
                "",
                "Recorded context:",
                *(
                    tuple(f"- {label}: {value}" for label, value in context_items)
                    or ("- None recorded.",)
                ),
                "",
                "Deliverables:",
                deliverables or "- No explicit deliverable was recorded.",
                "",
                "Requirements (IDs are for traceability; satisfy every mandatory item):",
                *(requirements or ("- No requirements were recorded.",)),
                "",
                "Acceptance criteria:",
                *(criteria or ("- No acceptance criteria were recorded.",)),
                "",
                "Quality criteria:",
                quality or "- None recorded.",
                "",
                "Evidence requirements:",
                evidence or "- None recorded.",
                "",
                "Approved assumptions:",
                assumptions or "- None recorded.",
                "",
                "Exclusions:",
                exclusions or "- None recorded.",
                "",
                "Produce the requested deliverable. Do not reproduce this calibration text.",
            )
        )
        prompt_hash = "sha256:" + hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        requirement_ids = tuple(item.requirement_id for item in intent.requirements)
        mandatory_ids = tuple(
            item.requirement_id
            for item in intent.requirements
            if item.priority == RequirementPriority.MANDATORY
        )
        return CalibratedPrompt(
            task_id=intent.task_id,
            intent_version=intent.version,
            intent_hash=intent.content_hash,
            calibration_version=CALIBRATION_VERSION,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            requirement_ids=requirement_ids,
            mandatory_requirement_ids=mandatory_ids,
        )