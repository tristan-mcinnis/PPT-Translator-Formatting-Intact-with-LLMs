from __future__ import annotations

from ppt_translator.translation import TranslationService
from ppt_translator.providers.base import TranslationProvider
from ppt_translator.utils import needs_translation


class DummyProvider(TranslationProvider):
    def __init__(self) -> None:
        super().__init__(model="dummy")
        self.calls: list[str] = []
        self.batch_calls: list[list[str]] = []

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        self.calls.append(text)
        return f"{text}->{target_lang}"

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> dict[str, str]:
        self.batch_calls.append(list(texts))
        return {text: f"{text}->{target_lang}" for text in texts}


def test_chunk_text_respects_maximum_size():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=20)
    text = "Sentence one. Sentence two. Sentence three."
    chunks = service.chunk_text(text, max_chunk_size=20)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 20 for chunk in chunks)


def test_translate_uses_cache():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=100)
    result_a = service.translate("你好世界", "zh", "en")
    result_b = service.translate("你好世界", "zh", "en")
    assert result_a == result_b
    assert provider.calls.count("你好世界") == 1
    assert service.cache_size() == 1


def test_translate_skips_text_already_in_target_script():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=100)
    result = service.translate("Already English", "zh", "en")
    assert result == "Already English"
    assert provider.calls == []


def test_translate_cache_is_language_pair_aware():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=100)
    en_result = service.translate("你好世界", "zh", "en")
    fr_result = service.translate("你好世界", "zh", "fr")
    assert en_result == "你好世界->en"
    assert fr_result == "你好世界->fr"
    assert provider.calls.count("你好世界") == 2
    assert service.cache_size() == 2


def test_translate_many_uses_single_batch_call():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=100)
    results = service.translate_many(["市场", "品牌", "消费者"], "zh", "en")
    assert results == {
        "市场": "市场->en",
        "品牌": "品牌->en",
        "消费者": "消费者->en",
    }
    assert provider.batch_calls == [["市场", "品牌", "消费者"]]
    assert provider.calls == []
    # Second run is served from cache, no new calls.
    service.translate_many(["市场", "品牌"], "zh", "en")
    assert len(provider.batch_calls) == 1


def test_translate_many_skips_non_source_text():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=100)
    results = service.translate_many(["Hello", "品牌"], "zh", "en")
    assert results == {"Hello": "Hello", "品牌": "品牌->en"}
    assert provider.batch_calls == [["品牌"]]


def test_chunk_text_handles_very_long_sentence():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=50)
    text = "a" * 130
    chunks = service.chunk_text(text, max_chunk_size=50)
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert sum(len(chunk) for chunk in chunks) >= len(text)


def test_clear_cache_resets_entries():
    provider = DummyProvider()
    service = TranslationService(provider, max_chunk_size=100)
    service.translate("缓存我", "zh", "de")
    assert service.cache_size() == 1
    service.clear_cache()
    assert service.cache_size() == 0


def test_needs_translation_script_detection():
    assert needs_translation("你好", "zh") is True
    assert needs_translation("Hello", "zh") is False
    assert needs_translation("こんにちは", "ja") is True
    assert needs_translation("안녕하세요", "ko") is True
    assert needs_translation("Привет", "ru") is True
    assert needs_translation("Hello", "ja") is False
    assert needs_translation("", "zh") is False
    assert needs_translation(None, "zh") is False
