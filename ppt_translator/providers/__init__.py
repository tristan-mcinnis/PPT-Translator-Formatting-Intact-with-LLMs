"""Provider factory for translation services."""
from __future__ import annotations

from typing import Dict, Type

from .anthropic_provider import AnthropicProvider
from .base import ProviderConfigurationError, TranslationProvider
from .deepseek import DeepSeekProvider
from .gemini_provider import GeminiProvider
from .grok_provider import GrokProvider
from .openai_provider import OpenAIProvider

PROVIDER_REGISTRY: Dict[str, Type[TranslationProvider]] = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "grok": GrokProvider,
    "gemini": GeminiProvider,
}

# Current model IDs as of the DeepSeek V4 line. See
# https://api-docs.deepseek.com/quick_start/pricing for the latest list.
PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "deepseek": {"model": "deepseek-v4-flash"},
    "openai": {"model": "gpt-5.2-2025-12-11"},
    "anthropic": {"model": "claude-sonnet-4-5-20250514"},
    "grok": {"model": "grok-4.1-fast"},
    "gemini": {"model": "gemini-3-flash-preview"},
}


def list_providers() -> list[str]:
    """Return the available provider identifiers."""
    return sorted(PROVIDER_REGISTRY.keys())


def create_provider(provider_name: str, *, model: str | None = None, **kwargs) -> TranslationProvider:
    """Instantiate a provider by name."""
    name = provider_name.lower()
    if name not in PROVIDER_REGISTRY:
        raise ValueError(f"Unsupported provider '{provider_name}'. Available: {', '.join(list_providers())}")
    provider_cls = PROVIDER_REGISTRY[name]
    default_options = PROVIDER_DEFAULTS.get(name, {}).copy()
    if model:
        default_options["model"] = model
    if "model" not in default_options:
        raise ValueError(f"No model specified for provider '{provider_name}'.")
    default_options.update(kwargs)
    return provider_cls(**default_options)


__all__ = [
    "AnthropicProvider",
    "DeepSeekProvider",
    "GeminiProvider",
    "GrokProvider",
    "OpenAIProvider",
    "ProviderConfigurationError",
    "TranslationProvider",
    "create_provider",
    "list_providers",
]
