from platform_core.evaluation.api_cases import parse_api_test_cases
from platform_core.evaluation.run_value_pilot import (
    _check_suite_contract,
    _token_totals,
)


def _suite():
    return parse_api_test_cases(
        '''{"cases":[
          {"case_id":"TC-1","requirement_ids":["ORACLE-001"],"scenario":"Accept nonblank input","operation":"create_task","input_text":"Pilot task","expected_status_code":201,"expected_task_status":"received","expected_source_request":"Pilot task","expected_error_detail":null},
          {"case_id":"TC-2","requirement_ids":["ORACLE-002"],"scenario":"Reject whitespace input","operation":"create_task","input_text":"   ","expected_status_code":422,"expected_task_status":null,"expected_source_request":null,"expected_error_detail":"input.text must not be blank"}
        ]}'''
    )


def _behaviors():
    return [
        {
            "oracle_requirement_id": "ORACLE-001",
            "input_text": "Pilot task",
            "expected_status_code": 201,
            "expected_task_status": "received",
            "expected_source_request": "Pilot task",
        },
        {
            "oracle_requirement_id": "ORACLE-002",
            "input_text": "   ",
            "expected_status_code": 422,
            "expected_error_detail": "input.text must not be blank",
        },
    ]


def test_frozen_oracle_accepts_exact_cases_and_links():
    result = _check_suite_contract(
        _suite(),
        _behaviors(),
        known_requirement_ids={"ORACLE-001", "ORACLE-002"},
        require_oracle_ids=True,
    )

    assert result == {"valid": True, "errors": []}


def test_frozen_oracle_rejects_wrong_expected_result_and_requirement_link():
    suite = _suite()
    wrong_case = suite.cases[0].model_copy(
        update={
            "requirement_ids": ("ORACLE-002",),
            "expected_status_code": 422,
            "expected_task_status": None,
            "expected_source_request": None,
            "expected_error_detail": "input.text must not be blank",
        }
    )
    result = _check_suite_contract(
        suite.model_copy(update={"cases": (wrong_case, suite.cases[1])}),
        _behaviors(),
        known_requirement_ids={"ORACLE-001", "ORACLE-002"},
        require_oracle_ids=True,
    )

    assert not result["valid"]
    assert any("does not link" in item for item in result["errors"])
    assert any("incorrect expected_status_code" in item for item in result["errors"])


def test_token_totals_are_withheld_when_any_call_usage_is_incomplete():
    totals = _token_totals(
        [
            {
                "provider_requests": 1,
                "input_tokens": 30,
                "output_tokens": 10,
                "total_tokens": 40,
                "token_usage_complete": True,
            },
            {
                "input_tokens": None,
                "output_tokens": 8,
                "total_tokens": None,
                "token_usage_complete": False,
            },
        ]
    )

    assert totals["provider_request_count"] == 2
    assert not totals["all_call_usage_complete"]
    assert totals["total_tokens"] is None