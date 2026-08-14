"""Base classes for translation providers."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List

from openai import OpenAI

from ..utils import needs_translation


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider cannot be configured properly."""


class TranslationProvider(ABC):
    """Abstract provider responsible for translating text."""

    def __init__(self, model: str, temperature: float = 0.3) -> None:
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate ``text`` from ``source_lang`` to ``target_lang``."""

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, str]:
        """Translate a list of texts.

        The default implementation calls :meth:`translate` per text; providers
        that can batch (e.g. OpenAI-compatible JSON mode) override this.

        Args:
            texts: Texts to translate.
            source_lang: Source language code.
            target_lang: Target language code.

        Returns:
            Mapping from original text to translation.
        """
        return {text: self.translate(text, source_lang, target_lang) for text in texts}


class OpenAICompatibleProvider(TranslationProvider):
    """Provider implementation for OpenAI compatible chat completion APIs."""

    api_key_env: str = "OPENAI_API_KEY"
    default_base_url: str | None = None

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.3,
        organization: str | None = None,
    ) -> None:
        super().__init__(model, temperature=temperature)
        resolved_key = api_key or os.getenv(self.api_key_env)
        if not resolved_key:
            raise ProviderConfigurationError(
                f"Missing API key for provider '{self.__class__.__name__}'. "
                f"Set the {self.api_key_env} environment variable."
            )
        self.client = OpenAI(
            api_key=resolved_key,
            base_url=base_url or self.default_base_url,
            organization=organization,
        )

    def build_messages(self, text: str, source_lang: str, target_lang: str) -> List[Dict[str, str]]:
        """Construct chat messages sent to the model."""
        system_prompt = (
            "You are a translation assistant. Translate the user provided text "
            f"from {source_lang} to {target_lang} while preserving tone and formatting. "
            "Output ONLY the translation, with no explanations or extra text."
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not needs_translation(text, source_lang):
            return text
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.build_messages(text, source_lang, target_lang),
            temperature=self.temperature,
            stream=False,
        )
        return response.choices[0].message.content.strip()

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, str]:
        """Translate a list of texts with a single JSON-mode request.

        Falls back to per-text :meth:`translate` when the model does not
        return a parseable JSON map or the API rejects JSON mode.

        Args:
            texts: Texts to translate.
            source_lang: Source language code.
            target_lang: Target language code.

        Returns:
            Mapping from original text to translation.
        """
        results: Dict[str, str] = {}
        to_translate = [t for t in texts if needs_translation(t, source_lang)]
        for text in texts:
            if text not in to_translate:
                results[text] = text

        if not to_translate:
            return results

        system_prompt = (
            "You are a translation assistant. Translate each text from "
            f"{source_lang} to {target_lang} while preserving tone and formatting. "
            "Return a JSON object where each key is the EXACT original text and "
            "each value is its translation. Output ONLY the JSON object, with no "
            "explanations, no markdown fences."
        )
        payload = json.dumps(to_translate, ensure_ascii=False)
        user_prompt = (
            f"Translate these {len(to_translate)} texts. Return a JSON object "
            f"mapping each original text to its {target_lang} translation.\n\n"
            f"TEXTS: {payload}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
                stream=False,
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            if isinstance(parsed, dict) and all(
                isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
            ):
                for text in to_translate:
                    translation = parsed.get(text)
                    results[text] = translation.strip() if translation and translation.strip() else text
                # Any text the model failed to echo falls back to single calls.
                missing = [t for t in to_translate if t not in parsed or not parsed.get(t, "").strip()]
                for text in missing:
                    results[text] = self.translate(text, source_lang, target_lang)
                return results
        except Exception:  # JSON mode unsupported or parse failure -> fall back
            pass

        for text in to_translate:
            results[text] = self.translate(text, source_lang, target_lang)
        return results
