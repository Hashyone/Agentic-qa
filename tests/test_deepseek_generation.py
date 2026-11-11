import json
from io import BytesIO

import pytest

from platform_core.providers.generation import (
    DeepSeekTextGenerator,
    TextGenerationError,
)


def test_text_generator_sends_calibrated_prompt_and_returns_usage(monkeypatch):
    captured = {}
    envelope = {
        "choices": [{"message": {"content": "Generated result"}}],
        "usage": {
            "prompt_tokens": 30,
            "completion_tokens": 10,
            "total_tokens": 40,
        },
    }

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return BytesIO(json.dumps(envelope).encode())

    monkeypatch.setattr("platform_core.providers.generation.urlopen", fake_urlopen)
    generator = DeepSeekTextGenerator(api_key="test-key", timeout=17)

    result = generator.generate("Traceable calibrated prompt")

    assert result.text == "Generated result"
    assert result.provider == "deepseek"
    assert result.model == "deepseek-chat"
    assert result.input_tokens == 30
    assert result.output_tokens == 10
    assert result.total_tokens == 40
    assert result.token_usage_complete
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["messages"][1]["content"] == "Traceable calibrated prompt"
    assert captured["timeout"] == 17


def test_text_generator_reports_missing_usage_as_incomplete(monkeypatch):
    response = {"choices": [{"message": {"content": "Generated result"}}]}
    monkeypatch.setattr(
        "platform_core.providers.generation.urlopen",
        lambda *args, **kwargs: BytesIO(json.dumps(response).encode()),
    )

    result = DeepSeekTextGenerator(api_key="test-key").generate("Prompt")

    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.total_tokens is None
    assert not result.token_usage_complete


def test_text_generator_rejects_empty_and_malformed_outputs(monkeypatch):
    generator = DeepSeekTextGenerator(api_key="test-key")
    with pytest.raises(ValueError, match="must not be blank"):
        generator.generate("  ")

    monkeypatch.setattr(
        "platform_core.providers.generation.urlopen",
        lambda *args, **kwargs: BytesIO(b"not-json"),
    )
    with pytest.raises(TextGenerationError, match="generation failed"):
        generator.generate("Prompt")