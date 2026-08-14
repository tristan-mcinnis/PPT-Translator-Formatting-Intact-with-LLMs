"""Translation service orchestrating providers, caching and chunking."""
from __future__ import annotations

import hashlib
import re
import threading
from typing import Dict, List

from .providers.base import TranslationProvider
from .utils import needs_translation

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")


class TranslationService:
    """Translate text using a configured provider with caching support."""

    def __init__(self, provider: TranslationProvider, *, max_chunk_size: int = 1000) -> None:
        self.provider = provider
        self.max_chunk_size = max_chunk_size
        self._cache: Dict[str, str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _cache_key(text: str, source_lang: str, target_lang: str) -> str:
        """Cache key includes the language pair so results never leak across runs."""
        payload = "\x1f".join([source_lang.lower(), target_lang.lower(), text])
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate ``text`` and cache repeated requests."""
        if not text or text.isspace():
            return text
        if not needs_translation(text, source_lang):
            return text

        key = self._cache_key(text, source_lang, target_lang)
        with self._lock:
            if key in self._cache:
                return self._cache[key]

        chunks = self.chunk_text(text, self.max_chunk_size)
        translated_chunks: List[str] = []
        for chunk in chunks:
            stripped = chunk.strip()
            if not stripped:
                translated_chunks.append(chunk)
                continue
            translated = self.provider.translate(chunk, source_lang, target_lang)
            translated_chunks.append(translated.strip())

        combined = " ".join(part for part in translated_chunks if part)
        if not combined:
            combined = text

        with self._lock:
            self._cache[key] = combined
        return combined

    def translate_many(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, str]:
        """Translate a list of texts in one provider batch call.

        Falls back to per-text translation for anything the provider's batch
        path cannot handle. Results are cached like :meth:`translate`.

        Args:
            texts: Texts to translate.
            source_lang: Source language code.
            target_lang: Target language code.

        Returns:
            Mapping from original text to translation.
        """
        results: Dict[str, str] = {}
        to_translate: List[str] = []

        for text in texts:
            if not text or text.isspace() or not needs_translation(text, source_lang):
                results[text] = text
                continue
            key = self._cache_key(text, source_lang, target_lang)
            with self._lock:
                cached = self._cache.get(key)
            if cached is not None:
                results[text] = cached
            else:
                to_translate.append(text)

        if to_translate:
            try:
                batch = self.provider.translate_batch(to_translate, source_lang, target_lang)
            except Exception:
                batch = {text: self.provider.translate(text, source_lang, target_lang) for text in to_translate}

            for text in to_translate:
                translation = batch.get(text, text)
                if not translation or translation.isspace():
                    translation = text
                results[text] = translation
                key = self._cache_key(text, source_lang, target_lang)
                with self._lock:
                    self._cache[key] = translation

        return results

    @staticmethod
    def chunk_text(text: str, max_chunk_size: int = 1000) -> List[str]:
        """Split long text into smaller chunks preserving sentence boundaries."""
        if len(text) <= max_chunk_size:
            return [text]

        sentences = [segment.strip() for segment in _SENTENCE_SPLIT_PATTERN.split(text) if segment.strip()]
        if not sentences:
            sentences = [text]

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current and current_len + sentence_len + 1 > max_chunk_size:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            if sentence_len > max_chunk_size:
                if current:
                    chunks.append(" ".join(current))
                    current = []
                    current_len = 0
                chunks.extend(
                    [sentence[i : i + max_chunk_size] for i in range(0, sentence_len, max_chunk_size)]
                )
                continue
            current.append(sentence)
            current_len += sentence_len + 1

        if current:
            chunks.append(" ".join(current))

        if not chunks:
            return [text]
        return chunks

    def clear_cache(self) -> None:
        """Drop cached translations."""
        with self._lock:
            self._cache.clear()

    def cache_size(self) -> int:
        """Return the number of cached entries."""
        with self._lock:
            return len(self._cache)
