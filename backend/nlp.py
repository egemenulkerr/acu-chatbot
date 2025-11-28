from __future__ import annotations

import re
from typing import Iterable, List

WHITESPACE_RE = re.compile(r"\s+")
PUNCTUATION_RE = re.compile(r"[^\wçğıöşüÇĞİÖŞÜ]+", re.UNICODE)


def normalize_text(text: str) -> str:
    """
    Basic Turkish-friendly normalization for lightweight intent matching.

    - Lowercases text using str.casefold (better for Turkish)
    - Strips punctuation except Turkish characters
    - Collapses repeated whitespace
    """
    lowered = text.casefold()
    no_punct = PUNCTUATION_RE.sub(" ", lowered)
    normalized = WHITESPACE_RE.sub(" ", no_punct).strip()
    return normalized


def tokenize(text: str) -> List[str]:
    """Tokenize normalized text into words."""
    normalized = normalize_text(text)
    return normalized.split()


def normalize_examples(examples: Iterable[str]) -> List[str]:
    """Normalize an iterable of example sentences."""
    return [normalize_text(example) for example in examples]
