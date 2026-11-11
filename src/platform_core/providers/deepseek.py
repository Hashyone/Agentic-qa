from __future__ import annotations

import json
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from platform_core.intent.extraction import (
    ExtractionTelemetry,
    INTENT_EXTRACTION_INSTRUCTIONS,
    IntentExtractionError,
    IntentExtractionPayload,
)
from platform_core.intent.models import SourceRequest


class DeepSeekIntentExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: float = 30,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API key must not be blank")
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._timeout = timeout
        self.last_usage = ExtractionTelemetry(
            elapsed_seconds=0,
            provider_requests=0,
            token_usage_complete=False,
        )
        self._usage_state: dict[str, int | bool | None] = {}

    def extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        started = perf_counter()
        self._usage_state = {
            "provider_requests": 0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "token_usage_complete": True,
        }
        try:
            return self._extract(source_request)
        finally:
            input_tokens = self._usage_state["input_tokens"]
            output_tokens = self._usage_state["output_tokens"]
            total_tokens = self._usage_state["total_tokens"]
            if (
                total_tokens is None
                and input_tokens is not None
                and output_tokens is not None
            ):
                total_tokens = input_tokens + output_tokens
            self.last_usage = ExtractionTelemetry(
                elapsed_seconds=perf_counter() - started,
                provider_requests=int(self._usage_state["provider_requests"] or 0),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                token_usage_complete=bool(
                    self._usage_state["token_usage_complete"]
                    and self._usage_state["provider_requests"]
                ),
            )

    def _extract(self, source_request: SourceRequest) -> IntentExtractionPayload:
        schema = json.dumps(IntentExtractionPayload.model_json_schema())
        system_message = (
            f"{INTENT_EXTRACTION_INSTRUCTIONS}\n"
            "Return only a JSON object matching this schema:\n"
            f"{schema}"
        )
        request_body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "source_request": source_request.text,
                                "attachments": list(source_request.attachments),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
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

        for attempt in range(2):
            self._usage_state["provider_requests"] = (
                int(self._usage_state["provider_requests"] or 0) + 1
            )
            try:
                with urlopen(request, timeout=self._timeout) as response:
                    envelope = json.loads(response.read())
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                self._usage_state["token_usage_complete"] = False
                raise IntentExtractionError("DeepSeek request failed") from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                self._usage_state["token_usage_complete"] = False
                if attempt == 0:
                    continue
                raise IntentExtractionError("DeepSeek returned invalid JSON") from error

            if isinstance(envelope, dict):
                self._capture_usage(envelope)
            else:
                self._usage_state["token_usage_complete"] = False


            try:
                content = envelope["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError("response content must be a string")
                return IntentExtractionPayload.model_validate_json(content)
            except (KeyError, IndexError, TypeError, ValidationError) as error:
                if attempt == 0:
                    continue
                raise IntentExtractionError(
                    "DeepSeek returned an invalid intent payload"
                ) from error

        raise IntentExtractionError("DeepSeek returned an invalid intent payload")

    def _capture_usage(self, envelope: dict) -> None:
        usage = envelope.get("usage")
        if not isinstance(usage, dict):
            self._usage_state["token_usage_complete"] = False
            return
        for field, provider_field in (
            ("input_tokens", "prompt_tokens"),
            ("output_tokens", "completion_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            value = usage.get(provider_field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                current = self._usage_state[field]
                self._usage_state[field] = (int(current) if current is not None else 0) + value
            else:
                self._usage_state["token_usage_complete"] = False