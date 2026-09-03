from scripts.cache_llm_usage_by_task import _event_summary, _usage_from_row


def test_event_summary_backfills_provider_prefix_tokens_from_raw_usage() -> None:
    summary = _event_summary(
        [
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 1114,
                "completion_tokens": 20,
                "total_tokens": 1134,
                "usage_available": True,
                "raw_usage": {"prompt_tokens_details": {"cached_tokens": 1024}},
            }
        ]
    )

    assert summary["llm_provider_cached_prompt_tokens"] == 1024
    assert summary["llm_provider_cached_prompt_call_count"] == 1
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 1
    assert (
        summary["llm_usage_by_source"]["toolsandbox_agent"][
            "llm_provider_cached_prompt_tokens"
        ]
        == 1024
    )


def test_row_usage_uses_event_backfill_and_preserves_unavailable_state() -> None:
    fallback = _event_summary(
        [
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
                "raw_usage": {"prompt_tokens_details": {"cached_tokens": 64}},
            }
        ]
    )
    usage = _usage_from_row(
        {
            "llm_usage_recorded": True,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 100,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 110,
            "llm_usage_available_count": 1,
        },
        fallback,
        arm="candidate",
    )

    assert usage["llm_provider_cached_prompt_tokens"] == 64
    assert usage["llm_provider_cached_prompt_call_count"] == 1
    assert usage["llm_provider_cached_prompt_tokens_available_count"] == 1
    unavailable = _event_summary([])
    assert unavailable["llm_provider_cached_prompt_tokens"] is None
    assert unavailable["llm_provider_cached_prompt_call_count"] is None
    assert unavailable["llm_provider_cached_prompt_tokens_available_count"] == 0


def test_row_usage_replaces_legacy_source_summary_from_reconciled_events() -> None:
    fallback = _event_summary(
        [
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
                "raw_usage": {"prompt_tokens_details": {"cached_tokens": 64}},
            }
        ]
    )
    usage = _usage_from_row(
        {
            "llm_usage_recorded": True,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 100,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 110,
            "llm_usage_available_count": 1,
            "llm_usage_by_source": {"toolsandbox_agent": {"llm_call_count": 1}},
        },
        fallback,
        arm="candidate",
    )

    source = usage["llm_usage_by_source"]["toolsandbox_agent"]
    assert source["llm_provider_cached_prompt_tokens"] == 64
    assert source["llm_provider_cached_prompt_call_count"] == 1
    assert source["llm_provider_cached_prompt_tokens_available_count"] == 1


def test_row_usage_never_downgrades_richer_source_provider_metadata() -> None:
    fallback = _event_summary(
        [
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
            }
        ]
    )
    usage = _usage_from_row(
        {
            "llm_usage_recorded": True,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 100,
            "llm_provider_cached_prompt_tokens": 64,
            "llm_provider_cached_prompt_call_count": 1,
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 110,
            "llm_usage_available_count": 1,
            "llm_usage_by_source": {
                "toolsandbox_agent": {
                    "llm_call_count": 1,
                    "llm_provider_cached_prompt_tokens": 64,
                    "llm_provider_cached_prompt_call_count": 1,
                    "llm_provider_cached_prompt_tokens_available_count": 1,
                }
            },
        },
        fallback,
        arm="candidate",
    )

    source = usage["llm_usage_by_source"]["toolsandbox_agent"]
    assert source["llm_provider_cached_prompt_tokens"] == 64
    assert source["llm_provider_cached_prompt_call_count"] == 1
    assert source["llm_provider_cached_prompt_tokens_available_count"] == 1


def test_event_summary_marks_mixed_provider_metadata_as_partial() -> None:
    summary = _event_summary(
        [
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
                "raw_usage": {"prompt_tokens_details": {"cached_tokens": 64}},
            },
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 50,
                "completion_tokens": 5,
                "total_tokens": 55,
                "usage_available": True,
                "raw_usage": {},
            },
        ]
    )

    assert summary["llm_call_count"] == 2
    assert summary["llm_provider_cached_prompt_tokens"] == 64
    assert summary["llm_provider_cached_prompt_call_count"] == 1
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 1
