from __future__ import annotations

from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_VIOLENCE: HarmBlockThreshold.BLOCK_NONE,
}


class GeminiClient:
    def __init__(self, api_key: str, model_name: str) -> None:
        if not api_key:
            raise ValueError("Google API anahtarı bulunamadı.")

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name=model_name)

    def generate(self, message: str) -> str:
        response = self._model.generate_content(
            message,
            safety_settings=SAFETY_SETTINGS,
        )

        text = self._extract_text(response)
        if not text:
            raise RuntimeError("Gemini boş yanıt döndürdü.")
        return text

    @staticmethod
    def _extract_text(response) -> Optional[str]:
        """
        Response.text çoğu durumda yeterli olsa da,
        gerekirse aday parçalarını birleştir.
        """
        if getattr(response, "text", None):
            return response.text.strip()

        candidates = getattr(response, "candidates", None)
        if not candidates:
            return None

        for candidate in candidates:
            parts = getattr(candidate, "content", None)
            if not parts:
                continue
            raw_parts = getattr(parts, "parts", [])
            texts = [
                getattr(part, "text", "")
                for part in raw_parts
                if getattr(part, "text", "")
            ]
            if texts:
                return "\n".join(texts).strip()
        return None

