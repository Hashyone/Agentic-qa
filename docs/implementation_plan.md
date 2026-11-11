# Implementation Plan

## Mission

Build a useful, provider-neutral AI intent and assurance platform as a sequence
of small, working capabilities. Keep one general core and one provider
connection. Add domain assurance modules only when distinct checks, reference
sources, or expertise are needed. Do not assume the core generalizes across
domains; measure it with a thin second domain before investing in more modules.

Every stage must be exercised as a real user workflow before the next stage
begins. Passing unit tests is necessary, but not sufficient: verify API
behavior, persistence, and operation in the local runtime. When a stage changes
provider interaction or prompt behavior, include a bounded live-provider check
when authorized and record its cost/usage and limitations. Do not make claims
that the check cannot support.

## Top Priority: Prove Value and Viability

Status: active. Do not complete the wider specification or build optional
features until this gate has evidence. The first correctness proof covers only
two task-creation cases; it is not evidence that the assurance product works
across agent tasks or creates business value.

Answer four questions with evidence:

1. **Can it verify agent work?** Evaluate the assurance result against actual
  execution and blind human adjudication. Measure critical false passes,
  false failures, precision, recall, and the share of cases the system marks
  unavailable or sends to review. A passing formatting check is not a quality
  verdict. Set acceptance thresholds before the pilot; any false pass of a
  critical failure blocks a positive claim.
2. **Does it improve outcomes?** Compare matched tasks under conventional
  prompting, prompt optimization, and the platform. Record accepted-output
  rate, critical/mandatory failures, elapsed time to accepted output,
  user-active time, total tokens across every provider call/retry, and
  redundant agent iterations from complete traces. Use the same agent, model,
  tools, task limits, and rubric where possible; randomize order and blind
  adjudicators where practical.
3. **Does it reduce agent loops?** The current product performs one generation
  and assurance pass; it does not orchestrate an autonomous agent loop. Before
  claiming fewer loops, add only the minimum experiment harness needed to run
  the same agent workflow in baseline and treatment and capture every action,
  tool call, retry, and stop reason. Define a redundant iteration before
  seeing results. Do not infer loop reduction from shorter prompts, fewer
  tokens, or a single-generation smoke test.
4. **Is the problem worth paying to solve?** Select a specific initial buyer
  and use case. Interview qualified budget owners about recent incidents,
  current workarounds, and measured cost; ask for a scoped pilot at a stated
  price rather than relying on hypothetical interest or survey intent. Record
  commitments and objections. Without credible paid-pilot or purchasing
  evidence, market value remains unproven.

Start with a small, correctness-gated pilot (provisionally six tasks with two
repetitions per condition) to test feasibility, not to claim statistical
significance. Before any pilot spend, freeze the task set, protocol, oracle,
review criteria, and practical go/no-go thresholds. Proposed efficiency
threshold: no new critical failures or lower adjudicated acceptance than the
best baseline, plus at least 15% paired median improvement in accepted-output
time or complete all-call tokens versus prompt optimization, with no more than
5% regression in other efficiency outcomes. Claim reduced agent looping only
if redundant iterations also fall by at least 15% at equal quality. Incomplete
usage means no token-savings claim.

Proceed with full product development only if verification is trustworthy for
the tested scope, a material efficiency benefit is observed, and target buyers
show credible willingness to pay. If any part fails or is inconclusive, stop
feature expansion and revise or reject the product hypothesis. This is a
directional early decision gate, not proof of causality or a market forecast.

Initial feasibility result (2026-11-11; one easy API task, one repetition per
condition; not a go decision): optimized prompting (B) generated two cases
that passed the local oracle in 1.31 seconds using 362 complete tokens.
Platform (C) generated two cases that passed the same oracle in 7.07 seconds
using 4,979 complete tokens across extraction and generation: about 5.4x the
wall time and 13.8x the tokens on this task. Conventional prompting (A) used
512 tokens but generated an over-broad/malformed suite and was not executable
under the frozen schema. C's assurance report was `partially_verified`; neither
passing suite has been human-adjudicated. No agent loop or user-active time was
measured, and willingness to pay is unknown. Raw reports are preserved in
`data/value_pilot_api_task_creation.json` and
`data/value_pilot_api_task_creation_v0.2.json`; v0.1 and v0.2 are separate
protocol attempts and must not be pooled. This is an early overhead warning for
a simple task, not evidence for or against the platform on complex agent work.

Next: do not build optional product features. Replicate the measurement on
representative, higher-value software-agent tasks and instrument actual agent
traces. Diagnose the platform's extraction/calibration overhead while
preserving all-call accounting and quality gates. Proceed only if task quality
and user value justify the overhead; otherwise simplify the treatment or stop.

## Stage Gates

For every stage, record its working behavior, focused automated tests, an
end-to-end API workflow against the local database, an operational smoke check,
and any remaining limitations. Fix failures before advancing. Do not build
later stages on unverified assumptions.

## Entry-Point Decision

Current entry point: the FastAPI application in `src/platform_core/api/app.py`,
started with `uvicorn platform_core.api.app:app --reload --app-dir src` after
the migrations are applied. Interactive API documentation is available at
`/docs`. There is no product-workflow CLI or dashboard today;
`platform_core.evaluation.run_intent` is only a provider-backed evaluation
diagnostic.

Decision: use the existing API and `/docs` for the correctness gate and value
pilot; do not build a CLI or dashboard first. If the evidence supports
continuing, build a small CLI as a thin HTTP client, not a second implementation
of business logic. It should support task inspection, clarifications,
approval, prompt preview, confirmed generation, and result inspection. Defer
the CLI until the correctness gate and initial value pilot pass; defer a
dashboard until repeated hands-on use demonstrates a need for a graphical
interface.

### 0. Existing Foundation

Status: complete. Task creation, Intent Record extraction, clarification,
approval, deterministic assurance, report persistence, and one DeepSeek
provider adapter exist. The baseline suite has 49 passing tests. This is a
prototype foundation, not a production-ready platform.

### 1. First Domain Vertical Slice

Status: complete. Implemented a discoverable domain-module contract and one
software test-plan check. The module declares its version, supported
domain/task types, required inputs, checks, and result fields. It validates a
user-requested Markdown test-case table without executing generated code.

Acceptance gate:

- The API exposes the registered module contract.
- A software test-plan criterion passes only when the requested table headers
  and at least one populated test case are present.
- A supported check with a malformed or missing table is contradicted.
- An unknown check, missing verification method, or unsupported task/domain is
  explicitly unavailable and can never produce an all-checks-passed report.
- The approved-task-to-assurance API flow persists and retrieves the output
  and report.
- The extraction prompt selects this check only when the user explicitly asks
  for the table and names its required columns.
- Focused tests, the complete suite, and a local runtime workflow all pass.

Verification: 53 tests passed and `compileall` passed. A bounded live DeepSeek
request through the local API selected the expected domain/task and check for
both table-related criteria; the supported check passed and the report
persisted and was retrieved. The check establishes requested table structure,
not whether the test cases are complete or technically correct.

### 1B. Test-Case Completeness and Review Gate

Status: complete for deterministic completeness checks. The initial software
check validated table shape only and was not sufficient evidence that the
cases were complete or correct. It now requires
unique test IDs, populated scenario/steps/expected-result fields, valid links
to Intent Record requirements, and coverage of every mandatory requirement.
Missing or invalid coverage must fail the check. When these deterministic
completeness checks pass, semantic correctness of the steps and expected
results must remain explicitly unverified and require human review; do not
report all checks passed.

Acceptance gate: verify complete/valid cases, duplicate IDs, missing fields,
unknown requirement IDs, uncovered mandatory requirements, and the explicit
human-review status through both focused tests and a persisted API workflow.
Repeat the bounded live workflow with the full table contract before advancing.

Verification: 58 tests passed, `compileall` passed, and changed files have no
diagnostics. A live software test-plan workflow extracted two mandatory
requirements, linked both in a complete case, passed deterministic structure
and coverage checks, returned `partially_verified` with semantic review
required, and persisted/retrieved the report. This confirms completeness
against the extracted Intent Record, not that the expected behavior is true in
the actual application.

### Critical Quality Gate: Test-Case Correctness and Execution

Status: passed for the first controlled target, `POST /v1/tasks`; this does not
establish correctness of arbitrary generated software tests. Generated cases
were parsed into a strict allowlisted JSON schema and run against an isolated
instance of the actual local API. Expected outcomes came from the endpoint
contract and existing API tests, not from model agreement.

Acceptance gate: generate test cases from an approved Intent Record; validate
IDs, steps, requirement links, and expected results; execute representative
positive, negative, and boundary cases against the declared local API target;
and compare actual responses/state with independently specified expectations.
Include a deliberately incorrect expected result and prove it is rejected.
Persist/retrieve the case execution and assurance result. Only execute
validated, allowlisted HTTP operations against the local test target; never run
arbitrary model-generated code or shell commands. Where behavior cannot be
determined mechanically, retain explicit human review and do not claim the
cases are correct.

### 2. Thin Second Domain

Status: complete. A business report with a requested Summary heading used the
existing generic `section_present` check. No business module or core code was
needed; prompt guidance was clarified to select supported generic methods
rather than inventing method names. No provider adapter was cloned.

Acceptance gate: verify task extraction, heading pass/fail behavior, the
approved-task-to-assurance API flow, and report persistence/retrieval. Confirm
that the business task uses the generic core and is not advertised as a
domain-specific module. Run focused and full tests plus one bounded live API
workflow before moving to Stage 3.

Verification: 54 tests passed and `compileall` passed. A bounded live DeepSeek
request through the local API selected `section_present:Summary`; assurance
passed and the persisted report was retrieved. The first live attempt invented
an unsupported method and was correctly unavailable; the prompt was tightened
and the repeated workflow passed. Existing generic checks cover both positive
and negative heading behavior.

### 3. Basic Calibrated Run

Status: complete for the basic workflow. The system can extract and approve an
Intent Record, preview a requirement-traceable calibrated prompt, execute it
through the configured DeepSeek generator, assure the generated output, and
persist/retrieve the prompt, provider result, output, and report. Generation is
behind an injectable interface for deterministic tests. Provider failure is
persisted as a failed run and creates no output or assurance report. A software
test plan that passes structural coverage still requires semantic human review.

Acceptance gate:

- Calibration accepts only an approved Intent Record and includes the original
  request, deliverable, requirements, exclusions, and acceptance criteria.
- Every mandatory requirement ID is included and traceable in the calibrated
  prompt; the prompt version and hash are recorded.
- The run API uses one provider call, stores its metadata and output, runs
  assurance on that exact output and intent version, and persists the report.
- The API exposes the calibrated prompt and returns retrievable run/output/
  assurance records; pre-approval and provider failures are explicit errors.
- Deterministic fake-provider API tests, the migration chain, the complete
  suite, and one bounded live-provider API workflow pass their stated checks.
- Stop after this basic loop. Do not add correction, source retrieval, queues,
  or broad orchestration in this stage.

Verification: 67 tests passed, `compileall` passed, the complete SQLite
migration chain upgraded through `0004_execution_runs`, and changed files have
no diagnostics. Tests cover approval gating, prompt preview without a provider
call, requirement traceability, generation success and failure, assurance,
report retrieval, and persistence across an app restart. A bounded live run
created an approved software test-plan intent, generated output, and persisted
the run with provider-reported generation usage. Assurance checked case-table
structure and mandatory behavior coverage; its overall result was
`partially_verified` because a remaining criterion was unavailable and semantic
correctness requires review. This run proves the pipeline works, not that the
generated test cases are correct or executable. The recorded usage is for the
generation call, not a complete task-wide provider-call ledger.

Correctness-gate evidence: a bounded live run generated two JSON cases linked
to existing Intent Record requirement IDs: a nonblank task request and a
whitespace-only request. Both executed against a fresh local API and matched
the independent expected status, task state/source preservation, or validation
error. Changing the first case's expected source text caused execution to fail
as intended. The passing case results were persisted against the exact
generated-output hash with oracle version `task-create-contract-v1` and
retrieved from the API. Migration `0005_api_case_evaluations` stores these
records. The generation assurance remained `partially_verified`; this proves
the two API cases are executable and match this contract, not that general
software test plans are semantically correct. Case execution is performed by
the local evaluator; the API records its submitted result and does not itself
execute cases. The prototype has no authentication, so these records are for
local development, not trusted multi-user evidence.

### 3A. Hands-On CLI

Status: deferred until the correctness gate and initial value pilot pass. Use
the existing HTTP API as the only business-logic entry point.
Prefer the Python standard-library `argparse` for the first CLI to avoid a new
runtime dependency. Support the full basic task workflow and print concise,
inspectable results, including the calibrated prompt/hash, run ID, generated
output, assurance status, and review items. Require confirmation before
billable generation; keep credentials in environment/config and never echo
them.

Acceptance gate: once authorized by the prior gates, exercise the installed
CLI against the running local API with task creation, approval, prompt preview,
a confirmed run, and result retrieval. Verify pre-approval rejection, provider
failure reporting, and prompt/output/report linkage. Include automated
CLI-to-API tests and a manual workflow. Do not start a dashboard.

### 3B. Generated Test-Case Correctness and Execution

The initial task-creation API target passed the critical quality gate above.
Any additional software behavior included in the value pilot must pass the
same generated-case, real-execution, negative-control, and persistence checks.
Use `/docs` and the local evaluator; do not wait for a CLI. Do not advance to
source retrieval, correction, more domain modules, or broad orchestration.

### 3C. Value-Add Pilot and Go/No-Go

Run only after the generated-case correctness gate passes. Compare three
matched conditions: (A) direct conventional prompting, (B) the current prompt
optimization baseline, and (C) the platform's extract/calibrate/assure loop.
Use the same model, tools, task, limits, and acceptance rubric across
conditions; randomize order where practical and have reviewers adjudicate
without seeing the condition where practical. Begin with a small pilot (for
example, six representative tasks with two repetitions per condition) to make
a build/stop decision, not a public performance claim.

Record for every task: whether an acceptable output was reached; critical and
mandatory acceptance failures; elapsed time to accepted output; user-active
time; total provider tokens across all calls and retries; model/tool calls and
retry count; and redundant iterations. Define a redundant iteration before
the pilot as a repeated action that adds no new evidence or changes no failed
criterion, and have reviewers label it from the trace. Do not infer iteration
savings from prompt length or token count.

Ratify the practical minimum before any pilot provider spend. Proposed initial
go/no-go threshold: continue only if condition C has no new critical failures
and no lower adjudicated acceptance rate than the best baseline, and improves
paired median time-to-accepted-output or complete all-call tokens by at least
15% versus prompt-optimization condition B, with no more than a 5% regression
in the other measured efficiency outcomes. Treat redundant-iteration reduction
as a separate claim: require at least a 15% paired median reduction with no
quality loss before claiming the platform helps agents avoid loops. If usage
coverage is incomplete, report it and do not claim token savings. If the pilot
is inconclusive or quality declines, stop feature expansion and revise or
reject the hypothesis. Treat pilot results as directional; they do not prove
statistical significance or causality.

Important limitation: the current product performs one calibrated generation
and assurance pass; it does not orchestrate an autonomous agent loop. The
platform cannot claim to reduce agent looping until a matched agent workflow
is exercised and its full trace is measured. A CLI is not a substitute for
that experiment.

### 4. Evidence and Source Checks

Add source/evidence records only after selecting a task with available,
reviewable source material. Verify identity and claim support separately;
unsupported source checks remain unavailable. Exercise ingestion, persistence,
and report retrieval with representative source records before adding another
domain.

### 5. Measurement and Broader Assurance

Complete adjudication, category coverage, and a held-out evaluation split
before release-quality claims or a controlled A/B/C runner. Add correction,
additional assurance methods, and further domain modules only behind
functional and evaluation gates.

## Current Work

The basic extract-calibrate-run-assure workflow and the first generated-case
correctness proof for task creation are complete. The one-task feasibility
pilot showed that B and C passed the deterministic API oracle but C had
substantial overhead on this easy task; neither output was human-adjudicated.
It is not a value win or a general verdict. Current product entry is
the FastAPI API and `/docs`; neither a workflow CLI nor dashboard is
implemented. Next, replicate on correctness-gated software-agent tasks with
instrumented agent traces. Stop feature expansion until verification quality,
matched efficiency, agent-loop evidence, and buyer willingness-to-pay have been
assessed; do not claim agent-loop savings without measured traces.