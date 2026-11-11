from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from platform_core.assurance.models import AssuranceReport, OutputResponse
from platform_core.intent.models import FrozenModel


class ExecutionRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProviderUsage(FrozenModel):
    elapsed_seconds: float = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    token_usage_complete: bool = False


class ExecutionRunResponse(FrozenModel):
    run_id: UUID
    task_id: UUID
    intent_version: int = Field(ge=1)
    calibration_version: str
    calibrated_prompt: str
    prompt_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: ExecutionRunStatus
    provider: str | None = None
    model: str | None = None
    provider_usage: ProviderUsage | None = None
    output: OutputResponse | None = None
    assurance_report: AssuranceReport | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None