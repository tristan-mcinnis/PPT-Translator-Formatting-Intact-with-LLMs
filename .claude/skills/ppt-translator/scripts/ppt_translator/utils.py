"""Utility helpers for CLI, filesystem handling and language detection."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator

# Script detection patterns keyed by ISO 639-1 / BCP-47 source language code.
# Only text containing characters from the source language's script is sent to
# the LLM, so already-translated (e.g. English) slide text is left untouched.
_SCRIPT_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    # Simplified + Traditional Chinese, incl. supplementary-plane extension B-F
    "zh": re.compile(
        r"[\u4E00-\u9FFF\u3400-\u4DBF\U00020000-\U0002A6DF\U0002A700-\U0002B73F"
        r"\U0002B740-\U0002B81F\U0002B820-\U0002CEAF\u2F00-\u2FDF\u3000-\u303F]"
    ),
    # Japanese: kana + CJK
    "ja": re.compile(r"[\u3040-\u30FF\u31F0-\u31FF\u4E00-\u9FFF\u3400-\u4DBF]"),
    # Korean: Hangul
    "ko": re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\uA960-\uA97F\uD7B0-\uD7FF]"),
    # Cyrillic scripts
    "ru": re.compile(r"[\u0400-\u04FF\u0500-\u052F]"),
    "uk": re.compile(r"[\u0400-\u04FF\u0500-\u052F]"),
    "be": re.compile(r"[\u0400-\u04FF\u0500-\u052F]"),
    "bg": re.compile(r"[\u0400-\u04FF\u0500-\u052F]"),
    "sr": re.compile(r"[\u0400-\u04FF\u0500-\u052F]"),
    # Greek
    "el": re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]"),
    # Arabic script
    "ar": re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"),
    "fa": re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"),
    "ur": re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"),
    # Hebrew
    "he": re.compile(r"[\u0590-\u05FF\uFB1D-\uFB4F]"),
    # Thai
    "th": re.compile(r"[\u0E00-\u0E7F]"),
    # Vietnamese: Latin + diacritics; any non-ASCII is a signal
    "vi": re.compile(r"[^\x00-\x7F]"),
    # Devanagari (Hindi, Marathi, Nepali)
    "hi": re.compile(r"[\u0900-\u097F]"),
    "mr": re.compile(r"[\u0900-\u097F]"),
    "ne": re.compile(r"[\u0900-\u097F]"),
}


def normalize_lang_code(source_lang: str) -> str:
    """Normalize a language code to its script-lookup key (e.g. zh-CN -> zh)."""
    if not source_lang:
        return "zh"
    return str(source_lang).strip().lower().split("-")[0].split("_")[0]


def needs_translation(text: Any, source_lang: str = "zh") -> bool:
    """Check whether text contains characters from the source language's script.

    For known scripts this is a precise regex test. For unrecognized source
    languages it falls back to "contains any non-ASCII characters".

    Args:
        text: Value to test (non-strings and blank strings are never translated).
        source_lang: Source language code (ISO 639-1 or BCP-47).

    Returns:
        True if the text should be sent for translation.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    pattern = _SCRIPT_PATTERNS.get(normalize_lang_code(source_lang))
    if pattern is None:
        return bool(re.search(r"[^\x00-\x7F]", text))
    return bool(pattern.search(text))


def clean_path(path: str) -> str:
    """Normalise shell provided paths, removing quotes and escaped spaces."""
    normalised = path.strip("'\"")
    normalised = normalised.replace("\\ ", " ")
    normalised = normalised.replace("\\'", "'")
    return normalised


def iter_presentation_files(target: Path) -> Iterator[Path]:
    """Yield PowerPoint files contained in *target*.

    If *target* is a single file it will be yielded when it has the expected
    suffix. When *target* is a directory the function walks the tree and yields
    any ``.ppt`` or ``.pptx`` files that are discovered.
    """
    suffixes = {".ppt", ".pptx"}
    if target.is_file():
        if target.suffix.lower() in suffixes:
            yield target
        return

    if not target.exists():
        return

    for path in target.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path
