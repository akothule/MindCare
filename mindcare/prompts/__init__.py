"""Prompt assets. Edit `system.txt` to change the LLM system prompt."""

from functools import lru_cache
from pathlib import Path

_SYSTEM_FILE = Path(__file__).resolve().parent / "system.txt"
_CLASSIFIER_SYSTEM_FILE = Path(__file__).resolve().parent / "classifier_system.txt"


@lru_cache
def load_system_prompt() -> str:
    if not _SYSTEM_FILE.is_file():
        raise RuntimeError(f"System prompt file missing: {_SYSTEM_FILE}")
    text = _SYSTEM_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"System prompt file is empty: {_SYSTEM_FILE}")
    return text


@lru_cache
def load_classifier_system_prompt() -> str:
    if not _CLASSIFIER_SYSTEM_FILE.is_file():
        raise RuntimeError(f"Classifier system prompt missing: {_CLASSIFIER_SYSTEM_FILE}")
    text = _CLASSIFIER_SYSTEM_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Classifier system prompt is empty: {_CLASSIFIER_SYSTEM_FILE}")
    return text
