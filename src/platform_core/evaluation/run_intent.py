from __future__ import annotations

import os

from dotenv import load_dotenv

from platform_core.evaluation.intent_dataset import (
    EvaluationRunMetadata,
    evaluate_intent_dataset,
    load_development_dataset,
)
from platform_core.intent.extraction import INTENT_EXTRACTION_PROMPT_VERSION
from platform_core.providers.deepseek import DeepSeekIntentExtractor


def main() -> None:
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required to run live intent evaluation")

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    extractor = DeepSeekIntentExtractor(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=model,
    )
    report = evaluate_intent_dataset(
        load_development_dataset(),
        extractor,
        run_metadata=EvaluationRunMetadata(
            provider="deepseek",
            model=model,
            adapter_version="0.1.0",
            prompt_version=INTENT_EXTRACTION_PROMPT_VERSION,
        ),
    )
    print(report.model_dump_json(indent=2))
    if report.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
