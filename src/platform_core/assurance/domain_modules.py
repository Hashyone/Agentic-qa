from __future__ import annotations

import re
from typing import Protocol

from platform_core.assurance.models import VerificationStatus
from platform_core.intent.models import FrozenModel, IntentRecord, Requirement


class DomainModuleDescriptor(FrozenModel):
    module_id: str
    version: str
    supported_domains: tuple[str, ...]
    supported_task_types: tuple[str, ...]
    required_inputs: tuple[str, ...]
    checks: tuple[str, ...]
    output_fields: tuple[str, ...]


class DomainCheckResult(FrozenModel):
    status: VerificationStatus
    explanation: str
    review_required: bool = False


class DomainAssuranceModule(Protocol):
    descriptor: DomainModuleDescriptor

    def evaluate(
        self, intent: IntentRecord, method: str, output: str
    ) -> DomainCheckResult | None:
        """Return a result for a recognized method, or None if it is not owned."""


class SoftwareTestPlanModule:
    descriptor = DomainModuleDescriptor(
        module_id="software-test-plan",
        version="0.1.0",
        supported_domains=("software",),
        supported_task_types=("test_plan",),
        required_inputs=(
            "intent.task.domain",
            "intent.task.task_type",
            "intent.requirements",
            "acceptance_criterion.verification_method",
            "output.text",
        ),
        checks=(
            "software_test_case_table:<requested-header>|...; standard "
            "test-case fields and mandatory-requirement coverage also apply",
        ),
        output_fields=("status", "explanation"),
    )
    _method_prefix = "software_test_case_table:"

    def evaluate(
        self, intent: IntentRecord, method: str, output: str
    ) -> DomainCheckResult | None:
        if not method.startswith(self._method_prefix):
            return None
        if (
            intent.task.domain.casefold() not in self.descriptor.supported_domains
            or intent.task.task_type.casefold()
            not in self.descriptor.supported_task_types
        ):
            return DomainCheckResult(
                status=VerificationStatus.UNAVAILABLE,
                explanation=(
                    "The software test-plan check is unavailable for task "
                    f"{intent.task.domain}/{intent.task.task_type}."
                ),
            )

        requested_headers = tuple(
            _normalize_header(item)
            for item in method.removeprefix(self._method_prefix).split("|")
            if item.strip()
        )
        if len(requested_headers) < 2:
            return DomainCheckResult(
                status=VerificationStatus.UNAVAILABLE,
                explanation=(
                    "The software test-case check needs at least two explicit "
                    "pipe-separated column names."
                ),
            )

        mandatory_requirements = tuple(
            requirement
            for requirement in intent.requirements
            if requirement.priority.value == "mandatory"
        )
        if not mandatory_requirements:
            return DomainCheckResult(
                status=VerificationStatus.UNAVAILABLE,
                explanation=(
                    "Test-plan completeness cannot be checked because the "
                    "Intent Record has no mandatory requirements."
                ),
            )
        behavior_requirements = tuple(
            requirement
            for requirement in mandatory_requirements
            if not _is_test_plan_format_requirement(requirement)
        )
        if not behavior_requirements:
            return DomainCheckResult(
                status=VerificationStatus.UNAVAILABLE,
                explanation=(
                    "Test-plan completeness cannot be checked because the "
                    "Intent Record has no mandatory software-behavior requirements."
                ),
            )
        required_headers = tuple(
            dict.fromkeys(
                (
                    "test id",
                    "requirement ids",
                    "scenario",
                    "steps",
                    "expected result",
                    *requested_headers,
                )
            )
        )
        return _evaluate_test_case_tables(
            output,
            required_headers=required_headers,
            known_requirement_ids={
                requirement.requirement_id for requirement in intent.requirements
            },
            mandatory_requirement_ids={
                requirement.requirement_id for requirement in behavior_requirements
            },
        )


def _evaluate_test_case_tables(
    output: str,
    *,
    required_headers: tuple[str, ...],
    known_requirement_ids: set[str],
    mandatory_requirement_ids: set[str],
) -> DomainCheckResult:
    tables = _markdown_tables(output)
    matching_tables = tuple(
        (headers, rows)
        for headers, rows in tables
        if all(header in headers for header in required_headers)
    )
    if not matching_tables:
        missing_headers = ", ".join(required_headers)
        return DomainCheckResult(
            status=VerificationStatus.CONTRADICTED,
            explanation=(
                "No Markdown test-case table contains all required columns: "
                f"{missing_headers}."
            ),
        )

    errors: list[str] = []
    for headers, rows in matching_tables:
        if len(headers) != len(set(headers)):
            errors.append("A test-case table contains duplicate column names.")
            continue
        if not rows:
            errors.append("A test-case table has no test cases.")
            continue

        indexes = {header: headers.index(header) for header in required_headers}
        seen_test_ids: set[str] = set()
        covered_mandatory_ids: set[str] = set()
        table_errors: list[str] = []
        for row_number, row in enumerate(rows, start=1):
            if len(row) != len(headers):
                table_errors.append(f"Test case row {row_number} has the wrong number of cells.")
                continue
            if any(not row[indexes[header]] for header in required_headers):
                table_errors.append(
                    f"Test case row {row_number} is missing a required field."
                )
                continue

            test_id = row[indexes["test id"]].strip().casefold()
            if test_id in seen_test_ids:
                table_errors.append(f"Test ID {test_id} is duplicated.")
            seen_test_ids.add(test_id)

            linked_ids = tuple(
                token
                for token in re.split(
                    r"[,;\s]+", row[indexes["requirement ids"]].strip()
                )
                if token
            )
            if not linked_ids:
                table_errors.append(f"Test case row {row_number} links no requirements.")
                continue
            unknown_ids = set(linked_ids) - known_requirement_ids
            if unknown_ids:
                table_errors.append(
                    f"Test case row {row_number} references unknown requirements: "
                    + ", ".join(sorted(unknown_ids))
                    + "."
                )
            covered_mandatory_ids.update(set(linked_ids) & mandatory_requirement_ids)

        uncovered_ids = mandatory_requirement_ids - covered_mandatory_ids
        if uncovered_ids:
            table_errors.append(
                "Mandatory requirements have no test case: "
                + ", ".join(sorted(uncovered_ids))
                + "."
            )
        if not table_errors:
            return DomainCheckResult(
                status=VerificationStatus.PARTIALLY_SUPPORTED,
                explanation=(
                    "Required fields, unique test IDs, valid requirement links, "
                    "and mandatory-requirement coverage passed. Human review is "
                    "still required to determine whether steps and expected "
                    "results are semantically correct."
                ),
                review_required=True,
            )
        errors.extend(table_errors)

    return DomainCheckResult(
        status=VerificationStatus.CONTRADICTED,
        explanation=" ".join(errors),
    )


def _markdown_tables(output: str) -> tuple[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]], ...]:
    lines = output.splitlines()
    tables: list[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = []
    index = 0
    while index < len(lines) - 1:
        if "|" not in lines[index] or not _is_separator_row(lines[index + 1]):
            index += 1
            continue
        headers = tuple(_normalize_header(cell) for cell in _split_table_row(lines[index]))
        separator = _split_table_row(lines[index + 1])
        if len(headers) != len(separator):
            index += 1
            continue
        rows: list[tuple[str, ...]] = []
        index += 2
        while index < len(lines) and "|" in lines[index]:
            rows.append(_split_table_row(lines[index]))
            index += 1
        tables.append((headers, tuple(rows)))
    return tuple(tables)


def _split_table_row(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))


def _is_separator_row(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().strip("`*_ ").casefold().split())


def _is_test_plan_format_requirement(requirement: Requirement) -> bool:
    category = requirement.category.casefold().replace("-", "_").replace(" ", "_")
    if category in {"format", "formatting", "output_format", "table"}:
        return True
    text = requirement.text.casefold()
    return "table" in text and any(
        term in text for term in ("column", "header", "markdown", "format")
    )


DEFAULT_DOMAIN_MODULES: tuple[DomainAssuranceModule, ...] = (
    SoftwareTestPlanModule(),
)