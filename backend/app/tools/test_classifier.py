#!/usr/bin/env python3
"""
Intent classifier accuracy test runner.

Usage (from repo root):
    python -m backend.app.tools.test_classifier

Or directly:
    cd backend && python -m app.tools.test_classifier
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))

from app.core.classifier import (
    INTENTS_DATA,
    load_intent_data,
    load_model,
    classify_intent,
)

TEST_FILE = ROOT / "data" / "test_queries.json"


def _color(text: str, code: int) -> str:
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _color(t, 32)


def red(t: str) -> str:
    return _color(t, 31)


def yellow(t: str) -> str:
    return _color(t, 33)


def bold(t: str) -> str:
    return _color(t, 1)


def run_tests() -> None:
    print(bold("=" * 60))
    print(bold("  AÇÜ Chatbot — Intent Classifier Accuracy Test"))
    print(bold("=" * 60))

    load_model()
    load_intent_data()

    if not INTENTS_DATA:
        print(red("ERROR: No intents loaded. Aborting."))
        sys.exit(1)

    with open(TEST_FILE, "r", encoding="utf-8") as f:
        test_cases: list[dict] = json.load(f)

    print(f"\nLoaded {len(test_cases)} test queries, {len(INTENTS_DATA)} intents.\n")

    correct = 0
    wrong = 0
    unmatched = 0
    errors_by_intent: dict[str, list] = defaultdict(list)
    times: list[float] = []

    for tc in test_cases:
        query = tc["query"]
        expected = tc["expected"]

        t0 = time.perf_counter()
        result = classify_intent(query)
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)

        predicted = result["intent_name"] if result else None

        if predicted == expected:
            correct += 1
            status = green("OK")
        elif predicted is None:
            unmatched += 1
            status = yellow("MISS")
            errors_by_intent[expected].append((query, "NONE"))
        else:
            wrong += 1
            status = red("WRONG")
            errors_by_intent[expected].append((query, predicted))

        print(f"  [{status}] \"{query}\"")
        if predicted != expected:
            print(f"         expected={expected}, got={predicted}")

    total = len(test_cases)
    accuracy = correct / total * 100 if total else 0
    avg_ms = sum(times) / len(times) if times else 0

    print(bold("\n" + "=" * 60))
    print(bold("  RESULTS"))
    print(bold("=" * 60))
    print(f"  Total:     {total}")
    print(f"  Correct:   {green(str(correct))}")
    print(f"  Wrong:     {red(str(wrong))}")
    print(f"  Unmatched: {yellow(str(unmatched))}")
    print(f"  Accuracy:  {bold(f'{accuracy:.1f}%')}")
    print(f"  Avg time:  {avg_ms:.1f} ms/query")

    if errors_by_intent:
        print(bold("\n  FAILURES BY INTENT:"))
        for intent, failures in sorted(errors_by_intent.items()):
            print(f"    {intent}:")
            for query, got in failures:
                print(f"      - \"{query}\" → {got}")

    print()
    sys.exit(0 if accuracy >= 80 else 1)


if __name__ == "__main__":
    run_tests()
