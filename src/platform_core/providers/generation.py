from __future__ import annotations

import json
from time import perf_counter
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import Field

from platform_core.intent.models import FrozenModel


class TextGenerationError(Exception):
    """Raised when a provider cannot generate a usable text output."""


class TextGenerationResult(FrozenModel):
    text: str = Field(min_length=1)
    provider: str
    model: str
    elapsed_seconds: float = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    token_usage_complete: bool = False


class TextGenerator(Protocol):
    def generate(self, prompt_text: str) -> TextGenerationResult:
        """Generate text from a calibrated prompt."""


class DeepSeekTextGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: float = 60,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API key must not be blank")
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._timeout = timeout

    def generate(self, prompt_text: str) -> TextGenerationResult:
        if not prompt_text.strip():
            raise ValueError("calibrated prompt must not be blank")
        started = perf_counter()
        request_body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Execute the calibrated task and produce its requested "
                            "deliverable. Do not claim that you independently "
                            "verified facts or ran tests unless you actually did."
                        ),
                    },
                    {"role": "user", "content": prompt_text},
                ],
            }
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=request_body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                envelope = json.loads(response.read())
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TextGenerationError("DeepSeek returned an empty output")
        except TextGenerationError:
            raise
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise TextGenerationError("DeepSeek generation failed") from error

        usage = envelope.get("usage", {})
        input_tokens = _nonnegative_int(usage.get("prompt_tokens"))
        output_tokens = _nonnegative_int(usage.get("completion_tokens"))
        total_tokens = _nonnegative_int(usage.get("total_tokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return TextGenerationResult(
            text=content.strip(),
            provider="deepseek",
            model=self._model,
            elapsed_seconds=perf_counter() - started,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            token_usage_complete=input_tokens is not None and output_tokens is not None,
        )


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None