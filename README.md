# Universal AI Intelligence & Quality Assurance Platform

This repository is the implementation workspace for the platform described
in the [master specification](./universal_ai_platform_MASTER_SPECIFICATION.md).

Start with the [architecture](./docs/architecture.md) for the proposed
modular-monolith structure, workflows, data boundaries, and implementation
sequence. Architecture choices marked as candidates still need validation
against team and deployment constraints.

## Development

The API persists tasks, the original request, and a validated Intent
Record. When `DEEPSEEK_API_KEY` is configured, task creation extracts the
Intent Record through DeepSeek; without it, the API creates a draft record.
The extraction contract remains injectable for deterministic testing and
other providers. The local development foundation does not provide
authentication.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
# Set DEEPSEEK_API_KEY in .env to enable DeepSeek extraction.
alembic upgrade head
uvicorn platform_core.api.app:app --reload --app-dir src
```

Run the focused tests with:

```bash
pytest
```

The default database is a local SQLite file under `data/`. Set
`DATABASE_URL` to a PostgreSQL connection URL to use PostgreSQL.

## Basic Calibrated Run

The API supports an end-to-end text workflow. Create a task with
`POST /v1/tasks`, inspect its Intent Record at `GET /v1/tasks/{task_id}/intent`,
resolve or skip open clarifications, and approve it with
`POST /v1/tasks/{task_id}/intent/approve`. Then preview the calibrated prompt
with `POST /v1/tasks/{task_id}/calibration`. Calibration requires approval and
does not call a provider. Review the returned prompt and hash before starting a
run.

`POST /v1/tasks/{task_id}/runs` calls the configured DeepSeek text generator,
assures the resulting output against the approved Intent Record, and persists
the prompt, provider usage, output, and report. It may incur provider charges.
The response includes the run ID; retrieve the durable result later with
`GET /v1/tasks/{task_id}/runs/{run_id}`. A run can complete while its assurance
status is `partially_verified` or `requires_human_review`; these are not
successful quality verdicts. The software test-plan check verifies structure
and requirement coverage but does not establish that test steps or expected
results are correct. Provider failures are recorded as failed runs and do not
create passing assurance reports.

The intent cases in `evaluation_data/development/` are synthetic
development data, not a held-out evaluation set or validated ground
truth. The extraction adapter contract is in
`src/platform_core/intent/extraction.py`; an adapter can be supplied to
`create_app` once a provider is selected.

To run the development intent diagnostic against DeepSeek, set
`DEEPSEEK_API_KEY` and run:

```bash
python -m platform_core.evaluation.run_intent
```

This makes at least one live provider request per case; malformed responses
may be retried once. Its report records the model, adapter, and prompt
versions, and includes explicit release-readiness blockers. The current
dataset is not adjudicated or held out, so its scores are diagnostic only and
must not be presented as validated quality results.

The evaluation module also defines a descriptive A/B/C comparison record for
conventional prompting, prompt optimisation, and the full platform. It reports
paired time, user-active time, and token differences only for runs that are
human-adjudicated, pass every recorded mandatory criterion, and share the same
case and repetition. Missing token usage is never estimated. Reports include
adjudication and token-coverage rates, plus domain and difficulty breakdowns.
This is measurement plumbing, not an experiment runner: it does not yet execute
matched A/B/C tasks, collect end-to-end platform timings, or establish causal
savings. The current live diagnostic measures intent extraction only. Do not
run it without intending to make potentially billable provider calls.

For any future comparison, freeze and record the dataset and acceptance
criteria; use the same cases and repetitions in all conditions; randomize run
order where feasible; and record the provider configuration, all provider-call
usage (including retries and assurance calls), elapsed time to an accepted
result, and user-active time. Human adjudicators should apply the same criteria
to every condition. Report unadjudicated cases and incomplete usage rather
than imputing results. Savings remain descriptive until the benchmark has
adequate adjudicated, held-out evidence.