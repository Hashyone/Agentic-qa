import json
from datetime import datetime, timezone
from io import BytesIO

import pytest

from platform_core.intent.extraction import IntentExtractionError
from platform_core.intent.models import SourceRequest
from platform_core.providers.deepseek import DeepSeekIntentExtractor


def _provider_response(content: dict) -> bytes:
    return json.dumps(
        {
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        }
    ).encode("utf-8")


def _valid_payload() -> dict:
    return {
        "objective": "Build a timer",
        "domain": "software",
        "task_type": "application",
        "requirements": [
            {
                "text": "Show elapsed time",
                "category": "functionality",
                "priority": "mandatory",
                "provenance": "explicit",
                "source_location": "source_request.text",
            }
        ],
    }


def test_extractor_sends_json_request_and_validates_provider_response(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return BytesIO(_provider_response(_valid_payload()))

    monkeypatch.setattr("platform_core.providers.deepseek.urlopen", fake_urlopen)
    extractor = DeepSeekIntentExtractor(api_key="test-key")

    payload = extractor.extract(
        SourceRequest(
            text="Build a timer that shows elapsed time",
            received_at=datetime.now(timezone.utc),
        )
    )

    assert payload.objective == "Build a timer"
    assert payload.requirements[0].text == "Show elapsed time"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert "must never be mandatory" in captured["body"]["messages"][0]["content"]
    assert "do not split one stated requirement" in captured["body"]["messages"][0]["content"]
    assert "typical domain conventions" in captured["body"]["messages"][0]["content"]
    assert "broad work area (not the subject matter)" in captured["body"]["messages"][0]["content"]
    assert "Do not copy the full request or its topic explanation into objective" in captured["body"]["messages"][0]["content"]
    assert "could materially change the result" in captured["body"]["messages"][0]["content"]
    assert "Keep a compound topic or scope as one requirement" in captured["body"]["messages"][0]["content"]
    assert "research_writing" in captured["body"]["messages"][0]["content"]
    assert "missing citation style, target length" in captured["body"]["messages"][0]["content"]
    assert "The objective is only a summary: it never replaces explicit requirements" in captured["body"]["messages"][0]["content"]
    assert "record that missing input as a material ambiguity" in captured["body"]["messages"][0]["content"]
    assert "source content, not merely citation metadata" in captured["body"]["messages"][0]["content"]
    assert "evidence_requirements describe what evidence to inspect" in captured["body"]["messages"][0]["content"]
    assert "never copy a source quote into that field" in captured["body"]["messages"][0]["content"]
    assert "software_test_case_table" in captured["body"]["messages"][0]["content"]
    assert "Do not infer a test-case table" in captured["body"]["messages"][0]["content"]
    assert '"Requirement IDs", "Scenario", "Steps"' in captured["body"]["messages"][0]["content"]
    assert '"section_present:<Markdown heading>"' in captured["body"]["messages"][0]["content"]
    assert "Never invent method" in captured["body"]["messages"][0]["content"]
    assert json.loads(captured["body"]["messages"][1]["content"])[
        "source_request"
    ] == "Build a timer that shows elapsed time"
    assert json.loads(captured["body"]["messages"][1]["content"])["attachments"] == []
    assert captured["timeout"] == 30
    assert extractor.last_usage.provider_requests == 1
    assert extractor.last_usage.input_tokens == 12
    assert extractor.last_usage.output_tokens == 8
    assert extractor.last_usage.total_tokens == 20
    assert extractor.last_usage.token_usage_complete
    assert extractor.last_usage.elapsed_seconds >= 0


def test_extractor_rejects_invalid_provider_payload(monkeypatch):
    response = _provider_response({"objective": "missing required fields"})
    monkeypatch.setattr(
        "platform_core.providers.deepseek.urlopen", lambda *args, **kwargs: BytesIO(response)
    )
    extractor = DeepSeekIntentExtractor(api_key="test-key")

    with pytest.raises(IntentExtractionError, match="invalid intent payload"):
        extractor.extract(
            SourceRequest(text="Do something", received_at=datetime.now(timezone.utc))
        )


def test_extractor_retries_once_after_invalid_payload(monkeypatch):
    responses = iter(
        [
            _provider_response({"objective": "missing required fields"}),
            _provider_response(_valid_payload()),
        ]
    )
    calls = 0

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        return BytesIO(next(responses))

    monkeypatch.setattr("platform_core.providers.deepseek.urlopen", fake_urlopen)
    extractor = DeepSeekIntentExtractor(api_key="test-key")

    payload = extractor.extract(
        SourceRequest(text="Build a timer", received_at=datetime.now(timezone.utc))
    )

    assert payload.objective == "Build a timer"
    assert calls == 2
    assert extractor.last_usage.provider_requests == 2
    assert extractor.last_usage.input_tokens == 24
    assert extractor.last_usage.output_tokens == 16
    assert extractor.last_usage.total_tokens == 40


def test_extractor_marks_token_usage_incomplete_when_provider_omits_it(monkeypatch):
    response = json.dumps(
        {"choices": [{"message": {"content": json.dumps(_valid_payload())}}]}
    ).encode("utf-8")
    monkeypatch.setattr(
        "platform_core.providers.deepseek.urlopen",
        lambda *args, **kwargs: BytesIO(response),
    )
    extractor = DeepSeekIntentExtractor(api_key="test-key")

    extractor.extract(
        SourceRequest(text="Build a timer", received_at=datetime.now(timezone.utc))
    )

    assert extractor.last_usage.provider_requests == 1
    assert extractor.last_usage.input_tokens is None
    assert extractor.last_usage.output_tokens is None
    assert extractor.last_usage.total_tokens is None
    assert not extractor.last_usage.token_usage_complete