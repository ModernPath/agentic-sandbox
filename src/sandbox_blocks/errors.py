"""Errors raised by sandbox building blocks. Messages never include API keys."""


class ConfigurationError(ValueError):
    """Settings are missing or invalid."""


class ProviderError(RuntimeError):
    """A model or search provider call failed."""
