from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import nlp


@dataclass
class Intent:
    name: str
    examples: List[str]
    responses: List[str]


class IntentClassifier:
    """
    Ultra-lightweight intent matcher.

    This is *not* a production-grade classifier but it allows the frontend to
    exercise the entire pipeline without an external LLM dependency.
    """

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        data = self._load_data()
        self.language = data.get("language", "tr")
        self.fallback_responses = data.get("fallbackResponses", [])
        self.intents = [
            Intent(intent["name"], intent["examples"], intent["responses"])
            for intent in data.get("intents", [])
        ]

    def _load_data(self) -> Dict:
        with self._data_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def _score(self, message_tokens: List[str], example: str) -> float:
        example_tokens = nlp.tokenize(example)
        if not example_tokens:
            return 0.0

        overlap = len(set(message_tokens) & set(example_tokens))
        return overlap / len(example_tokens)

    def predict(self, message: str) -> Tuple[Optional[Intent], float]:
        normalized_message = nlp.normalize_text(message)
        tokens = normalized_message.split()

        best_intent: Optional[Intent] = None
        best_score = 0.0

        for intent in self.intents:
            intent_score = max((self._score(tokens, example) for example in intent.examples), default=0.0)
            if intent_score > best_score:
                best_score = intent_score
                best_intent = intent

        return best_intent, best_score

    def sample_response(self, intent: Optional[Intent]) -> str:
        if intent and intent.responses:
            return random.choice(intent.responses)

        if self.fallback_responses:
            return random.choice(self.fallback_responses)

        return "Şu anda yardımcı olamıyorum ancak yakında tekrar deneyebilirsiniz."
