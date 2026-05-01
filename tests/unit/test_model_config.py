from sage_ts.config.models import (
    DEFAULT_MODEL,
    LEGACY_MODEL,
    model_metadata,
    paired_model_metadata,
    supports_temperature,
)


def test_default_model_is_gpt_4o_mini() -> None:
    assert DEFAULT_MODEL == "gpt-4o-mini"
    assert LEGACY_MODEL == "gpt-5-mini"


def test_model_metadata_marks_gpt_4o_mini_for_comparisons() -> None:
    metadata = model_metadata("gpt-4o-mini")

    assert metadata["requested_model"] == "gpt-4o-mini"
    assert metadata["resolved_model"] == "gpt-4o-mini"
    assert metadata["comparison_key"] == "gpt-4o-mini"
    assert metadata["temperature_supported"] is True


def test_gpt_5_mini_remains_available_with_different_parameter_policy() -> None:
    assert supports_temperature("gpt-4o-mini") is True
    assert supports_temperature("gpt-5-mini") is False


def test_paired_model_metadata_has_stable_key() -> None:
    metadata = paired_model_metadata(
        agent_model="gpt-4o-mini",
        generation_model="gpt-4o-mini",
        user_model="GPT_4_o_2024_05_13",
    )

    assert metadata["comparison_key"].startswith(
        "agent=gpt-4o-mini|generation=gpt-4o-mini|"
    )
