from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

from platform_core.assurance.domain_modules import (
    DEFAULT_DOMAIN_MODULES,
    DomainModuleDescriptor,
)
from platform_core.assurance.engine import AssuranceEngine
from platform_core.assurance.models import (
    AssuranceReport,
    CreateAssuranceRequest,
    OutputResponse,
)
from platform_core.calibration import (
    CalibratedPrompt,
    CalibrationError,
    PromptCalibrator,
)
from platform_core.execution import (
    ExecutionRunResponse,
    ExecutionRunStatus,
    ProviderUsage,
)
from platform_core.evaluation.api_cases import (
    APICaseEvaluationRecord,
    APICaseEvaluationSubmission,
    APITestSuiteResult,
    parse_api_test_cases,
)
from platform_core.intent.extraction import (
    IntentExtractionError,
    IntentExtractionService,
    IntentExtractor,
)
from platform_core.intent.models import (
    IntentRecord,
    IntentStatus,
    Requirement,
    RequirementPriority,
    RequirementProvenance,
    SourceRequest,
    hash_intent_record,
    hash_source_text,
    utc_now,
)
from platform_core.providers.deepseek import DeepSeekIntentExtractor
from platform_core.providers.generation import (
    DeepSeekTextGenerator,
    TextGenerationError,
    TextGenerator,
)
from platform_core.storage.models import (
    Base,
    AssuranceReportRow,
    APICaseEvaluationRow,
    ClarificationRow,
    ExecutionRunRow,
    IntentRecordRow,
    OutputRow,
    SourceRequestRow,
    TaskRow,
)

load_dotenv()


class CreateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: CreateTaskInput


class TaskResponse(BaseModel):
    task_id: UUID
    status: str
    created_at: datetime
    intent_url: str


class TaskDetailResponse(TaskResponse):
    source_request: str


class ClarificationAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1)


class SubmitClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clarification_id: UUID
    answer: ClarificationAnswer


class ClarificationResponse(BaseModel):
    clarification_id: UUID
    task_id: UUID
    intent_version: int
    question: str
    reason: str
    status: str
    answer: dict | None
    created_at: datetime
    answered_at: datetime | None


class SubmitClarificationResponse(BaseModel):
    clarification: ClarificationResponse
    intent_version: int
    task_status: str


def create_engine_for_url(database_url: str) -> Engine:
    options: dict = {}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if database_url.endswith(":memory:"):
            options["poolclass"] = StaticPool
        elif database_url.startswith("sqlite:///./"):
            Path(database_url.removeprefix("sqlite:///./")).parent.mkdir(
                parents=True, exist_ok=True
            )
    return create_engine(database_url, **options)


def create_app(
    database_url: str | None = None,
    *,
    initialize_schema: bool = False,
    intent_extractor: IntentExtractor | None = None,
    text_generator: TextGenerator | None = None,
) -> FastAPI:
    resolved_url = database_url or os.getenv(
        "DATABASE_URL", "sqlite:///./data/platform.db"
    )
    resolved_extractor = intent_extractor
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if resolved_extractor is None and deepseek_api_key:
        resolved_extractor = DeepSeekIntentExtractor(
            api_key=deepseek_api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )
    resolved_generator = text_generator
    if resolved_generator is None and deepseek_api_key:
        resolved_generator = DeepSeekTextGenerator(
            api_key=deepseek_api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )
    engine = create_engine_for_url(resolved_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize_schema:
            Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Universal AI Intelligence & Quality Assurance Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/v1/assurance/modules",
        response_model=list[DomainModuleDescriptor],
    )
    def get_assurance_modules() -> list[DomainModuleDescriptor]:
        return [module.descriptor for module in DEFAULT_DOMAIN_MODULES]

    @app.post("/v1/tasks", response_model=TaskResponse, status_code=201)
    def create_task(request: CreateTaskRequest) -> TaskResponse:
        text = request.input.text
        if not text.strip():
            raise HTTPException(status_code=422, detail="input.text must not be blank")

        task_id = uuid4()
        now = utc_now()
        source_request = SourceRequest(text=text, received_at=now)
        if resolved_extractor is None:
            intent = IntentRecord.create_initial_draft(task_id, source_request)
        else:
            try:
                intent = IntentExtractionService(resolved_extractor).extract(
                    task_id, source_request
                )
            except IntentExtractionError as error:
                raise HTTPException(
                    status_code=502, detail="Intent extraction failed"
                ) from error
        task_status = "needs_user_input" if intent.ambiguities else "received"

        with session_factory.begin() as session:
            session.add(
                TaskRow(id=str(task_id), status=task_status, created_at=now)
            )
            session.add(
                SourceRequestRow(
                    id=str(uuid4()),
                    task_id=str(task_id),
                    raw_text=text,
                    received_at=now,
                    content_hash=hash_source_text(text),
                )
            )
            session.add(
                IntentRecordRow(
                    id=str(intent.intent_id),
                    task_id=str(task_id),
                    version=intent.version,
                    status=intent.status.value,
                    content_json=intent.model_dump(mode="json"),
                    content_hash=intent.content_hash,
                    created_at=now,
                )
            )
            for clarification_id, question in zip(
                intent.clarification_ids, intent.ambiguities
            ):
                session.add(
                    ClarificationRow(
                        id=str(clarification_id),
                        task_id=str(task_id),
                        intent_version=intent.version,
                        question=question,
                        reason="This detail was identified as unclear in the request.",
                        status="open",
                        answer_json=None,
                        created_at=now,
                    )
                )

        return TaskResponse(
            task_id=task_id,
            status=task_status,
            created_at=now,
            intent_url=f"/v1/tasks/{task_id}/intent",
        )

    @app.get("/v1/tasks/{task_id}", response_model=TaskDetailResponse)
    def get_task(task_id: UUID) -> TaskDetailResponse:
        with session_factory() as session:
            task, source = _get_task_and_source(session, task_id)
            return TaskDetailResponse(
                task_id=task_id,
                status=task.status,
                created_at=_ensure_utc(task.created_at),
                intent_url=f"/v1/tasks/{task_id}/intent",
                source_request=source.raw_text,
            )

    @app.get("/v1/tasks/{task_id}/intent", response_model=IntentRecord)
    def get_intent(
        task_id: UUID, version: int | None = Query(default=None, ge=1)
    ) -> IntentRecord:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            row = _get_intent_row(session, task_id, version)
            return _validate_intent_row(row)

    @app.get(
        "/v1/tasks/{task_id}/clarifications",
        response_model=list[ClarificationResponse],
    )
    def get_clarifications(task_id: UUID) -> list[ClarificationResponse]:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            rows = session.scalars(
                select(ClarificationRow)
                .where(ClarificationRow.task_id == str(task_id))
                .order_by(ClarificationRow.created_at, ClarificationRow.id)
            ).all()
            return [_clarification_response(row) for row in rows]

    @app.post(
        "/v1/tasks/{task_id}/clarifications",
        response_model=SubmitClarificationResponse,
    )
    def submit_clarification(
        task_id: UUID, request: SubmitClarificationRequest
    ) -> SubmitClarificationResponse:
        now = utc_now()
        with session_factory.begin() as session:
            _get_task_and_source(session, task_id)
            clarification = session.get(ClarificationRow, str(request.clarification_id))
            if clarification is None or clarification.task_id != str(task_id):
                raise HTTPException(status_code=404, detail="Clarification not found")
            if clarification.status != "open":
                raise HTTPException(status_code=409, detail="Clarification is not open")

            current_row = _get_intent_row(session, task_id, None)
            current = _validate_intent_row(current_row)
            next_version = current.version + 1
            answer_value = request.answer.value.strip()
            if not answer_value:
                raise HTTPException(status_code=422, detail="answer.value must not be blank")

            explicitly_unspecified = answer_value.casefold() == "not specified"
            clarification.status = "skipped" if explicitly_unspecified else "answered"
            clarification.answer_json = {"value": answer_value}
            clarification.answered_at = now

            remaining_ambiguities = tuple(
                item for item in current.ambiguities if item != clarification.question
            )
            requirements = current.requirements
            if not explicitly_unspecified:
                requirement_number = len(requirements) + 1
                clarified_requirement = Requirement(
                    requirement_id=f"REQ-{requirement_number:03d}",
                    text=f"{clarification.question} Answer: {answer_value}",
                    category="clarification",
                    priority=RequirementPriority.MANDATORY,
                    provenance=RequirementProvenance.CLARIFIED,
                    source_location=f"clarification:{clarification.id}",
                )
                requirements = (*requirements, clarified_requirement)
            updated = _version_intent(
                current,
                version=next_version,
                requirements=requirements,
                ambiguities=remaining_ambiguities,
                status=(
                    IntentStatus.NEEDS_CLARIFICATION
                    if remaining_ambiguities
                    else IntentStatus.DRAFT
                ),
            )
            session.add(_intent_row(updated, now))
            task = session.get(TaskRow, str(task_id))
            assert task is not None
            task.status = (
                "needs_user_input" if remaining_ambiguities else "intent_draft"
            )
            session.flush()

            return SubmitClarificationResponse(
                clarification=_clarification_response(clarification),
                intent_version=updated.version,
                task_status=task.status,
            )

    @app.post("/v1/tasks/{task_id}/intent/approve", response_model=IntentRecord)
    def approve_intent(task_id: UUID) -> IntentRecord:
        now = utc_now()
        with session_factory.begin() as session:
            _get_task_and_source(session, task_id)
            current_row = _get_intent_row(session, task_id, None)
            current = _validate_intent_row(current_row)
            if current.status == IntentStatus.APPROVED:
                return current
            open_clarification = session.scalar(
                select(ClarificationRow.id)
                .where(
                    ClarificationRow.task_id == str(task_id),
                    ClarificationRow.status == "open",
                )
                .limit(1)
            )
            if current.ambiguities or open_clarification is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolve or skip open clarifications before approval",
                )
            approved = _version_intent(
                current,
                version=current.version + 1,
                status=IntentStatus.APPROVED,
            )
            session.add(_intent_row(approved, now))
            task = session.get(TaskRow, str(task_id))
            assert task is not None
            task.status = "intent_approved"
            return approved

    @app.post(
        "/v1/tasks/{task_id}/calibration",
        response_model=CalibratedPrompt,
    )
    def calibrate_task_prompt(task_id: UUID) -> CalibratedPrompt:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            intent_row = _get_intent_row(session, task_id, None)
            intent = _validate_intent_row(intent_row)
            try:
                return PromptCalibrator().calibrate(intent)
            except CalibrationError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/v1/tasks/{task_id}/runs",
        response_model=ExecutionRunResponse,
        status_code=201,
    )
    def create_execution_run(task_id: UUID) -> ExecutionRunResponse:
        if resolved_generator is None:
            raise HTTPException(
                status_code=503,
                detail="Text generation provider is not configured",
            )
        now = utc_now()
        run_id = uuid4()
        with session_factory.begin() as session:
            _get_task_and_source(session, task_id)
            intent_row = _get_intent_row(session, task_id, None)
            intent = _validate_intent_row(intent_row)
            try:
                calibrated = PromptCalibrator().calibrate(intent)
            except CalibrationError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.add(
                ExecutionRunRow(
                    id=str(run_id),
                    task_id=str(task_id),
                    intent_version=intent.version,
                    calibration_version=calibrated.calibration_version,
                    prompt_text=calibrated.prompt_text,
                    prompt_hash=calibrated.prompt_hash,
                    status=ExecutionRunStatus.RUNNING.value,
                    created_at=now,
                )
            )

        try:
            generated = resolved_generator.generate(calibrated.prompt_text)
        except TextGenerationError as error:
            completed_at = utc_now()
            with session_factory.begin() as session:
                run_row = session.get(ExecutionRunRow, str(run_id))
                assert run_row is not None
                run_row.status = ExecutionRunStatus.FAILED.value
                run_row.error_message = "Text generation failed"
                run_row.completed_at = completed_at
                task = session.get(TaskRow, str(task_id))
                assert task is not None
                task.status = "intent_approved"
            raise HTTPException(
                status_code=502,
                detail={
                    "run_id": str(run_id),
                    "message": "Text generation failed",
                },
            ) from error

        output_id = uuid4()
        completed_at = utc_now()
        report = AssuranceEngine().evaluate(
            intent,
            generated.text,
            output_id=output_id,
            created_at=completed_at,
        )
        with session_factory.begin() as session:
            run_row = session.get(ExecutionRunRow, str(run_id))
            assert run_row is not None
            session.add(
                OutputRow(
                    id=str(output_id),
                    task_id=str(task_id),
                    intent_version=intent.version,
                    text=generated.text,
                    content_hash=hash_source_text(generated.text),
                    created_at=completed_at,
                )
            )
            session.add(
                AssuranceReportRow(
                    id=str(report.report_id),
                    task_id=str(task_id),
                    output_id=str(output_id),
                    intent_version=intent.version,
                    overall_status=report.overall_status.value,
                    report_json=report.model_dump(mode="json"),
                    created_at=completed_at,
                )
            )
            session.flush()
            run_row.status = ExecutionRunStatus.COMPLETED.value
            run_row.provider = generated.provider
            run_row.model = generated.model
            run_row.usage_json = {
                "elapsed_seconds": generated.elapsed_seconds,
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
                "total_tokens": generated.total_tokens,
                "token_usage_complete": generated.token_usage_complete,
            }
            run_row.output_id = str(output_id)
            run_row.assurance_report_id = str(report.report_id)
            run_row.completed_at = completed_at

        with session_factory() as session:
            row = session.get(ExecutionRunRow, str(run_id))
            assert row is not None
            return _execution_run_response(session, row)

    @app.get(
        "/v1/tasks/{task_id}/runs/{run_id}",
        response_model=ExecutionRunResponse,
    )
    def get_execution_run(task_id: UUID, run_id: UUID) -> ExecutionRunResponse:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            row = session.get(ExecutionRunRow, str(run_id))
            if row is None or row.task_id != str(task_id):
                raise HTTPException(status_code=404, detail="Execution run not found")
            return _execution_run_response(session, row)

    @app.post(
        "/v1/tasks/{task_id}/runs/{run_id}/case-evaluations",
        response_model=APICaseEvaluationRecord,
        status_code=201,
    )
    def create_case_evaluation(
        task_id: UUID,
        run_id: UUID,
        request: APICaseEvaluationSubmission,
    ) -> APICaseEvaluationRecord:
        now = utc_now()
        evaluation_id = uuid4()
        with session_factory.begin() as session:
            _get_task_and_source(session, task_id)
            run_row = session.get(ExecutionRunRow, str(run_id))
            if run_row is None or run_row.task_id != str(task_id):
                raise HTTPException(status_code=404, detail="Execution run not found")
            if run_row.status != ExecutionRunStatus.COMPLETED.value:
                raise HTTPException(
                    status_code=409,
                    detail="Only a completed execution run can be case-evaluated",
                )
            if run_row.output_id is None:
                raise HTTPException(
                    status_code=409, detail="Execution run has no generated output"
                )
            output = session.get(OutputRow, run_row.output_id)
            if output is None or output.content_hash != request.suite_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Case-evaluation suite hash does not match the generated output",
                )
            try:
                generated_suite = parse_api_test_cases(output.text)
            except ValueError as error:
                raise HTTPException(
                    status_code=409,
                    detail="Generated output is not a supported API test suite",
                ) from error
            if tuple(case.case_id for case in generated_suite.cases) != tuple(
                result.case_id for result in request.result.case_results
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Case-evaluation results do not match the generated suite",
                )
            session.add(
                APICaseEvaluationRow(
                    id=str(evaluation_id),
                    task_id=str(task_id),
                    run_id=str(run_id),
                    target_id=request.target_id,
                    oracle_version=request.oracle_version,
                    suite_hash=request.suite_hash,
                    result_json=request.result.model_dump(mode="json"),
                    created_at=now,
                )
            )
        return APICaseEvaluationRecord(
            evaluation_id=evaluation_id,
            task_id=task_id,
            run_id=run_id,
            target_id=request.target_id,
            oracle_version=request.oracle_version,
            suite_hash=request.suite_hash,
            result=request.result,
            created_at=now,
        )

    @app.get(
        "/v1/tasks/{task_id}/runs/{run_id}/case-evaluations",
        response_model=list[APICaseEvaluationRecord],
    )
    def get_case_evaluations(
        task_id: UUID, run_id: UUID
    ) -> list[APICaseEvaluationRecord]:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            run_row = session.get(ExecutionRunRow, str(run_id))
            if run_row is None or run_row.task_id != str(task_id):
                raise HTTPException(status_code=404, detail="Execution run not found")
            rows = session.scalars(
                select(APICaseEvaluationRow)
                .where(APICaseEvaluationRow.run_id == str(run_id))
                .order_by(APICaseEvaluationRow.created_at, APICaseEvaluationRow.id)
            ).all()
            return [_api_case_evaluation_response(session, row) for row in rows]

    @app.post(
        "/v1/tasks/{task_id}/assurance",
        response_model=AssuranceReport,
        status_code=201,
    )
    def create_assurance_report(
        task_id: UUID, request: CreateAssuranceRequest
    ) -> AssuranceReport:
        now = utc_now()
        output_id = uuid4()
        with session_factory.begin() as session:
            _get_task_and_source(session, task_id)
            intent_row = _get_intent_row(session, task_id, None)
            intent = _validate_intent_row(intent_row)
            if intent.status != IntentStatus.APPROVED:
                raise HTTPException(
                    status_code=409,
                    detail="Approve the Intent Record before assurance",
                )
            report = AssuranceEngine().evaluate(
                intent,
                request.output,
                output_id=output_id,
                created_at=now,
            )
            session.add(
                OutputRow(
                    id=str(output_id),
                    task_id=str(task_id),
                    intent_version=intent.version,
                    text=request.output,
                    content_hash=hash_source_text(request.output),
                    created_at=now,
                )
            )
            session.add(
                AssuranceReportRow(
                    id=str(report.report_id),
                    task_id=str(task_id),
                    output_id=str(output_id),
                    intent_version=intent.version,
                    overall_status=report.overall_status.value,
                    report_json=report.model_dump(mode="json"),
                    created_at=now,
                )
            )
        return report

    @app.get(
        "/v1/tasks/{task_id}/assurance",
        response_model=AssuranceReport,
    )
    def get_assurance_report(task_id: UUID) -> AssuranceReport:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            row = session.scalar(
                select(AssuranceReportRow)
                .where(AssuranceReportRow.task_id == str(task_id))
                .order_by(
                    AssuranceReportRow.created_at.desc(),
                    AssuranceReportRow.id.desc(),
                )
                .limit(1)
            )
            if row is None:
                raise HTTPException(
                    status_code=404, detail="Assurance report not found"
                )
            return _validate_assurance_report_row(session, row)

    @app.get(
        "/v1/tasks/{task_id}/outputs/{output_id}",
        response_model=OutputResponse,
    )
    def get_output(task_id: UUID, output_id: UUID) -> OutputResponse:
        with session_factory() as session:
            _get_task_and_source(session, task_id)
            row = session.get(OutputRow, str(output_id))
            if row is None or row.task_id != str(task_id):
                raise HTTPException(status_code=404, detail="Output not found")
            if row.content_hash != hash_source_text(row.text):
                raise HTTPException(
                    status_code=500, detail="Stored output failed integrity check"
                )
            return OutputResponse(
                output_id=UUID(row.id),
                task_id=UUID(row.task_id),
                intent_version=row.intent_version,
                text=row.text,
                content_hash=row.content_hash,
                created_at=_ensure_utc(row.created_at),
            )

    return app


def _get_task_and_source(
    session: Session, task_id: UUID
) -> tuple[TaskRow, SourceRequestRow]:
    task = session.get(TaskRow, str(task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    source = session.scalar(
        select(SourceRequestRow).where(SourceRequestRow.task_id == str(task_id))
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source request not found")
    if source.content_hash != hash_source_text(source.raw_text):
        raise HTTPException(status_code=500, detail="Stored source request failed integrity check")
    return task, source


def _get_intent_row(
    session: Session, task_id: UUID, version: int | None
) -> IntentRecordRow:
    statement = select(IntentRecordRow).where(
        IntentRecordRow.task_id == str(task_id)
    )
    if version is not None:
        statement = statement.where(IntentRecordRow.version == version)
    else:
        statement = statement.order_by(IntentRecordRow.version.desc()).limit(1)
    row = session.scalar(statement)
    if row is None:
        raise HTTPException(status_code=404, detail="Intent Record not found")
    return row


def _validate_intent_row(row: IntentRecordRow) -> IntentRecord:
    record = IntentRecord.model_validate(row.content_json)
    if (
        record.content_hash != row.content_hash
        or record.content_hash != hash_intent_record(record)
    ):
        raise HTTPException(
            status_code=500, detail="Stored Intent Record failed integrity check"
        )
    return record


def _validate_assurance_report_row(
    session: Session, row: AssuranceReportRow
) -> AssuranceReport:
    report = AssuranceReport.model_validate(row.report_json)
    if (
        report.report_id != UUID(row.id)
        or report.task_id != UUID(row.task_id)
        or report.output_id != UUID(row.output_id)
        or report.intent_version != row.intent_version
        or report.overall_status.value != row.overall_status
    ):
        raise HTTPException(
            status_code=500, detail="Stored assurance report failed integrity check"
        )
    output = session.get(OutputRow, row.output_id)
    if output is None or output.task_id != row.task_id:
        raise HTTPException(
            status_code=500, detail="Stored assurance report output is unavailable"
        )
    if output.content_hash != hash_source_text(output.text):
        raise HTTPException(
            status_code=500, detail="Stored output failed integrity check"
        )
    return report


def _execution_run_response(
    session: Session, row: ExecutionRunRow
) -> ExecutionRunResponse:
    if row.prompt_hash != hash_source_text(row.prompt_text):
        raise HTTPException(
            status_code=500, detail="Stored calibrated prompt failed integrity check"
        )
    output = None
    if row.output_id is not None:
        output_row = session.get(OutputRow, row.output_id)
        if (
            output_row is None
            or output_row.task_id != row.task_id
            or output_row.intent_version != row.intent_version
            or output_row.content_hash != hash_source_text(output_row.text)
        ):
            raise HTTPException(
                status_code=500, detail="Stored execution output failed integrity check"
            )
        output = OutputResponse(
            output_id=UUID(output_row.id),
            task_id=UUID(output_row.task_id),
            intent_version=output_row.intent_version,
            text=output_row.text,
            content_hash=output_row.content_hash,
            created_at=_ensure_utc(output_row.created_at),
        )

    report = None
    if row.assurance_report_id is not None:
        report_row = session.get(AssuranceReportRow, row.assurance_report_id)
        if (
            report_row is None
            or report_row.task_id != row.task_id
            or report_row.output_id != row.output_id
            or report_row.intent_version != row.intent_version
        ):
            raise HTTPException(
                status_code=500, detail="Stored execution report is unavailable"
            )
        report = _validate_assurance_report_row(session, report_row)
    if row.status == ExecutionRunStatus.COMPLETED.value and (
        output is None or report is None
    ):
        raise HTTPException(
            status_code=500, detail="Completed execution run is missing its results"
        )

    usage = ProviderUsage.model_validate(row.usage_json) if row.usage_json else None
    return ExecutionRunResponse(
        run_id=UUID(row.id),
        task_id=UUID(row.task_id),
        intent_version=row.intent_version,
        calibration_version=row.calibration_version,
        calibrated_prompt=row.prompt_text,
        prompt_hash=row.prompt_hash,
        status=ExecutionRunStatus(row.status),
        provider=row.provider,
        model=row.model,
        provider_usage=usage,
        output=output,
        assurance_report=report,
        error_message=row.error_message,
        created_at=_ensure_utc(row.created_at),
        completed_at=_ensure_utc(row.completed_at) if row.completed_at else None,
    )


def _api_case_evaluation_response(
    session: Session, row: APICaseEvaluationRow
) -> APICaseEvaluationRecord:
    run_row = session.get(ExecutionRunRow, row.run_id)
    output = session.get(OutputRow, run_row.output_id) if run_row else None
    if (
        run_row is None
        or run_row.task_id != row.task_id
        or output is None
        or output.content_hash != row.suite_hash
        or output.content_hash != hash_source_text(output.text)
    ):
        raise HTTPException(
            status_code=500, detail="Stored case evaluation failed integrity check"
        )
    result = APITestSuiteResult.model_validate(row.result_json)
    return APICaseEvaluationRecord(
        evaluation_id=UUID(row.id),
        task_id=UUID(row.task_id),
        run_id=UUID(row.run_id),
        target_id=row.target_id,
        oracle_version=row.oracle_version,
        suite_hash=row.suite_hash,
        result=result,
        created_at=_ensure_utc(row.created_at),
    )


def _version_intent(
    record: IntentRecord,
    *,
    version: int,
    status: IntentStatus | None = None,
    requirements: tuple[Requirement, ...] | None = None,
    ambiguities: tuple[str, ...] | None = None,
) -> IntentRecord:
    updates: dict = {"intent_id": uuid4(), "version": version}
    if status is not None:
        updates["status"] = status
    if requirements is not None:
        updates["requirements"] = requirements
    if ambiguities is not None:
        updates["ambiguities"] = ambiguities
    candidate = record.model_copy(update=updates)
    return IntentRecord.model_validate(
        {
            **candidate.model_dump(mode="python", exclude={"content_hash"}),
            "content_hash": hash_intent_record(candidate),
        }
    )


def _intent_row(record: IntentRecord, created_at: datetime) -> IntentRecordRow:
    return IntentRecordRow(
        id=str(record.intent_id),
        task_id=str(record.task_id),
        version=record.version,
        status=record.status.value,
        content_json=record.model_dump(mode="json"),
        content_hash=record.content_hash,
        created_at=created_at,
    )


def _clarification_response(row: ClarificationRow) -> ClarificationResponse:
    return ClarificationResponse(
        clarification_id=UUID(row.id),
        task_id=UUID(row.task_id),
        intent_version=row.intent_version,
        question=row.question,
        reason=row.reason,
        status=row.status,
        answer=row.answer_json,
        created_at=_ensure_utc(row.created_at),
        answered_at=_ensure_utc(row.answered_at) if row.answered_at else None,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


app = create_app()
