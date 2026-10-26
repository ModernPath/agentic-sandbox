import pytest

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError


def test_defaults_from_empty_env():  # T1
    settings = Settings.from_env({})
    assert settings.llm_provider == "gemini"
    assert settings.search_provider == "none"
    assert settings.search_max_results == 5
    assert settings.fetch_max_chars == 8000


def test_provider_and_model_overrides():  # T2
    settings = Settings.from_env({
        "SANDBOX_LLM_PROVIDER": "openai",
        "SANDBOX_LLM_MODEL": "my-model",
        "SANDBOX_SEARCH_PROVIDER": "exa",
    })
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "my-model"
    assert settings.search_provider == "exa"


def test_unknown_llm_provider_is_rejected():  # T3
    with pytest.raises(ConfigurationError, match="gemini, openai"):
        Settings.from_env({"SANDBOX_LLM_PROVIDER": "mistral"})


def test_non_integer_numeric_setting_is_rejected():  # T4
    with pytest.raises(ConfigurationError, match="SANDBOX_SEARCH_MAX_RESULTS"):
        Settings.from_env({"SANDBOX_SEARCH_MAX_RESULTS": "many"})


def test_env_example_lists_every_variable_read_by_config():  # T25
    from pathlib import Path
    import re

    root = Path(__file__).resolve().parents[1]
    documented = set(re.findall(r"^#?\s*([A-Z_]+)=", (root / ".env.example").read_text(), re.M))
    read = set(re.findall(r'"([A-Z_]+)"', (root / "src/sandbox_blocks/config.py").read_text()))
    read = {name for name in read if name.startswith(("SANDBOX_", "GEMINI_", "OPENAI_", "EXA_", "ANTHROPIC_", "AZURE_"))}
    assert read - documented == set()
