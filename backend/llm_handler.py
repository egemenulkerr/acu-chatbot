from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .classifier import IntentClassifier
from .gemini_client import GeminiClient


@dataclass
class LLMResult:
    intent: Optional[str]
    confidence: float
    response: str


class LLMHandler:
    """
    Thin abstraction over the intent classifier.

    This class is intentionally simple for now; the `generate_reply` method is
    the seam where a real LLM or third-party API could be integrated later.
    """

    def __init__(self, classifier: IntentClassifier, gemini_client: Optional[GeminiClient] = None) -> None:
        self._classifier = classifier
        self._gemini_client = gemini_client

    def generate_reply(self, message: str) -> LLMResult:
        intent, confidence = self._classifier.predict(message)
        intent_name = intent.name if intent else None

        if self._gemini_client:
            try:
                response = self._gemini_client.generate(message)
                return LLMResult(
                    intent=intent_name,
                    confidence=confidence,
                    response=response,
                )
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning(
                    "Gemini yanıtı alınamadı, sınıflandırıcıya düşülüyor: %s",
                    exc,
                )

        fallback = self._classifier.sample_response(intent)
        return LLMResult(
            intent=intent_name,
            confidence=confidence,
            response=fallback,
        )
