from research_brief.__main__ import main


def test_cli_without_topic_prints_usage():
    assert main([], environ={}) == 2


def test_cli_with_search_disabled_reports_configuration_error(capsys):
    code = main(["quantum computing"], environ={"SANDBOX_SEARCH_PROVIDER": "none", "GEMINI_API_KEY": "k"})
    assert code == 1
    assert "SANDBOX_SEARCH_PROVIDER" in capsys.readouterr().err
