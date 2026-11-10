# Universal AI Intelligence & Quality Assurance Platform

## Specification Pack

**Version:** 1.0\
**Status:** Working technical baseline\
**Cost modelling:** Deliberately deferred\
**Architecture decisions:** Hybrid intelligence; adaptive clarification;
standalone-first with integration capability.

This specification pack translates the product concept into an initial
engineering baseline. It is intended to guide prototyping and technical
review, not to imply that every design choice has been experimentally
validated.

## Documents

1.  [`01-core-technical-specification.md`](01-core-technical-specification.md)
    --- product scope, architecture, components, workflows, requirements
    and security.
2.  [`02-data-models-and-api-contracts.md`](02-data-models-and-api-contracts.md)
    --- canonical data structures, persistence model, API contracts and
    event model.
3.  [`03-evaluation-and-verification-methodology.md`](03-evaluation-and-verification-methodology.md)
    --- assurance methodology, benchmark dataset, metrics, test design
    and acceptance criteria.
4.  [`04-implementation-backlog.md`](04-implementation-backlog.md) ---
    staged prototype backlog, dependencies, engineering tasks and
    acceptance tests.

## Core product proposition

The platform converts human intent into structured, executable
requirements; coordinates AI execution; independently evaluates outputs
against the original intent; and drives targeted correction where
appropriate.

**Human intent → intent representation → clarification → calibrated
specification → AI execution → independent assurance → correction →
transparent delivery.**

The platform is not merely a prompt rewriter, an AI wrapper or a
generator that grades its own work. Its central proposition is a
provider-neutral intent and assurance layer.

## Working architectural decisions

  -----------------------------------------------------------------------
  Area                                Working decision
  ----------------------------------- -----------------------------------
  Intelligence model                  Hybrid: probabilistic AI reasoning
                                      plus deterministic validation

  User interaction                    Adaptive: ask only when
                                      clarification materially reduces
                                      risk or uncertainty

  Product delivery                    Standalone platform and
                                      integrations

  Build sequence                      Standalone-first; integration-ready
                                      architecture

  Initial architecture                Modular monolith with explicit
                                      module boundaries

  Foundation model                    Use external providers initially;
                                      do not train a foundation model for
                                      the MVP

  Verification                        Independent assurance, claim-level
                                      where applicable, with explicit
                                      uncertainty

  Cost modelling                      Deferred to a separate exercise
  -----------------------------------------------------------------------

## Important qualification

Formulas, thresholds, confidence values and performance targets in these
documents are hypotheses or proposed engineering mechanisms until
validated. The system must not imply certainty where evidence is
incomplete. The benchmark programme is intended to determine whether the
platform materially improves task outcomes over relevant baselines.

## Global design principles

1.  Preserve the original user request and a versioned Intent Record.
2.  Never let the execution agent silently redefine acceptance criteria.
3.  Distinguish explicit requirements, inferred preferences and
    assumptions.
4.  Treat external content as untrusted data, not instructions.
5.  Separate generated output from verification evidence.
6.  Distinguish false, unsupported, partially supported and
    not-applicable claims.
7.  Use deterministic checks wherever they are more reliable than model
    judgement.
8.  Make domain-specific assurance modules extensible.
9.  Keep customer data tenant-isolated and do not use it for
    cross-customer learning without an appropriate legal basis and
    authorisation.
10. Make every consequential state transition and verification result
    traceable.


---

# Core Technical Specification

## Universal AI Intelligence & Quality Assurance Platform

**Version:** 1.0\
**Status:** Working baseline for prototype design\
**Cost modelling:** Excluded and deferred\
**Audience:** Product engineering, architecture, backend, frontend,
AI/ML and assurance teams

------------------------------------------------------------------------

## 1. Purpose

The platform is an independent intelligence and quality-assurance layer
between people and AI systems. It interprets user intent, identifies
material uncertainty, translates intent into structured execution
requirements, orchestrates AI work, independently evaluates outputs and
initiates targeted correction.

The platform is intended to support different industries and modalities
rather than being limited to software development or prompt engineering.

### 1.1 Core workflow

**Human intent → intent extraction → ambiguity detection → adaptive
clarification → calibrated execution specification → AI execution →
independent assurance → targeted correction → verified delivery.**

### 1.2 Product outcomes

The system should:

-   Reduce the expertise required to obtain useful results from AI.
-   Improve the match between outputs and the user's actual intent.
-   Detect missing, conflicting and ambiguous requirements.
-   Reduce factual, structural and constraint-related errors.
-   Make verification status and limitations transparent.
-   Work across AI providers and, progressively, text, documents, code,
    images, audio and video.
-   Improve through controlled evaluation and authorised feedback.

### 1.3 Non-goals for the first prototype

The MVP will not:

-   Train or operate its own foundation model.
-   Replace professional judgement in law, medicine, finance or other
    regulated contexts.
-   Guarantee that every factual statement is true.
-   Support every provider and modality at launch.
-   Autonomously take consequential external actions without approval.
-   Attempt to solve subjective creative quality with a universal
    objective score.

------------------------------------------------------------------------

## 2. Working architecture decisions

  -----------------------------------------------------------------------
  Decision                            Baseline
  ----------------------------------- -----------------------------------
  Intelligence                        Hybrid probabilistic reasoning and
                                      deterministic verification

  Clarification                       Adaptive, based on materiality and
                                      expected value

  Delivery                            Standalone product plus
                                      API/integrations

  Build order                         Standalone-first, integration-ready

  Backend architecture                Modular monolith initially

  AI providers                        Provider-neutral adapter interface

  Verification                        Independent from generation, with
                                      multiple verification methods

  Learning                            Separate general methods from
                                      domain-specific rules

  Cost modelling                      Deferred
  -----------------------------------------------------------------------

These are working decisions and should be revisited only when prototype
evidence or material constraints justify a change.

------------------------------------------------------------------------

## 3. System architecture

### 3.1 Logical components

1.  **Client interfaces** --- web application initially; mobile and
    embedded experiences later.
2.  **API gateway** --- authentication, request validation, rate
    limiting and routing.
3.  **Input processor** --- parses text, files and supported media.
4.  **Context manager** --- maintains task-specific context and
    references.
5.  **Intent engine** --- extracts objectives, constraints, deliverables
    and preferences.
6.  **Ambiguity engine** --- identifies missing, contradictory or
    uncertain requirements.
7.  **Clarification manager** --- asks targeted questions or records
    labelled assumptions.
8.  **Calibration engine** --- converts approved intent into an
    execution specification.
9.  **Execution orchestrator** --- manages task lifecycle, provider
    selection and retries.
10. **Provider adapters** --- normalise external AI provider interfaces.
11. **Assurance engine** --- checks outputs against acceptance criteria.
12. **Evidence engine** --- manages claims, sources and evidence
    relationships.
13. **Correction engine** --- produces targeted correction tasks.
14. **Reporting engine** --- produces output, assurance status and audit
    trail.
15. **Evaluation engine** --- runs offline benchmarks and production
    quality monitoring.
16. **Security and policy layer** --- tenant boundaries, permissions,
    retention and safety controls.

### 3.2 Architecture diagram

``` mermaid
flowchart TD
    U[User / Integration] --> API[API Gateway]
    API --> IN[Input Processor]
    IN --> CTX[Context Manager]
    CTX --> INT[Intent Engine]
    INT --> AMB[Ambiguity Engine]
    AMB --> Q{Clarification materially useful?}
    Q -->|Yes| USERQ[Clarification Manager]
    USERQ --> INT
    Q -->|No| IR[Versioned Intent Record]
    IR --> CAL[Calibration Engine]
    CAL --> SPEC[Execution Specification]
    SPEC --> ORCH[Execution Orchestrator]
    ORCH --> ADAPT[Provider Adapter]
    ADAPT --> MODEL[External AI Provider]
    MODEL --> OUT[Output Store]
    OUT --> ASSURE[Independent Assurance]
    ASSURE --> PASS{Acceptance criteria passed?}
    PASS -->|No| CORR[Correction Engine]
    CORR --> ORCH
    PASS -->|Yes / Partial| REPORT[Assurance Report]
    REPORT --> DELIVERY[User Delivery]
    EVAL[Evaluation Framework] -.-> INT
    EVAL -.-> CAL
    EVAL -.-> ASSURE
```

### 3.3 Deployment approach

Start with a modular monolith. Maintain explicit module interfaces and
separate data ownership boundaries so components can later be extracted
if operational evidence supports it. Do not introduce distributed
services, queues or complex orchestration infrastructure before needed.

A background worker and durable task queue will be required for
long-running research, code and media tasks. The first implementation
may use a lightweight queue, provided task state and retries are
durable.

------------------------------------------------------------------------

## 4. Functional requirements

  ID       Requirement                                           Priority
  -------- ----------------------------------------------------- ----------
  FR-001   Accept natural-language task requests                 P0
  FR-002   Accept supporting text and documents                  P0
  FR-003   Preserve original request                             P0
  FR-004   Generate a structured, versioned Intent Record        P0
  FR-005   Identify missing and conflicting requirements         P0
  FR-006   Ask targeted clarification questions                  P0
  FR-007   Record labelled assumptions                           P0
  FR-008   Generate a provider-neutral execution specification   P0
  FR-009   Validate specification against original intent        P0
  FR-010   Execute through at least one external provider        P0
  FR-011   Independently evaluate output                         P0
  FR-012   Report uncertainty and verification limitations       P0
  FR-013   Generate targeted corrections                         P1
  FR-014   Re-verify corrected outputs                           P1
  FR-015   Maintain task and audit history                       P0
  FR-016   Expose versioned API                                  P1
  FR-017   Support multiple providers                            P1
  FR-018   Support domain-specific assurance plugins             P1
  FR-019   Support image, audio and video inputs/outputs         P2
  FR-020   Run benchmark and regression suites                   P0

P0 denotes necessary for a credible first prototype; P1 denotes the next
capability layer; P2 denotes later expansion.

------------------------------------------------------------------------

## 5. Intent Record

The Intent Record is the canonical, provider-independent representation
of the user's intent. It must remain separate from the calibrated prompt
and generated output.

### 5.1 Required properties

-   Immutable original request reference.
-   Versioned structured interpretation.
-   Explicit/inferred/assumed provenance for requirements.
-   Stable requirement identifiers.
-   Confidence or uncertainty at field level, not only one global score.
-   Clarification history.
-   Acceptance criteria.
-   Risk and criticality classification.
-   Traceability to the source text or uploaded material.

The detailed JSON contract is in `02-data-models-and-api-contracts.md`.

### 5.2 Preservation rule

The execution agent must not be able to mutate the source Intent Record
or acceptance criteria. Any user-approved change creates a new Intent
Record version. The assurance engine evaluates against the approved
version that governed the execution.

### 5.3 Requirement provenance

Every requirement must be classified as one of:

-   `explicit` --- stated directly by the user or an authorised source.
-   `inferred` --- interpreted from context.
-   `assumed` --- filled in by the system and clearly disclosed.
-   `clarified` --- confirmed or corrected by the user.

Inferred and assumed requirements must not silently become mandatory
requirements.

------------------------------------------------------------------------

## 6. Intent intelligence and ambiguity

### 6.1 Extraction pipeline

1.  Parse the request and attached context.
2.  Identify task objective, domain, task type and deliverables.
3.  Extract mandatory requirements, preferences and exclusions.
4.  Identify audience, jurisdiction, date range and evidence needs where
    relevant.
5.  Detect contradictions and unresolved references.
6.  Attach provenance to extracted fields.
7.  Validate the structured record.
8.  Generate candidate clarifications or assumptions.

Use an AI model for semantic interpretation and deterministic code for
schema validation, required-field checks, rule enforcement and
provenance validation.

### 6.2 Uncertainty

Do not treat an LLM's self-reported confidence as a calibrated
probability. Maintain field-level confidence estimates and calibrate
them against labelled data.

A weighted summary may be useful for prioritisation:

\[ C_I = `\sum`{=tex}\_{i=1}\^{n} w_i c_i \]

where (c_i) is an estimated confidence for field (i) and (w_i) is its
importance. This is a heuristic until empirically calibrated. A critical
uncertain field must remain visible even if the average score is high.

### 6.3 Clarification decision

A candidate question should be assessed by:

-   Probability of misunderstanding without clarification.
-   Severity of the resulting error.
-   Expected reduction in uncertainty.
-   User interruption cost.
-   Whether a reversible assumption is safe.

A conceptual value-of-information model is:

\[ VOI(q) = E\[L\_{`\text{without }`{=tex}q}\] -
E\[L\_{`\text{with }`{=tex}q}\] - C(q) \]

Ask when the expected reduction in loss is material and exceeds the
interruption cost. Do not use a fixed universal threshold until it has
been evaluated.

### 6.4 Clarification behaviour

-   Ask the smallest number of questions that resolves material
    uncertainty.
-   Ask one question at a time where that is easier for the user.
-   Permit safe, labelled assumptions.
-   Explain why a question matters when not self-evident.
-   Preserve unanswered uncertainties.
-   Do not block low-risk tasks over immaterial preferences.

------------------------------------------------------------------------

## 7. Prompt calibration

The calibration engine converts the approved Intent Record into an
execution specification. It must not simply expand the prompt or add
repetitive instructions.

### 7.1 Execution specification contents

-   Task objective.
-   Relevant context.
-   Explicit requirements.
-   Preferences.
-   Exclusions.
-   Deliverable format.
-   Acceptance criteria.
-   Evidence and citation rules.
-   Tool-use requirements.
-   Domain assurance requirements.
-   Unresolved assumptions.
-   Failure and escalation behaviour.

### 7.2 Calibration process

1.  Load the approved Intent Record version.
2.  Resolve requirement dependencies.
3.  Identify contradictions.
4.  Generate a concise execution specification.
5.  Link each instruction to one or more requirement IDs.
6.  Validate that no mandatory requirement was omitted or altered.
7.  Store a versioned specification.

### 7.3 Idempotency and traceability

Unchanged inputs should not produce arbitrary changes in the
specification. Store the source Intent Record version, calibration
engine version and specification hash.

------------------------------------------------------------------------

## 8. Execution orchestration

### 8.1 Provider-neutral adapter

Each provider adapter must expose a common interface for execution,
capabilities and health checks. Provider-specific options should be
isolated inside the adapter.

Example:

``` python
from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    async def execute(self, specification: dict, context: dict) -> dict:
        ...

    @abstractmethod
    async def capabilities(self) -> dict:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
```

### 8.2 Routing criteria

Select providers based on:

-   Supported modality and task type.
-   Structured-output and tool-use capability.
-   Context requirements.
-   Reliability and evaluation history.
-   User or organisation policy.
-   Data residency and provider data-handling terms.
-   Availability and latency.
-   Cost, once the separate cost model is completed.

Do not assume one model is optimal for every task.

### 8.3 Task lifecycle

``` text
RECEIVED
  -> INTERPRETING
  -> NEEDS_USER_INPUT (optional)
  -> CALIBRATING
  -> READY
  -> EXECUTING
  -> VERIFYING
  -> CORRECTING (optional, bounded)
  -> COMPLETED / PARTIALLY_VERIFIED
```

Other states: `FAILED`, `CANCELLED`, `REQUIRES_HUMAN_REVIEW`.

Every transition must be persisted with timestamp, actor/component and
reason.

### 8.4 Retries and failure handling

Distinguish transient provider failures from invalid outputs and
assurance failures. Use bounded retries with idempotency controls. Do
not treat a provider timeout as proof that execution did not occur.
Store provider request identifiers where available.

------------------------------------------------------------------------

## 9. Independent assurance

### 9.1 Principle

Generation and assurance must be separate logical responsibilities.
Using a different model can reduce some correlated errors but does not
establish independence by itself. Prefer deterministic checks,
authoritative evidence, executable tests and independent tools where
possible.

### 9.2 Assurance dimensions

1.  Structural compliance.
2.  Requirement compliance.
3.  Factual support.
4.  Citation and source integrity.
5.  Logical consistency.
6.  Numerical correctness.
7.  Domain-specific quality.
8.  Style and presentation.
9.  Safety and policy compliance.

### 9.3 Claim-level evaluation

For factual tasks, extract atomic claims and evaluate each against
evidence. Preserve the claim's location in the output and links to
sources. A document-wide assessment must not conceal unsupported
critical claims.

### 9.4 Verification statuses

-   `supported`
-   `contradicted`
-   `partially_supported`
-   `unverified`
-   `not_applicable`
-   `requires_human_review`

Source existence, source credibility and claim support are distinct
checks.

### 9.5 Quality and hard gates

A weighted quality score may help compare outputs:

\[ Q = `\sum`{=tex}\_{i=1}\^{n} w_i s_i \]

However, critical requirements must be hard gates. A high
writing-quality score cannot compensate for fabricated legal
authorities, missing mandatory functionality or a security
vulnerability.

Never label an output "100% accurate". Report coverage, evidence
limitations and unresolved issues.

------------------------------------------------------------------------

## 10. Correction engine

A correction request must identify:

-   Failed requirement ID.
-   Output location.
-   Failure description.
-   Evidence or test result.
-   Severity.
-   Expected correction.
-   Re-verification method.

The engine should request the smallest correction likely to resolve the
failure. It should preserve prior output versions, compare changed
sections, recheck affected claims and requirements, and re-run critical
global checks.

Correction attempts must be bounded. Repeated failure should trigger
escalation or a transparent partial result rather than an infinite loop.

------------------------------------------------------------------------

## 11. Domain assurance modules

The universal core supplies intent interpretation, orchestration,
traceability and common verification infrastructure. Domain modules
provide specialised acceptance criteria, reference sources and tests.

### 11.1 Academic module

Potential checks:

-   Bibliographic record and DOI resolution.
-   Source identity and publication metadata.
-   Citation-to-claim support.
-   Quotation accuracy.
-   Citation style and bibliography consistency.
-   Methodology and evidence limitations.
-   Distinction between fact, inference and opinion.

### 11.2 Legal module

Potential checks:

-   Jurisdiction and applicable law.
-   Existence and status of legislation and decisions.
-   Citation, quotation and pinpoint accuracy.
-   Subsequent treatment where reliable data is available.
-   Procedural and professional requirements.
-   Whether cited authority supports the proposition.

Legal conclusions requiring professional judgement must be escalated to
a qualified human. Access to authoritative legal databases may require
licensed integrations.

### 11.3 Software module

Potential checks:

-   Unit and integration tests.
-   Acceptance tests linked to requirements.
-   Static analysis and dependency scanning.
-   Runtime testing in a controlled environment.
-   Security testing.
-   Regression tests.
-   Build and deployment checks.

### 11.4 Creative and multimodal module

Potential checks:

-   Brief and storyboard compliance.
-   Character, object and scene continuity.
-   Branding and visual identity.
-   Audio/visual synchronisation.
-   Aspect ratio, resolution and file-format requirements.
-   Text and logo correctness.

Subjective artistic quality must be assessed against user-approved
criteria and should not be represented as objective truth.

### 11.5 Plugin contract

Each module should declare supported task types, required inputs,
checks, outputs and version. The core must be able to skip unsupported
checks and report them as unavailable rather than silently passing them.

------------------------------------------------------------------------

## 12. Security, privacy and governance

The system may process confidential legal documents, research, source
code, business plans and personal information.

Minimum controls:

-   Encryption in transit and at rest.
-   Tenant isolation and organisation-level access controls.
-   Role-based permissions.
-   Secure secret and API key management.
-   Configurable retention and deletion.
-   Provider data-use and retention controls.
-   Audit logging.
-   Malware scanning and safe file parsing.
-   Prompt-injection resistance.
-   Human approval for consequential external actions.
-   Data minimisation.
-   Export and deletion workflows.

Treat uploaded files, webpages and retrieved material as untrusted data,
not system instructions. A document cannot override the user's original
intent or platform policy.

Design for South Africa's POPIA requirements and support
jurisdiction-specific privacy configurations. Obtain legal review before
production deployment in regulated markets.

Cross-customer learning must not use confidential task content without a
valid legal basis, transparent policy and required authorisation. Prefer
opt-in feedback, synthetic examples, aggregated metrics and properly
governed datasets.

------------------------------------------------------------------------

## 13. Suggested technology baseline

  Layer              Candidate
  ------------------ ---------------------------------------------
  Backend            Python, FastAPI
  Frontend           React / Next.js
  Primary database   PostgreSQL
  Vector retrieval   pgvector where justified
  Object storage     S3-compatible storage
  Background jobs    Durable queue / workflow engine
  Containers         Docker
  Observability      OpenTelemetry-compatible instrumentation
  Version control    GitHub or equivalent
  Testing            pytest plus API and end-to-end test tooling

These are candidates, not final vendor commitments. Avoid introducing a
technology solely because it is fashionable. Select based on team
capability, deployment constraints, security and maintainability.

------------------------------------------------------------------------

## 14. Non-functional requirements

  ID        Requirement
  --------- ---------------------------------------------------------
  NFR-001   Every task has a unique ID and durable state
  NFR-002   Important records are versioned
  NFR-003   Provider adapters are replaceable
  NFR-004   Tenant data is isolated
  NFR-005   Verification results are traceable to evidence or tests
  NFR-006   Unverified results are explicitly labelled
  NFR-007   Long-running tasks can resume after worker failure
  NFR-008   API contracts are versioned
  NFR-009   Sensitive data is not logged unnecessarily
  NFR-010   Core modules have automated tests
  NFR-011   Evaluation results are reproducible where possible
  NFR-012   Human review can be requested or required

Performance, availability and scale targets should be set after workload
and deployment assumptions are defined. They are not invented in this
version.

------------------------------------------------------------------------

## 15. MVP definition

A credible MVP should support:

1.  Text-based task input.
2.  Document context ingestion.
3.  Intent Record generation and versioning.
4.  Ambiguity detection and adaptive clarification.
5.  Calibrated execution specification.
6.  One external AI provider.
7.  Structural and requirement verification.
8.  Basic factual claim and source verification for research tasks.
9.  Targeted correction.
10. Transparent assurance report.
11. Evaluation harness and benchmark comparison.

The first cross-domain demonstration should cover academic research,
software development and an AI-video brief. Full automated video
verification can follow after text and document workflows prove the
architecture.

------------------------------------------------------------------------

## 16. Definition of success

The prototype is successful when it demonstrates measurable improvement
over conventional prompting and prompt optimisation baselines on a
held-out benchmark, without unacceptable false-positive rates or
excessive user interruption.

It must show:

-   Better extraction of mandatory requirements.
-   Detection of material ambiguity and contradictions.
-   Improved task acceptance rate.
-   More reliable identification of unsupported claims.
-   Traceable corrections.
-   Honest reporting of uncertainty and coverage.

A successful prototype justifies further development; it does not by
itself prove production readiness or market differentiation.


---

# Data Models and API Contracts

## Universal AI Intelligence & Quality Assurance Platform

**Version:** 1.0\
**Status:** Proposed implementation contract\
**Dependency:** Core Technical Specification v1.0

------------------------------------------------------------------------

## 1. Design principles

1.  Use provider-neutral data structures.
2.  Preserve the original request separately from its interpretation.
3.  Version mutable business records.
4.  Give requirements stable IDs.
5.  Record provenance for extracted fields.
6.  Keep outputs, claims, evidence and verification results distinct.
7.  Use explicit status enums.
8.  Store large binary objects in object storage; keep metadata and
    references in PostgreSQL.
9.  Use UTC timestamps in storage and ISO 8601 at API boundaries.
10. Validate all external payloads.

The examples below are illustrative contracts. They should be converted
into validated Pydantic models and OpenAPI schemas during
implementation.

------------------------------------------------------------------------

## 2. Canonical identifiers and common fields

Use UUIDs for internal primary identifiers unless an external provider
supplies its own identifier. Every persisted record should include:

``` json
{
  "id": "uuid",
  "created_at": "2026-11-09T12:00:00Z",
  "updated_at": "2026-11-09T12:00:00Z",
  "created_by": "user-or-service-id"
}
```

For versioned records, include `version`, `supersedes_id` where
applicable, and a content hash.

------------------------------------------------------------------------

## 3. Intent Record schema

### 3.1 Example

``` json
{
  "intent_id": "uuid",
  "task_id": "uuid",
  "version": 1,
  "source_request": {
    "text": "Help me prepare a research paper about AI and economic development in Africa.",
    "attachments": [],
    "received_at": "2026-11-09T12:00:00Z"
  },
  "task": {
    "objective": "Prepare a research paper",
    "domain": "academic",
    "task_type": "research_and_writing",
    "deliverables": ["research paper"]
  },
  "context": {
    "description": null,
    "audience": null,
    "jurisdiction": null,
    "geographic_scope": ["Africa"],
    "time_period": null,
    "reference_materials": []
  },
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "text": "Address AI and economic development in Africa",
      "category": "scope",
      "priority": "mandatory",
      "provenance": "explicit",
      "source_location": "source_request.text",
      "confidence": 0.97
    }
  ],
  "quality_criteria": [],
  "evidence_requirements": [],
  "exclusions": [],
  "ambiguities": [],
  "assumptions": [],
  "clarification_ids": [],
  "acceptance_criteria": [],
  "risk_profile": {
    "level": "unclassified",
    "critical_requirement_ids": []
  },
  "status": "draft",
  "content_hash": "sha256:..."
}
```

### 3.2 Enums

**Requirement priority** - `mandatory` - `preferred` - `optional`

**Provenance** - `explicit` - `inferred` - `assumed` - `clarified`

**Intent status** - `draft` - `needs_clarification` - `approved` -
`superseded` - `cancelled`

**Risk level** - `low` - `moderate` - `high` - `critical` -
`unclassified`

### 3.3 Validation rules

-   Every requirement has a unique ID within the Intent Record.
-   Every inferred or assumed requirement has provenance and a
    confidence/uncertainty field.
-   A critical requirement cannot be silently downgraded.
-   An approved Intent Record is immutable; edits create a new version.
-   Every acceptance criterion references one or more requirement IDs.
-   The original source request is retained subject to the user's
    retention policy.

------------------------------------------------------------------------

## 4. Clarification model

``` json
{
  "clarification_id": "uuid",
  "task_id": "uuid",
  "intent_version": 1,
  "question": "Which citation style should the paper use?",
  "reason": "The citation style affects formatting and bibliography requirements.",
  "related_requirement_ids": [],
  "materiality": "moderate",
  "answer_type": "single_choice_or_text",
  "options": ["APA", "Harvard", "Chicago", "Other"],
  "status": "open",
  "answer": null,
  "answered_at": null
}
```

Statuses: `open`, `answered`, `skipped`, `expired`, `not_required`.

The system must support a safe default or explicit "not specified"
response where appropriate. A question should not be asked merely
because a field is empty.

------------------------------------------------------------------------

## 5. Execution Specification model

``` json
{
  "specification_id": "uuid",
  "task_id": "uuid",
  "intent_id": "uuid",
  "intent_version": 1,
  "version": 1,
  "objective": "Prepare a research paper...",
  "context": [],
  "instructions": [],
  "constraints": [],
  "exclusions": [],
  "deliverables": [],
  "acceptance_criteria": [
    {
      "criterion_id": "AC-001",
      "requirement_ids": ["REQ-001"],
      "description": "The paper addresses the stated geographic and subject scope.",
      "verification_method": "requirement_review",
      "critical": true
    }
  ],
  "evidence_policy": {},
  "assumptions": [],
  "unresolved_items": [],
  "calibration_engine_version": "0.1.0",
  "content_hash": "sha256:...",
  "status": "validated"
}
```

Statuses: `draft`, `validated`, `approved`, `superseded`, `rejected`.

The calibration engine must produce a traceability map from each
instruction and acceptance criterion to the source requirement IDs.

------------------------------------------------------------------------

## 6. Provider and execution models

### 6.1 Provider capability record

``` json
{
  "provider_id": "uuid",
  "name": "provider-name",
  "adapter_key": "provider_adapter",
  "capabilities": {
    "modalities_in": ["text", "pdf"],
    "modalities_out": ["text", "json"],
    "tool_use": true,
    "structured_output": true,
    "max_context_tokens": null
  },
  "policy": {
    "approved_for_data_classes": ["public", "internal"],
    "region": null
  },
  "status": "active"
}
```

Do not hard-code unsupported capability values. Capabilities should be
discovered or maintained from verified provider documentation and tested
adapter behaviour.

### 6.2 Execution record

``` json
{
  "execution_id": "uuid",
  "task_id": "uuid",
  "specification_id": "uuid",
  "provider_id": "uuid",
  "provider_request_id": null,
  "attempt": 1,
  "status": "submitted",
  "started_at": "2026-11-09T12:00:00Z",
  "completed_at": null,
  "input_hash": "sha256:...",
  "output_id": null,
  "error": null,
  "metadata": {}
}
```

Execution statuses: `queued`, `submitted`, `running`, `succeeded`,
`failed`, `timed_out`, `cancelled`.

### 6.3 Normalised output envelope

``` json
{
  "output_id": "uuid",
  "task_id": "uuid",
  "execution_id": "uuid",
  "version": 1,
  "content": {
    "type": "text",
    "text": "Generated content"
  },
  "artifacts": [],
  "provider_metadata": {},
  "created_at": "2026-11-09T12:00:00Z",
  "content_hash": "sha256:..."
}
```

Artifacts should reference object storage and include MIME type, size,
checksum and access policy.

------------------------------------------------------------------------

## 7. Claim and evidence models

### 7.1 Claim

``` json
{
  "claim_id": "uuid",
  "output_id": "uuid",
  "text": "The extracted factual statement.",
  "claim_type": "empirical",
  "location": {
    "section": "economic_impact",
    "page": null,
    "start_offset": null,
    "end_offset": null
  },
  "criticality": "normal",
  "verification_status": "unverified"
}
```

Claim types may include `empirical`, `legal`, `historical`, `numerical`,
`attribution`, `definition`, `opinion`, `prediction` and `other`.

### 7.2 Evidence record

``` json
{
  "evidence_id": "uuid",
  "claim_id": "uuid",
  "source": {
    "uri": "https://example.org/source",
    "title": "Source title",
    "publisher": "Publisher",
    "published_at": null,
    "retrieved_at": "2026-11-09T12:00:00Z"
  },
  "source_type": "primary",
  "source_reliability": "not_assessed",
  "relevance": "not_assessed",
  "support_relationship": "not_assessed",
  "supporting_excerpt": null,
  "locator": null
}
```

Store only excerpts needed for verification, subject to copyright and
source access restrictions. Record the retrieval time and source version
where possible.

### 7.3 Verification result

``` json
{
  "verification_id": "uuid",
  "task_id": "uuid",
  "output_id": "uuid",
  "claim_id": "uuid",
  "criterion_id": null,
  "method": "source_comparison",
  "status": "unverified",
  "confidence": null,
  "explanation": "Insufficient evidence was found.",
  "evidence_ids": [],
  "review_required": false,
  "verifier_version": "0.1.0",
  "verified_at": "2026-11-09T12:00:00Z"
}
```

Verification statuses: `supported`, `contradicted`,
`partially_supported`, `unverified`, `not_applicable`,
`requires_human_review`.

Do not force all verification methods to emit a numerical confidence. If
a score is emitted, document its meaning and calibration.

------------------------------------------------------------------------

## 8. Correction and report models

### 8.1 Correction issue

``` json
{
  "issue_id": "uuid",
  "task_id": "uuid",
  "output_id": "uuid",
  "requirement_id": "REQ-001",
  "severity": "high",
  "location": {},
  "description": "The output does not satisfy the required geographic scope.",
  "evidence_ids": [],
  "requested_change": "Revise the relevant section to address the specified scope.",
  "verification_plan": ["AC-001"],
  "status": "open"
}
```

### 8.2 Assurance report

``` json
{
  "report_id": "uuid",
  "task_id": "uuid",
  "intent_version": 1,
  "output_id": "uuid",
  "overall_status": "partially_verified",
  "quality_assessment": null,
  "mandatory_gates": [],
  "requirement_results": [],
  "claim_summary": {
    "supported": 0,
    "contradicted": 0,
    "partially_supported": 0,
    "unverified": 0
  },
  "limitations": [],
  "human_review_items": [],
  "created_at": "2026-11-09T12:00:00Z"
}
```

The report must distinguish verification coverage from correctness. A
result with many unchecked claims must not appear fully verified.

------------------------------------------------------------------------

## 9. Proposed relational database

  -----------------------------------------------------------------------
  Table                   Important fields        Notes
  ----------------------- ----------------------- -----------------------
  `users`                 id, email, status       Account identity

  `organisations`         id, name, policy        Tenant

  `memberships`           user_id,                Access control
                          organisation_id, role   

  `tasks`                 id, owner_id,           Workflow root
                          organisation_id, status 

  `source_requests`       task_id, raw_text,      Original request
                          attachments             

  `intent_records`        id, task_id, version,   Versioned canonical
                          content_json, hash      intent

  `requirements`          id, intent_id,          Traceable requirements
                          requirement_key,        
                          content_json            

  `clarifications`        id, task_id,            User interaction
                          question_json,          
                          answer_json, status     

  `specifications`        id, task_id, version,   Calibrated spec
                          content_json, hash      

  `providers`             id, name, adapter_key,  Provider registry
                          capabilities_json       

  `executions`            id, task_id,            Execution attempts
                          provider_id, status     

  `outputs`               id, task_id,            Generated outputs
                          execution_id, version,  
                          artifact_ref            

  `claims`                id, output_id,          Extracted claims
                          claim_json              

  `evidence`              id, claim_id,           Evidence
                          source_json             

  `verifications`         id, output_id,          Verification results
                          claim_id, status        

  `correction_issues`     id, task_id,            Remediation
                          issue_json, status      

  `assurance_reports`     id, task_id, output_id, Final report
                          report_json             

  `audit_events`          id, task_id, actor,     Traceability
                          event_type, payload     

  `evaluation_runs`       id, dataset_version,    Benchmark records
                          results                 
  -----------------------------------------------------------------------

Use JSONB for evolving domain-specific structures, but retain relational
columns for common filtering, joins, ownership, status and indexing. Do
not turn the entire database into an unstructured JSON store.

### 9.1 Tenant isolation

Every tenant-owned record must be scoped to an organisation or user
owner. Enforce access in the application and, where appropriate,
PostgreSQL row-level security. Test cross-tenant access explicitly.

### 9.2 File storage

Store file metadata in PostgreSQL and binary content in object storage.
Metadata should include:

-   Object key.
-   MIME type.
-   Size.
-   Checksum.
-   Owner and tenant.
-   Classification.
-   Retention policy.
-   Malware scan status.
-   Processing status.

------------------------------------------------------------------------

## 10. REST API contracts

Base path: `/v1`

All requests and responses use JSON unless the endpoint explicitly
handles file upload or streaming. Use standard HTTP status codes and a
consistent error envelope.

### 10.1 Create task

`POST /v1/tasks`

Request:

``` json
{
  "input": {
    "text": "Help me prepare a research paper about AI and economic development in Africa."
  },
  "preferences": {
    "interaction_mode": "adaptive"
  }
}
```

Response `201`:

``` json
{
  "task_id": "uuid",
  "status": "received",
  "created_at": "2026-11-09T12:00:00Z"
}
```

### 10.2 Get task

`GET /v1/tasks/{task_id}`

Returns task status, current stage, timestamps and links to available
resources. Do not expose provider secrets or internal chain-of-thought.

### 10.3 Add context

`POST /v1/tasks/{task_id}/context`

Use multipart upload or a pre-authorised object-storage upload flow.
Validate file size, MIME type, malware status and tenant ownership.
Return a context asset ID and processing status.

### 10.4 Get Intent Record

`GET /v1/tasks/{task_id}/intent`

Return the current approved or draft Intent Record and its version.
Historical versions should be retrievable through an explicit version
parameter or subresource.

### 10.5 Submit clarification

`POST /v1/tasks/{task_id}/clarifications`

Request:

``` json
{
  "clarification_id": "uuid",
  "answer": {
    "value": "APA"
  }
}
```

Response includes the updated task stage and new Intent Record version
if the answer changes the interpretation.

### 10.6 Get execution specification

`GET /v1/tasks/{task_id}/specification`

Return the calibrated specification, source Intent Record version and
validation status.

### 10.7 Start execution

`POST /v1/tasks/{task_id}/execute`

Request:

``` json
{
  "specification_id": "uuid",
  "approval": true
}
```

Response `202`:

``` json
{
  "execution_id": "uuid",
  "task_id": "uuid",
  "status": "queued"
}
```

### 10.8 Get assurance report

`GET /v1/tasks/{task_id}/assurance`

Return requirement-level results, claim summary, evidence references,
mandatory gates, limitations and human-review items.

### 10.9 Initiate correction

`POST /v1/tasks/{task_id}/corrections`

Request:

``` json
{
  "issue_ids": ["uuid"],
  "approval": true
}
```

Response `202` with correction execution ID and status.

### 10.10 Get final report

`GET /v1/tasks/{task_id}/report`

Return the final deliverable references and assurance report. Access
must be checked against task ownership and tenant permissions.

------------------------------------------------------------------------

## 11. API conventions

### 11.1 Error envelope

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": [],
    "request_id": "uuid"
  }
}
```

### 11.2 Idempotency

Support `Idempotency-Key` on task creation, execution initiation and
correction initiation. Repeated requests with the same key and
equivalent payload should not create duplicate operations.

### 11.3 Pagination

Use cursor-based pagination for event histories and large result sets.
Return `next_cursor` when more results exist.

### 11.4 Authentication

Use secure session authentication for the standalone application and
scoped API keys or OAuth-based authorisation for integrations. Never
place secrets in URLs.

### 11.5 Webhooks

Potential events:

-   `task.needs_user_input`
-   `task.execution_started`
-   `task.verification_completed`
-   `task.correction_started`
-   `task.completed`
-   `task.failed`

Sign webhook payloads, include event IDs and support retry with replay
protection.

------------------------------------------------------------------------

## 12. Event and audit model

Important events should be append-only:

-   Task created.
-   Context added.
-   Intent extracted.
-   Clarification requested.
-   Clarification answered.
-   Intent approved or amended.
-   Specification generated and validated.
-   Provider selected.
-   Execution started/completed/failed.
-   Output stored.
-   Verification completed.
-   Correction initiated/completed.
-   Report delivered.
-   User feedback received.

Audit records should identify the actor or service, event type,
timestamp, task and relevant record version. Avoid logging unnecessary
personal or confidential content.

------------------------------------------------------------------------

## 13. API and data acceptance tests

1.  A task can be created and retrieved by its owner.
2.  An unrelated tenant cannot access the task.
3.  Original request text is preserved.
4.  Intent edits create a new version.
5.  Requirement IDs remain traceable across specifications.
6.  A clarification answer updates the intended version without erasing
    history.
7.  A provider response is normalised into the output envelope.
8.  Claims link to the correct output version.
9.  Verification records link to claims or acceptance criteria.
10. A report distinguishes unverified claims from contradicted claims.
11. Duplicate execution requests with the same idempotency key do not
    launch duplicate work.
12. Webhook signatures can be validated.
13. Deletion and retention policies apply to both database records and
    object storage.

------------------------------------------------------------------------

## 14. Open implementation decisions

Resolve during implementation planning:

-   Pydantic version and schema conventions.
-   Queue/workflow engine.
-   Authentication provider.
-   Object storage provider.
-   Whether vector search is needed for the first release.
-   Exact event delivery semantics.
-   Data retention defaults.
-   File size and modality limits.
-   Provider capability discovery and update process.

Do not resolve these by assumption where they materially affect
security, reliability or operating constraints.


---

# Evaluation and Verification Methodology

## Universal AI Intelligence & Quality Assurance Platform

**Version:** 1.0\
**Status:** Proposed research and engineering protocol\
**Purpose:** Establish whether the platform measurably improves AI task
outcomes.

------------------------------------------------------------------------

## 1. Purpose

This document defines how to test the platform's central proposition:

> Converting human intent into structured requirements, calibrating
> execution and independently verifying outputs produces more reliable
> task outcomes than conventional prompting alone.

The system must be evaluated empirically. Product claims should be
limited to what the benchmark results demonstrate.

## 2. Evaluation principles

1.  Compare against credible baselines.
2.  Use held-out test cases.
3.  Separate development data from final evaluation data.
4.  Define expected outcomes before running the system.
5.  Use independent human adjudication for ambiguous ground truth.
6.  Measure false positives as well as detection success.
7.  Report coverage and uncertainty.
8.  Test multiple providers where feasible.
9.  Preserve reproducible test configurations.
10. Avoid using the same model as generator, ground-truth author and
    sole evaluator.

------------------------------------------------------------------------

## 3. Evaluation layers

### 3.1 Intent interpretation

Does the platform identify the actual objective, scope, deliverables and
constraints?

### 3.2 Clarification

Does it identify important ambiguity and ask useful questions without
excessive interruption?

### 3.3 Calibration

Does the execution specification preserve the user's requirements and
translate them into actionable instructions?

### 3.4 Execution

Does the selected AI provider produce a useful output under the
calibrated specification?

### 3.5 Assurance

Does the system detect factual, structural, logical and requirement
failures?

### 3.6 Correction

Can it resolve identified failures without introducing new material
errors?

### 3.7 End-to-end outcome

Does the complete workflow improve task success and user experience?

------------------------------------------------------------------------

## 4. Universal Task Evaluation Dataset

Create a versioned dataset spanning different domains, task types,
difficulty levels and failure modes.

### 4.1 Initial domains

-   Academic research and writing.
-   Legal research and drafting.
-   Software development.
-   Business analysis.
-   Numerical and financial analysis.
-   Creative content and video briefs.
-   General personal and professional productivity.

The initial prototype should focus on academic research, software
development and an AI-video brief. Legal cases should be added only when
reliable authoritative reference material and appropriate human
reviewers are available.

### 4.2 Test categories

  -----------------------------------------------------------------------
  Category                            Test design
  ----------------------------------- -----------------------------------
  Vague request                       Request lacks important scope or
                                      audience

  Missing context                     Essential context is absent

  Contradictory instructions          Requirements conflict

  Hidden constraints                  Requirements appear in attachments

  False premise                       User request assumes something
                                      incorrect

  Citation trap                       References are fabricated or do not
                                      support claims

  Numerical trap                      Calculation or unit conversion is
                                      wrong

  Requirement conflict                Deliverable conflicts with a stated
                                      constraint

  Prompt injection                    External content contains malicious
                                      instructions

  Multimodal inconsistency            Text brief conflicts with
                                      visual/audio requirements

  Adversarial phrasing                Important requirement is easy to
                                      overlook

  Over-specification                  Excessive constraints make task
                                      infeasible
  -----------------------------------------------------------------------

### 4.3 Dataset record

``` json
{
  "case_id": "UAT-0001",
  "dataset_version": "0.1.0",
  "domain": "academic",
  "task_type": "research_writing",
  "difficulty": "moderate",
  "user_prompt": "Prepare a research paper on AI and economic development in Africa.",
  "context_assets": [],
  "planted_issues": [],
  "expected_intent": {},
  "mandatory_requirements": [],
  "acceptable_clarifications": [],
  "unsafe_assumptions": [],
  "acceptance_tests": [],
  "ground_truth_sources": [],
  "adjudication_notes": {}
}
```

### 4.4 Ground truth

Each case should have:

-   An expected Intent Record or acceptable range of interpretations.
-   Mandatory and optional requirements.
-   Acceptable clarifying questions.
-   Unsafe or unjustified assumptions.
-   Expected output acceptance criteria.
-   Known planted errors where applicable.
-   Reliable reference sources or executable tests.
-   Adjudication notes.

For open-ended creative tasks, ground truth should be rubric-based and
preferably assessed by multiple independent reviewers. Do not pretend
there is one objectively correct creative output.

### 4.5 Dataset governance

-   Version each dataset release.
-   Record author and reviewer roles.
-   Keep a hidden holdout set.
-   Prevent test leakage into prompt templates.
-   Document changes to cases.
-   Use synthetic or licensed materials where possible.
-   Do not include confidential user content without authorisation.

------------------------------------------------------------------------

## 5. Experimental baselines

Run at least three conditions on equivalent cases.

### Baseline A --- Conventional prompting

The original user prompt is submitted directly to the chosen AI
provider.

### Baseline B --- Prompt optimisation

The original prompt is rewritten or optimised, but there is no separate
Intent Record and independent assurance loop.

### Treatment C --- Full platform

Intent extraction, adaptive clarification, calibration, execution,
independent assurance and targeted correction are used.

Where possible, hold the underlying generation model,
temperature/settings, available tools and reference material constant.
If this cannot be done, document the difference.

Run repeated trials for stochastic systems and report variation.

------------------------------------------------------------------------

## 6. Metrics

### 6.1 Intent extraction

**Requirement precision**

\[ P_r =
`\frac{\text{correctly extracted requirements}}{\text{all extracted requirements}}`{=tex}
\]

**Requirement recall**

\[ R_r =
`\frac{\text{correctly extracted requirements}}{\text{all expected requirements}}`{=tex}
\]

Report both micro and macro averages. A system that invents many
requirements may have high recall but poor precision.

### 6.2 Clarification

Measure:

-   Material ambiguity detection recall.
-   Clarification precision.
-   Percentage of questions judged necessary.
-   Percentage of material uncertainties left unresolved.
-   Average number of questions per task.
-   User response burden.
-   Frequency and severity of harmful assumptions.

A question is useful only if it resolves a material uncertainty or
changes the appropriate execution path.

### 6.3 Calibration fidelity

Measure whether:

-   All mandatory requirements appear in the execution specification.
-   Exclusions are preserved.
-   Preferences are not incorrectly elevated to mandatory requirements.
-   Assumptions are labelled.
-   Acceptance criteria are traceable to the Intent Record.
-   The specification does not introduce unsupported constraints.

### 6.4 Factual and citation verification

**Detection recall**

\[ Recall = `\frac{TP}{TP+FN}`{=tex} \]

**Detection precision**

\[ Precision = `\frac{TP}{TP+FP}`{=tex} \]

Where: - TP = planted or adjudicated error correctly flagged. - FP =
correct or adequately supported content incorrectly flagged. - FN =
error not detected.

Also measure: - Citation existence accuracy. - Citation-to-claim support
accuracy. - Source reliability classification. - Unsupported-claim rate
in final outputs. - False reassurance rate: incorrect claims reported as
supported.

### 6.5 Requirement compliance

Measure the proportion of mandatory acceptance criteria passed. Report
critical-gate failures separately; do not hide them in an average.

### 6.6 Correction effectiveness

-   Percentage of identified issues resolved.
-   Percentage of corrections that introduce new failures.
-   Regression rate.
-   Number of correction cycles.
-   Percentage escalated appropriately.

### 6.7 End-to-end metrics

-   Task success rate.
-   Human acceptance rate.
-   User effort and interruption burden.
-   Time to acceptable result.
-   Output completeness.
-   Trust calibration: whether users understand what was and was not
    verified.

Cost metrics are intentionally excluded from this version and will be
defined in a separate cost model.

------------------------------------------------------------------------

## 7. Verification protocol by domain

### 7.1 Academic research

For each factual claim:

1.  Extract atomic proposition.
2.  Identify source requirements.
3.  Resolve source identity and metadata.
4.  Inspect relevant source passage.
5.  Determine whether the passage supports, contradicts or only
    partially supports the claim.
6.  Record source quality and limitations.
7.  Escalate inaccessible or ambiguous sources.

A DOI resolving successfully is not proof that the cited source supports
the claim.

### 7.2 Legal work

For each legal proposition:

1.  Identify jurisdiction.
2.  Identify the cited authority.
3.  Confirm existence through authoritative or licensed sources.
4.  Confirm relevant text and pinpoint.
5.  Check status and subsequent treatment where data is available.
6.  Compare the proposition with the authority.
7.  Flag uncertainty and require qualified human review where necessary.

The evaluation dataset must be reviewed by appropriately qualified legal
professionals. Do not use general model judgement as the sole legal
ground truth.

### 7.3 Software

1.  Convert requirements into acceptance tests.
2.  Run unit and integration tests.
3.  Run static analysis.
4.  Inspect dependency and vulnerability reports.
5.  Execute in a sandbox.
6.  Run security and regression tests appropriate to the scope.
7.  Record test environment and versions.

A passing test suite does not prove absence of vulnerabilities. Report
coverage and known limitations.

### 7.4 Creative and video work

1.  Convert brief into explicit visual, audio, narrative and delivery
    criteria.
2.  Inspect outputs at relevant temporal intervals and scenes.
3.  Compare scene continuity and required content.
4.  Check measurable technical properties.
5.  Use human review for subjective quality.
6.  Report criteria that could not be assessed reliably.

------------------------------------------------------------------------

## 8. Confidence calibration

Model confidence should not be accepted at face value.

For outputs that expose probability-like confidence:

-   Collect predictions and adjudicated outcomes.
-   Plot reliability diagrams.
-   Calculate Brier score where suitable.
-   Evaluate expected calibration error with documented binning.
-   Recalibrate on a separate calibration set.
-   Re-test on held-out data.
-   Monitor drift over time.

Do not force a probability onto qualitative verification outcomes when
the underlying evidence does not support one.

------------------------------------------------------------------------

## 9. Human adjudication

Human reviewers should assess a stratified sample of outputs and all
high-impact disagreements.

Review protocol:

-   Reviewers see the original task and reference criteria.
-   Reviewers do not see the system's overall score before independent
    assessment.
-   At least two reviewers assess a subset of ambiguous or high-risk
    cases.
-   Disagreements are resolved through a documented adjudication
    process.
-   Reviewer expertise must match the domain.
-   Inter-rater agreement is reported where appropriate.

------------------------------------------------------------------------

## 10. Initial acceptance gates

The first benchmark should establish baseline measurements before
setting ambitious thresholds. Proposed release gates:

1.  No loss or silent mutation of original user requirements.
2.  All mandatory requirements traceable to acceptance criteria.
3.  No critical tenant-isolation or data-exposure defects.
4.  No unbounded execution or correction loops.
5.  Verification reports distinguish contradicted from unverified
    claims.
6.  Critical requirements cannot be overridden by aggregate quality
    scores.
7.  False-positive and false-negative rates are reported.
8.  Full-platform treatment demonstrates statistically and practically
    meaningful improvement over at least one baseline on the
    pre-registered primary outcome.
9.  Performance is reported separately by domain and difficulty.
10. Human-review escalation works as designed.

Numerical thresholds should be set after pilot data is collected and
risk tolerance is agreed. Do not choose arbitrary targets and then
present them as validated.

------------------------------------------------------------------------

## 11. Experimental procedure

1.  Freeze the dataset version.
2.  Pre-register primary and secondary metrics.
3.  Select generation providers and configurations.
4.  Randomise case order where feasible.
5.  Run baseline A, baseline B and treatment C.
6.  Repeat stochastic cases.
7.  Preserve prompts, specifications, outputs and tool traces subject to
    privacy controls.
8.  Blind human reviewers to experimental condition where possible.
9.  Adjudicate disagreements.
10. Calculate metrics and confidence intervals.
11. Analyse by domain, difficulty and failure type.
12. Record limitations and unexpected behaviours.
13. Publish an internal benchmark report.

------------------------------------------------------------------------

## 12. Regression testing

Every material change to intent extraction, calibration, routing,
verification rules or correction logic should run a regression suite.

Regression categories:

-   Previously passing cases.
-   Previously failing cases.
-   Security and prompt-injection cases.
-   Cross-domain cases.
-   Long-context cases.
-   Provider-specific cases.
-   Cases involving ambiguous evidence.
-   Cases where no reliable verification is possible.

A change should not be released solely because aggregate score improved
if it causes a serious regression in a critical domain.

------------------------------------------------------------------------

## 13. Production monitoring

Monitor:

-   Task-stage failure rates.
-   Provider error rates.
-   Clarification abandonment.
-   Verification coverage.
-   Correction-loop frequency.
-   Human-review escalation.
-   User feedback.
-   Drift in model/provider behaviour.
-   Security events.

Do not use production customer content for general model training by
default. Apply data minimisation, access controls, retention rules and
the relevant legal basis.

------------------------------------------------------------------------

## 14. Reporting template

Every benchmark report should include:

1.  Dataset and version.
2.  Experimental conditions.
3.  Providers and configurations.
4.  Number of cases and repetitions.
5.  Primary metric and results.
6.  Secondary metrics.
7.  Results by domain and difficulty.
8.  False positives and false negatives.
9.  Human adjudication methodology.
10. Statistical uncertainty.
11. Failure examples.
12. Limitations.
13. Regression analysis.
14. Recommendation and unresolved risks.

------------------------------------------------------------------------

## 15. Research questions

The benchmark should specifically investigate:

-   Does explicit Intent Record construction improve requirement recall?
-   Does adaptive clarification improve outcomes enough to justify
    interruption?
-   Does calibration outperform simple prompt rewriting?
-   Which verification tasks benefit from deterministic methods?
-   How often do generator and verifier errors correlate?
-   Can evidence-linked claim verification reduce false reassurance?
-   Does a universal core generalise across domains, or does it require
    substantial domain-specific configuration?
-   Can the same task be routed across providers without losing intent
    fidelity?

The answers should determine the next architecture iteration.


---

# Implementation Backlog

## Universal AI Intelligence & Quality Assurance Platform

**Version:** 1.0\
**Status:** Proposed prototype plan\
**Dependency:** Core Technical Specification and Data/API Contracts\
**Cost modelling:** Deferred

------------------------------------------------------------------------

## 1. Delivery strategy

Build the smallest complete end-to-end workflow that proves the central
proposition. Avoid building a large platform shell before the intent,
calibration and assurance loop works.

The initial implementation should be a modular monolith with a web
interface, API, one provider adapter and a repeatable evaluation
harness.

### 1.1 Prototype sequence

1.  Repository and development foundation.
2.  Intent Record and schema validation.
3.  Intent extraction and ambiguity handling.
4.  Adaptive clarification.
5.  Prompt calibration and traceability.
6.  One provider integration.
7.  Output normalisation and storage.
8.  Independent assurance.
9.  Correction and re-verification.
10. Benchmarking across three initial domains.

------------------------------------------------------------------------

## 2. Suggested repository structure

``` text
universal-ai-platform/
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── apps/
│   ├── api/
│   └── web/
├── src/
│   └── platform_core/
│       ├── api/
│       ├── auth/
│       ├── context/
│       ├── intent/
│       ├── clarification/
│       ├── calibration/
│       ├── orchestration/
│       ├── providers/
│       ├── assurance/
│       ├── evidence/
│       ├── correction/
│       ├── reporting/
│       ├── evaluation/
│       ├── storage/
│       └── security/
├── domain_modules/
│   ├── academic/
│   ├── software/
│   └── creative/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── security/
│   └── evaluation/
├── evaluation_data/
│   ├── development/
│   ├── validation/
│   └── holdout/
└── docs/
```

This is a proposed structure. It may be simplified if the first
implementation is small.

------------------------------------------------------------------------

## 3. Backlog priorities

-   **P0:** Required to prove the MVP.
-   **P1:** Important follow-on capability.
-   **P2:** Later expansion.

Each item should become an independently testable engineering ticket.

------------------------------------------------------------------------

## 4. Epic A --- Foundation and developer experience

### A-001: Create repository and project skeleton

**Priority:** P0

Tasks: - Create source and test directories. - Configure Python project
and dependency management. - Add environment configuration. - Add
formatting, linting and type-checking. - Add CI pipeline. - Add
development documentation.

Acceptance: - A new developer can install dependencies and run tests
from documented instructions. - Secrets are not committed. - CI runs
formatting/lint and unit tests.

### A-002: Configure API application

**Priority:** P0

Tasks: - Create FastAPI application. - Add health endpoint. - Add
request ID middleware. - Add structured error handling. - Generate
OpenAPI documentation.

Acceptance: - Health endpoint returns expected status. - Invalid
payloads return a consistent error envelope. - Request IDs appear in
logs and responses.

### A-003: Configure database and migrations

**Priority:** P0

Tasks: - Configure PostgreSQL. - Add migration framework. - Create task
and user/owner tables. - Add versioned Intent Record storage. - Add test
database setup.

Acceptance: - Migrations can be applied and rolled back in
development. - Task and Intent Record data persist across application
restarts.

------------------------------------------------------------------------

## 5. Epic B --- Intent Record

### B-001: Implement Intent Record schema

**Priority:** P0

Tasks: - Define Pydantic models. - Define enums and validation. - Add
requirement provenance. - Add stable requirement IDs. - Add schema
version.

Acceptance: - Valid example records pass. - Missing or invalid fields
fail validation. - Inferred and assumed requirements require
provenance. - Mandatory requirements are not silently downgraded.

### B-002: Preserve source request

**Priority:** P0

Tasks: - Store original request text. - Store attachment references. -
Compute content hash. - Link source text spans to extracted requirements
where possible.

Acceptance: - Original request is retrievable. - Changes to
interpretation do not alter source content. - Hash mismatch is
detectable.

### B-003: Version Intent Records

**Priority:** P0

Tasks: - Implement immutable approved versions. - Create new versions
for approved changes. - Record supersession relationships. - Add history
retrieval.

Acceptance: - An approved version cannot be overwritten. - New versions
preserve history and traceability.

------------------------------------------------------------------------

## 6. Epic C --- Intent extraction and ambiguity

### C-001: Implement extraction service

**Priority:** P0

Tasks: - Define model prompt and structured output contract. - Extract
objective, domain, task type and deliverables. - Extract constraints,
preferences and exclusions. - Attach provenance. - Validate model output
against schema.

Acceptance: - Representative test prompts produce valid Intent
Records. - Invalid model output is rejected or safely repaired through
bounded validation. - Extraction errors are observable.

### C-002: Implement contradiction detection

**Priority:** P0

Tasks: - Add deterministic checks for explicit conflicts. - Add
model-assisted semantic conflict detection. - Store conflict pairs and
explanations. - Distinguish genuine contradiction from apparent
ambiguity.

Acceptance: - Known contradictory test cases are flagged. -
Non-conflicting paraphrases are not routinely flagged as conflicts.

### C-003: Implement uncertainty representation

**Priority:** P0

Tasks: - Store field-level confidence/uncertainty. - Distinguish model
confidence from empirically calibrated confidence. - Mark critical
unresolved fields.

Acceptance: - Critical uncertainty remains visible regardless of
aggregate confidence. - Uncalibrated values are labelled as estimates.

### C-004: Implement adaptive clarification

**Priority:** P0

Tasks: - Generate candidate questions. - Link each question to
unresolved requirements. - Assess materiality and risk. - Support
labelled assumptions and skipped questions. - Persist answers.

Acceptance: - Material questions are asked in benchmark cases. -
Immaterial missing preferences do not unnecessarily block execution. -
User answers create traceable Intent Record versions.

------------------------------------------------------------------------

## 7. Epic D --- Calibration engine

### D-001: Define execution specification schema

**Priority:** P0

Tasks: - Define instructions, constraints and exclusions. - Define
deliverables and acceptance criteria. - Add evidence requirements. - Add
unresolved assumptions. - Add source requirement links.

Acceptance: - Every mandatory requirement is represented in instructions
or acceptance criteria. - Every criterion links to one or more
requirement IDs.

### D-002: Generate calibrated specification

**Priority:** P0

Tasks: - Generate provider-neutral specification. - Avoid redundant
instructions. - Preserve original meaning. - Store engine version and
hash.

Acceptance: - Specification is valid against schema. - No mandatory
source requirement is omitted in the test suite. - Unauthorised
constraints are not introduced.

### D-003: Validate specification fidelity

**Priority:** P0

Tasks: - Compare requirements and exclusions. - Detect omissions and
changes. - Reject invalid specification. - Record validation results.

Acceptance: - Known omissions and changed requirements are detected. -
Valid specifications pass with traceable results.

------------------------------------------------------------------------

## 8. Epic E --- Execution orchestration

### E-001: Implement provider adapter interface

**Priority:** P0

Tasks: - Define execute, capabilities and health-check interface. -
Define normalised output envelope. - Define provider error mapping. -
Add adapter contract tests.

Acceptance: - A mock provider passes contract tests. - Provider-specific
response formats do not leak into core domain models.

### E-002: Integrate first external provider

**Priority:** P0

Tasks: - Select provider based on access, privacy, reliability and
supported features. - Implement adapter. - Secure API credentials. - Add
timeout and retry handling. - Capture provider request identifiers.

Acceptance: - A calibrated task can be submitted and a response
normalised. - Secrets are not exposed in logs or API responses. -
Failure states are persisted.

### E-003: Implement task state machine

**Priority:** P0

Tasks: - Define allowed transitions. - Persist transition history. - Add
bounded retries. - Support cancellation and failure. - Support
asynchronous execution.

Acceptance: - Invalid state transitions are rejected. - Worker restart
does not silently lose task state. - Duplicate requests do not create
duplicate execution.

------------------------------------------------------------------------

## 9. Epic F --- Assurance engine

### F-001: Implement requirement evaluator

**Priority:** P0

Tasks: - Evaluate output against acceptance criteria. - Store
criterion-level results. - Apply critical hard gates. - Record rationale
and limitations.

Acceptance: - A failed critical criterion prevents full-pass status. -
Aggregate quality cannot override a failed mandatory gate.

### F-002: Implement structural verification

**Priority:** P0

Tasks: - Validate required sections and formats. - Validate output
schema where applicable. - Validate file and artifact metadata.

Acceptance: - Missing mandatory sections and invalid structures are
detected.

### F-003: Implement basic claim extraction

**Priority:** P1

Tasks: - Extract candidate factual claims. - Preserve output location. -
Classify claim type. - Avoid treating opinion as fact.

Acceptance: - Claims are traceable to output spans. - Uncertain
extractions can be marked for review.

### F-004: Implement source verification

**Priority:** P1

Tasks: - Resolve source identity. - Retrieve source metadata where
permitted. - Compare source content to claim. - Store evidence and
retrieval timestamp. - Distinguish unsupported from contradicted.

Acceptance: - Nonexistent, inaccessible and non-supporting sources are
distinguished. - A source's existence alone does not mark a claim as
supported.

### F-005: Implement assurance report

**Priority:** P0

Tasks: - Summarise criterion results. - Summarise claim statuses where
available. - Report limitations and review items. - Distinguish partial
verification from full acceptance.

Acceptance: - Report accurately reflects underlying records. - No
unsupported accuracy guarantee is displayed.

------------------------------------------------------------------------

## 10. Epic G --- Correction and re-verification

### G-001: Create correction issues

**Priority:** P1

Tasks: - Convert failed checks into structured issues. - Link issues to
requirements and output locations. - Set severity and verification plan.

Acceptance: - Every correction issue identifies the failed criterion or
claim.

### G-002: Generate targeted correction instructions

**Priority:** P1

Tasks: - Send relevant issue context to execution provider. - Preserve
unaffected content where possible. - Track correction attempts.

Acceptance: - Correction instructions are limited to identified
failures. - The original Intent Record remains unchanged.

### G-003: Re-verify revised output

**Priority:** P1

Tasks: - Compare output versions. - Recheck affected criteria. - Re-run
critical global checks. - Detect regression.

Acceptance: - Previously passing critical criteria are rechecked. -
Regressions are reported. - Correction loops terminate after configured
limits.

------------------------------------------------------------------------

## 11. Epic H --- Evaluation framework

### H-001: Define benchmark case format

**Priority:** P0

Tasks: - Define dataset schema. - Add case metadata and expected
requirements. - Add planted issue annotations. - Add ground-truth source
references.

Acceptance: - Benchmark cases validate against schema. - Dataset version
is recorded in every run.

### H-002: Build initial benchmark set

**Priority:** P0

Tasks: - Create cases for academic, software and creative tasks. -
Include vague, contradictory, incomplete and adversarial requests. -
Create reference criteria. - Obtain independent review for ambiguous
cases.

Acceptance: - Cases have expected outcomes and adjudication notes. -
Holdout cases are not used to tune prompts.

### H-003: Implement baseline runner

**Priority:** P0

Tasks: - Run conventional prompt baseline. - Run prompt-optimisation
baseline. - Run full platform treatment. - Preserve configuration and
outputs.

Acceptance: - Runs are reproducible to the extent supported by provider
determinism. - Experimental condition is recorded.

### H-004: Calculate metrics and report

**Priority:** P0

Tasks: - Calculate requirement precision and recall. - Calculate
clarification metrics. - Calculate verification precision and recall. -
Calculate task success and correction outcomes. - Report by domain and
difficulty.

Acceptance: - False positives and false negatives are both reported. -
Results include dataset and configuration versions.

------------------------------------------------------------------------

## 12. Epic I --- Security and privacy

### I-001: Tenant and access boundaries

**Priority:** P0 before multi-user testing

Tasks: - Define ownership and organisation scopes. - Enforce access
checks. - Add row-level security if appropriate. - Test cross-tenant
access.

Acceptance: - Cross-tenant access tests fail safely.

### I-002: Secret management

**Priority:** P0

Tasks: - Store provider credentials securely. - Redact secrets from
logs. - Rotate keys. - Separate development and production credentials.

Acceptance: - Automated tests detect accidental secret exposure in known
logging paths.

### I-003: Prompt-injection controls

**Priority:** P1

Tasks: - Separate instructions from untrusted content. - Mark retrieved
and uploaded content as untrusted. - Prevent content from mutating
Intent Record or platform policy. - Add adversarial tests.

Acceptance: - Test documents cannot override system instructions or the
user's approved intent.

### I-004: Retention and deletion

**Priority:** P1 before production

Tasks: - Define retention policy. - Implement deletion workflow across
database and object storage. - Record deletion status. - Review backups
and provider-side retention.

Acceptance: - Deletion workflow covers all known storage locations and
reports exceptions.

------------------------------------------------------------------------

## 13. Epic J --- User interface

### J-001: Task submission

**Priority:** P0

Acceptance: - User can submit a natural-language request. - User can see
task creation status.

### J-002: Intent review

**Priority:** P0

Acceptance: - User can inspect objective, requirements, assumptions and
ambiguities. - User can correct the interpretation before execution.

### J-003: Clarification interaction

**Priority:** P0

Acceptance: - User can answer, skip or approve a safe assumption where
permitted. - Clarification history is visible.

### J-004: Execution and assurance view

**Priority:** P0

Acceptance: - User can see task stage. - User can distinguish passed,
failed, unverified and human-review items. - User can inspect the
assurance explanation.

### J-005: Correction approval

**Priority:** P1

Acceptance: - User can approve a correction cycle where required. -
Revised output and prior version can be compared.

------------------------------------------------------------------------

## 14. Cross-domain prototype scenarios

### Scenario 1 --- Academic research

Input: A broad request for a research paper with incomplete citation,
length and source requirements.

Expected demonstration: - Intent extraction. - Identification of
material missing details. - Adaptive clarification. - Source and
citation requirements in calibrated specification. - Claim-level source
checks. - Transparent unverified claims.

### Scenario 2 --- Software development

Input: A request to build a small application with incomplete functional
requirements.

Expected demonstration: - Requirement extraction. - Contradiction and
missing requirement detection. - Acceptance criteria. - Code execution
and tests. - Requirement-linked assurance. - Targeted correction.

### Scenario 3 --- AI video

Input: A creative brief for a short commercial with specified brand,
scene, character, audio and delivery constraints.

Expected demonstration: - Structured brief extraction. - Clarification
of material creative/technical ambiguity. - Output specification. -
Assessment of available visual/audio evidence. - Verification of
measurable constraints. - Human review for subjective quality.

The first prototype may assess a supplied video or storyboard rather
than generate video itself.

------------------------------------------------------------------------

## 15. Release gates

Do not declare the MVP complete until:

-   Original requests and approved Intent Records are preserved.
-   Mandatory requirements are traceable to acceptance criteria.
-   Clarification and assumptions are recorded.
-   At least one provider adapter works end-to-end.
-   Outputs are independently assessed.
-   Critical gates cannot be bypassed by aggregate scores.
-   Unverified and contradicted results are distinguished.
-   Correction attempts are bounded.
-   Benchmark baselines are available.
-   Security and tenant-isolation tests pass for the intended test
    scope.
-   Known limitations are documented.

------------------------------------------------------------------------

## 16. Suggested first sprint

The first sprint should not attempt the entire product.

1.  Create repository and project skeleton.
2.  Configure FastAPI and PostgreSQL.
3.  Implement task and Intent Record schemas.
4.  Persist original request and Intent Record versions.
5.  Add schema validation and unit tests.
6.  Create a simple API endpoint to submit a task and retrieve its
    Intent Record.
7.  Create a small labelled set of 20--30 intent extraction cases for
    development testing.

Sprint completion means the system can reliably store and retrieve a
validated, versioned Intent Record. It does not yet mean the platform
can execute or verify tasks.

------------------------------------------------------------------------

## 17. Deferred cost and capacity work

The following are intentionally out of scope for this backlog version:

-   Cloud infrastructure cost estimates.
-   Model token and inference cost estimates.
-   Cost per successful task.
-   Storage and media processing cost.
-   Provider pricing comparisons.
-   Subscription and margin modelling.
-   Capacity planning and production scale estimates.

These should be calculated after the architecture and representative
workload are sufficiently stable. Any future estimates must state
assumptions, workload profiles, provider pricing dates and uncertainty
ranges.
