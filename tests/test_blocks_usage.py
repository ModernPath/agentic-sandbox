from blocks_fakes import RecordingTransport
from sandbox_blocks.config import Settings
from sandbox_blocks.llm import build_llm
from sandbox_blocks.usage import UsageTotals, metered, track_usage


def test_usage_is_summed_per_tracked_block():  # U-1
    transport = RecordingTransport({"output_text": "a", "usage": {"input_tokens": 10, "output_tokens": 3}})
    llm = build_llm(Settings.from_env({"SANDBOX_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "k"}), transport=transport)
    with track_usage() as totals:
        llm.complete("one")
        llm.complete("two")
    assert totals == UsageTotals(input_tokens=20, output_tokens=6, calls=2)


def test_calls_outside_tracking_are_not_counted():  # U-2
    transport = RecordingTransport({"output_text": "a", "usage": {"input_tokens": 5, "output_tokens": 1}})
    llm = build_llm(Settings.from_env({"SANDBOX_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "k"}), transport=transport)
    llm.complete("untracked")
    with track_usage() as totals:
        pass
    assert totals.calls == 0


def test_gemini_style_usage_names_are_normalised():  # U-3
    inner = RecordingTransport({"usage": {"total_input_tokens": 7, "total_output_tokens": 2}})
    with track_usage() as totals:
        metered(inner)("u", {}, {}, 1)
    assert (totals.input_tokens, totals.output_tokens, totals.calls) == (7, 2, 1)


def test_missing_usage_still_counts_the_call():  # U-4
    inner = RecordingTransport({"output_text": "x"})
    with track_usage() as totals:
        metered(inner)("u", {}, {}, 1)
    assert totals.calls == 1 and totals.input_tokens == 0
