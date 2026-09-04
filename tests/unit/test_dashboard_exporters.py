# mypy: ignore-errors
import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from sage_ts.dashboard import exporters
from sage_ts.dashboard.exporters import write_protocol_dashboard
from sage_ts.dashboard.server import DashboardRequestHandler


@pytest.fixture(autouse=True)
def _avoid_global_latest_dashboard_pointer(monkeypatch) -> None:
    monkeypatch.setattr(
        exporters, "_write_latest_pointer", lambda *args, **kwargs: None
    )


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "result_summary.json").write_text(
        json.dumps({"per_scenario_results": rows}) + "\n",
        encoding="utf-8",
    )


def _write_live_summary(
    path: Path,
    rows: list[dict[str, object]],
    *,
    updated_at=None,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"per_scenario_results": rows}
    if updated_at is not None:
        payload["updated_at"] = updated_at
    (path / "live_result_summary.json").write_text(
        json.dumps(payload) + "\n", encoding="utf-8"
    )


def test_dashboard_json_readers_tolerate_in_progress_empty_files(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    partial = tmp_path / "partial.json"
    partial.write_text("{", encoding="utf-8")

    assert exporters._read_json(empty, {"status": "pending"}) == {"status": "pending"}
    assert exporters._read_json(partial, {"status": "pending"}) == {"status": "pending"}
    assert exporters._read_json_value(empty, []) == []
    assert exporters._read_json_value(partial, []) == []


def test_dashboard_jsonl_reader_tolerates_only_unterminated_live_tail(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live.jsonl"
    path.write_text('{"complete": true}\n{"partial":', encoding="utf-8")

    assert exporters._read_jsonl(path) == [{"complete": True}]

    path.write_text('{"complete": true}\nnot-json\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        exporters._read_jsonl(path)


def test_cached_control_transcript_loading_is_opt_in(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    records = repo / "artifacts" / "baselines" / "control_task_baselines" / "records"
    records.mkdir(parents=True)
    record_id = "a" * 64
    transcript = repo / "old_run" / "trajectories" / "scenario" / "conversation.json"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps([{"role": "assistant", "content": "cached transcript"}]) + "\n",
        encoding="utf-8",
    )
    (records / f"{record_id}.json").write_text(
        json.dumps(
            {
                "transcript_path": str(transcript.relative_to(repo)),
                "transcript_hash": "hash",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exporters, "_repo_root", lambda: repo)
    monkeypatch.delenv("SAGE_DASHBOARD_LOAD_CACHED_CONTROL_TRANSCRIPTS", raising=False)

    messages, source = exporters._cached_control_transcript({"record_ids": [record_id]})

    assert messages == []
    assert source["record_id"] == record_id
    assert source["transcript_loaded"] is False
    assert source["transcript_load_policy"] == "disabled_for_live_dashboard"

    monkeypatch.setenv("SAGE_DASHBOARD_LOAD_CACHED_CONTROL_TRANSCRIPTS", "1")
    messages, source = exporters._cached_control_transcript({"record_ids": [record_id]})

    assert messages == [{"role": "assistant", "content": "cached transcript"}]
    assert source["transcript_loaded"] is True


class _SuccessfulDashboardResponse:
    status = 200

    def __init__(self, body: bytes = b"dashboard") -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_open_dashboard_uses_checked_macos_open(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    index = tmp_path / "index.html"
    index.write_text("dashboard", encoding="utf-8")

    monkeypatch.setattr(
        exporters,
        "ensure_dashboard_server",
        lambda *, port, server_root: calls.append(("server", port)),
    )
    monkeypatch.setattr(
        exporters,
        "dashboard_url",
        lambda index_path, *, port, server_root: (
            f"http://127.0.0.1:{port}/dashboard/index.html"
        ),
    )
    monkeypatch.setattr(
        exporters, "urlopen", lambda url, timeout: _SuccessfulDashboardResponse()
    )
    monkeypatch.setattr(
        exporters.webbrowser,
        "open_new_tab",
        lambda _url: pytest.fail("macOS must use only the checked OS opener"),
    )
    monkeypatch.setattr(exporters.sys, "platform", "darwin")
    monkeypatch.setattr(
        exporters.subprocess,
        "run",
        lambda args, **kwargs: calls.append(("open", (args, kwargs))),
    )

    url = exporters.open_dashboard(index, port=5520)

    assert url == "http://127.0.0.1:5520/dashboard/index.html"
    assert ("server", 5520) in calls
    open_call = next(value for label, value in calls if label == "open")
    assert open_call[0] == ["open", url]
    assert open_call[1]["check"] is True
    assert open_call[1]["timeout"] == 10


def test_open_dashboard_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Dashboard file does not exist"):
        exporters.open_dashboard(tmp_path / "missing.html", port=5520)


def test_open_dashboard_requires_non_macos_browser_acceptance(
    tmp_path: Path, monkeypatch
) -> None:
    index = tmp_path / "index.html"
    index.write_text("dashboard", encoding="utf-8")
    monkeypatch.setattr(exporters, "ensure_dashboard_server", lambda **_kwargs: None)
    monkeypatch.setattr(
        exporters,
        "dashboard_url",
        lambda *_args, **_kwargs: "http://127.0.0.1:5520/index.html",
    )
    monkeypatch.setattr(
        exporters, "urlopen", lambda url, timeout: _SuccessfulDashboardResponse()
    )
    monkeypatch.setattr(exporters.sys, "platform", "linux")
    monkeypatch.setattr(exporters.webbrowser, "open_new_tab", lambda _url: False)

    with pytest.raises(RuntimeError, match="default browser refused"):
        exporters.open_dashboard(index, port=5520)


def test_dashboard_server_rejects_listener_with_wrong_root(
    tmp_path: Path, monkeypatch
) -> None:
    desired_root = tmp_path / "desired"
    wrong_root = tmp_path / "wrong"
    monkeypatch.setattr(exporters, "_dashboard_port_is_open", lambda _port: True)
    monkeypatch.setattr(
        exporters,
        "_dashboard_server_identity",
        lambda _port: {
            "protocol": exporters.DASHBOARD_SERVER_PROTOCOL,
            "root": str(wrong_root.resolve()),
        },
    )

    with pytest.raises(RuntimeError, match="different dashboard root"):
        exporters.ensure_dashboard_server(port=5520, server_root=desired_root)


def test_dashboard_server_reuses_only_matching_identified_root(
    tmp_path: Path, monkeypatch
) -> None:
    desired_root = tmp_path / "desired"
    monkeypatch.setattr(exporters, "_dashboard_port_is_open", lambda _port: True)
    monkeypatch.setattr(
        exporters,
        "_dashboard_server_identity",
        lambda _port: {
            "protocol": exporters.DASHBOARD_SERVER_PROTOCOL,
            "root": str(desired_root.resolve()),
        },
    )
    monkeypatch.setattr(
        exporters.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("matching server must be reused"),
    )

    exporters.ensure_dashboard_server(port=5520, server_root=desired_root)


def test_dashboard_server_identity_endpoint_is_bound_to_served_root(
    tmp_path: Path,
) -> None:
    handler = partial(
        DashboardRequestHandler,
        directory=str(tmp_path),
        dashboard_root=str(tmp_path),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        identity = exporters._dashboard_server_identity(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert identity == {
        "protocol": exporters.DASHBOARD_SERVER_PROTOCOL,
        "root": str(tmp_path.resolve()),
    }


def test_open_dashboard_rejects_content_from_a_different_root(
    tmp_path: Path, monkeypatch
) -> None:
    index = tmp_path / "index.html"
    index.write_text("expected dashboard", encoding="utf-8")
    monkeypatch.setattr(exporters, "ensure_dashboard_server", lambda **_kwargs: None)
    monkeypatch.setattr(
        exporters,
        "dashboard_url",
        lambda *_args, **_kwargs: "http://127.0.0.1:5520/index.html",
    )
    monkeypatch.setattr(
        exporters,
        "urlopen",
        lambda _url, timeout: _SuccessfulDashboardResponse(b"wrong dashboard"),
    )

    with pytest.raises(RuntimeError, match="different file/root"):
        exporters.open_dashboard(index, port=5520)


def test_open_dashboard_rejects_file_outside_explicit_server_root(
    tmp_path: Path,
) -> None:
    index = tmp_path / "outside" / "index.html"
    index.parent.mkdir()
    index.write_text("dashboard", encoding="utf-8")

    with pytest.raises(ValueError, match="outside server root"):
        exporters.open_dashboard(
            index,
            port=5520,
            server_root=tmp_path / "different-root",
        )


def test_dashboard_url_supports_output_outside_repo(tmp_path: Path) -> None:
    dashboard_dir = tmp_path / "external_run" / "dashboard"
    index_path = dashboard_dir / "task_compare.html"

    assert (
        exporters.dashboard_url(
            index_path,
            port=62000,
        )
        == "http://127.0.0.1:62000/task_compare.html"
    )


def test_write_protocol_dashboard_exports_paired_data(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    control = run_root / "control" / "control_run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    control.parent.mkdir(parents=True)
    candidate.parent.mkdir(parents=True)
    (control.parent / "sage_ts_run_manifest.json").write_text(
        json.dumps({"started_at": "2026-05-31T12:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    (candidate.parent / "sage_ts_run_manifest.json").write_text(
        json.dumps({"started_at": "2026-05-31T12:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    _write_summary(
        control,
        [
            {
                "name": "a",
                "similarity": 0.2,
                "turn_count": 6,
                "llm_usage_recorded": True,
                "llm_call_count": 2,
                "llm_prompt_tokens": 120,
                "llm_provider_cached_prompt_tokens": 64,
                "llm_provider_cached_prompt_call_count": 1,
                "llm_provider_cached_prompt_tokens_available_count": 2,
                "llm_completion_tokens": 30,
                "llm_total_tokens": 150,
                "llm_live_call_count": 2,
                "llm_cached_call_count": 0,
                "llm_usage_available_count": 2,
                "categories": ["CANONICALIZATION"],
                "control_cache_source": "cached",
                "control_cache": {
                    "source": "cached",
                    "compatible_count": 3,
                    "canonical_variance": 0.01,
                },
            },
            {"name": "b", "similarity": 1.0, "turn_count": 4, "categories": []},
        ],
    )
    _write_live_summary(
        control,
        [],
        updated_at="2026-05-31T12:02:00+00:00",
    )
    _write_summary(
        candidate,
        [
            {
                "name": "a",
                "similarity": 1.0,
                "turn_count": 4,
                "llm_usage_recorded": True,
                "llm_call_count": 3,
                "llm_prompt_tokens": 210,
                "llm_provider_cached_prompt_tokens": 128,
                "llm_provider_cached_prompt_call_count": 2,
                "llm_provider_cached_prompt_tokens_available_count": 3,
                "llm_completion_tokens": 45,
                "llm_total_tokens": 255,
                "llm_live_call_count": 3,
                "llm_cached_call_count": 0,
                "llm_usage_available_count": 3,
                "categories": ["CANONICALIZATION"],
            },
            {"name": "b", "similarity": 0.5, "turn_count": 5, "categories": []},
        ],
    )
    _write_live_summary(
        candidate,
        [],
        updated_at="2026-05-31T12:04:00+00:00",
    )
    (candidate / "tool_birth_events.jsonl").write_text(
        json.dumps({"accepted": True, "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (candidate / "reuse_events.jsonl").write_text(
        json.dumps({"scenario": "a", "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="mechanism_40",
        status="complete",
        phase="comparison",
        agent="gpt-4o-mini",
        user="GPT_4_o_2024_05_13",
        model_metadata={
            "agent": {
                "requested_model": "gpt-4o-mini",
                "resolved_model": "gpt-4o-mini",
            },
            "generation": {
                "requested_model": "gpt-4o-mini",
                "resolved_model": "gpt-4o-mini",
            },
            "comparison_key": "agent=gpt-4o-mini|generation=gpt-4o-mini|user=GPT_4_o_2024_05_13",
        },
        generation_enabled=True,
        base_tool_policy="recency_reduced",
        scenario_count=2,
        control_dir=control,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    assert index.exists()
    data = json.loads((index.parent / "data.json").read_text(encoding="utf-8"))
    assert data["comparison"]["gain_count"] == 1
    assert data["comparison"]["regression_count"] == 1
    assert data["control"]["wall_time_seconds"] == pytest.approx(120.0)
    assert data["candidate"]["wall_time_seconds"] == pytest.approx(240.0)
    assert data["candidate"]["accepted_tool_count"] == 1
    assert data["candidate"]["reuse_count"] == 1
    assert data["model_metadata"]["agent"]["resolved_model"] == "gpt-4o-mini"
    assert data["comparison_model_key"].startswith("agent=gpt-4o-mini")
    assert data["scenarios"][0]["reused_tools"] == ["helper"]
    assert data["scenarios"][0]["control_cache_source"] == "cached"
    assert data["scenarios"][0]["control_cache"]["compatible_count"] == 3
    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    assert task_focus["tasks"][0]["control_cache_source"] == "cached"
    assert task_focus["summary"]["control_llm_call_count"] == 2
    assert task_focus["summary"]["candidate_llm_total_tokens"] == 255
    assert task_focus["summary"]["control_llm_provider_cached_prompt_tokens"] == 64
    assert task_focus["summary"]["candidate_llm_provider_cached_prompt_call_count"] == 2
    assert (
        task_focus["summary"][
            "candidate_llm_provider_cached_prompt_tokens_available_count"
        ]
        == 3
    )
    assert task_focus["pairs"][0]["control"]["llm_call_count"] == 2
    assert task_focus["pairs"][0]["candidate"]["llm_total_tokens"] == 255
    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    assert task_compare["summary"]["control_llm_total_tokens"] == 150
    assert task_compare["summary"]["candidate_llm_call_count"] == 3
    assert task_compare["summary"]["control_llm_provider_cached_prompt_tokens"] == 64
    assert (
        task_compare["summary"][
            "control_llm_provider_cached_prompt_tokens_available_count"
        ]
        == 2
    )
    assert task_compare["summary"]["control_wall_time_seconds"] == pytest.approx(120.0)
    assert task_compare["summary"]["candidate_wall_time_seconds"] == pytest.approx(
        240.0
    )
    task_compare_html = (index.parent / "task_compare.html").read_text(encoding="utf-8")
    overview_html = index.read_text(encoding="utf-8")
    task_focus_html = (index.parent / "task_focus.html").read_text(encoding="utf-8")
    assert "Outcome Difference" in overview_html
    assert "Canonical Audit Movement" in overview_html
    assert "Score Lift" not in overview_html
    assert "Baseline Outcome" in task_focus_html
    assert "Canonical Audit" in task_focus_html
    assert "Baseline Score" not in task_focus_html
    assert "Total Time B / S" in task_compare_html
    assert "LLM Calls B / S" in task_compare_html
    assert "Tokens B / S" in task_compare_html
    assert "provider-prefix cached" in task_compare_html
    assert 'metric(`${armLabel("control")} Outcome`' in task_compare_html
    assert 'metric(`${armLabel("candidate")} Outcome`' in task_compare_html
    assert "Canonical" not in task_compare_html
    assert "Score Lift" not in task_compare_html
    assert "Score Contribution" not in task_compare_html
    assert "outcome_milestone_similarity" not in task_compare_html
    assert not (index.parent / "custom_task.html").exists()
    assert "control source: cached" in (index.parent / "index.html").read_text(
        encoding="utf-8"
    )


def test_task_compare_live_tool_summary_uses_partial_fallback_data(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    control = run_root / "control" / "control_run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    _write_summary(
        control,
        [
            {
                "name": "called",
                "similarity": 0.4,
                "outcome_similarity": 0.25,
            },
            {
                "name": "visible_only",
                "similarity": 1.0,
                "outcome_similarity": 1.0,
            },
        ],
    )
    _write_summary(
        candidate,
        [
            {
                "name": "called",
                "similarity": 0.8,
                "outcome_similarity": 0.75,
            },
            {
                "name": "visible_only",
                "similarity": 1.0,
                "outcome_similarity": 1.0,
            },
        ],
    )
    (candidate / "tool_birth_events.jsonl").write_text(
        json.dumps({"accepted": True, "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (candidate / "reuse_events.jsonl").write_text(
        json.dumps({"scenario": "called", "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (candidate / "scenario_tool_visibility.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"scenario": "called", "generated_tools": ["helper"]}),
                json.dumps({"scenario": "visible_only", "generated_tools": ["helper"]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (candidate / "scenario_tool_selection.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "scenario": "called",
                        "generated_tools_visible": ["helper"],
                        "generated_tools_called": ["helper"],
                        "generated_tools_failed": [],
                        "generated_tools_attempted": ["helper"],
                    }
                ),
                json.dumps(
                    {
                        "scenario": "visible_only",
                        "generated_tools_visible": ["helper"],
                        "generated_tools_called": [],
                        "generated_tools_failed": [],
                        "generated_tools_attempted": [],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="online_build_full",
        status="running",
        phase="comparison",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        generation_enabled=True,
        base_tool_policy="upstream",
        scenario_count=2,
        control_dir=control,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    tool_summary = task_compare["tool_summary"]
    assert tool_summary["source"] == "live_fallback"
    assert tool_summary["visibility_known"] is True
    assert tool_summary["contribution_known"] is True
    assert tool_summary["visible_tool_count"] == 1
    assert tool_summary["outcome_gains"] == 1
    helper = tool_summary["tools"][0]
    assert helper["name"] == "helper"
    assert helper["visible_count"] == 2
    assert helper["called_count"] == 1
    assert helper["visible_not_called_count"] == 1
    assert "called_subset_mean_canonical_delta" not in helper
    assert helper["called_subset_mean_outcome_delta"] == pytest.approx(0.5)
    assert helper["contribution_pending"] is False
    assert helper["decision"] == "provisional live paired subset"


def test_task_compare_data_recursively_excludes_non_outcome_performance_fields(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    dashboard_dir = run_root / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (run_root / "helper_contribution_summary.json").write_text(
        json.dumps(
            {
                "helpers": {
                    "generated_terminal_action": {
                        "origin": "newly_generated",
                        "visible_count": 1,
                        "called_count": 1,
                        "called_subset": {
                            "scenario_count": 1,
                            "mean_canonical_delta": 0.25,
                            "mean_outcome_delta": 1.0,
                            "canonical_gains": 1,
                            "canonical_regressions": 0,
                            "outcome_gains": 1,
                            "outcome_regressions": 0,
                            "outcome_preserved": 0,
                        },
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    transcript = {
        "index": 0,
        "role": "assistant",
        "label": "assistant",
        "content": (
            "The transcript may say score, milestone, minefield, or canonical; "
            "task evidence must not be redacted."
        ),
        "generated_tools": ["generated_terminal_action"],
        "uses_generated_tool": True,
    }
    task = {
        "id": "candidate:run:direct_action",
        "phase": "candidate",
        "scenario": "direct_action",
        "short_name": "direct action",
        "status": "complete",
        "display_index": 1,
        "similarity": 0.25,
        "score": 0.25,
        "outcome_similarity": 1.0,
        "outcome_milestone_similarity": 0.25,
        "milestones": [{"score": 0.25}],
        "minefields": [{"score": 0.0}],
        "evaluation": {"final_score": 0.25},
        "outcome": {
            "similarity": 0.25,
            "correctness_label": "not exact",
            "agent_result_summary": "Score: 0.250",
        },
        "control_cache_source": "cached",
        "control_cache": {
            "canonical_mean": 0.25,
            "canonical_variance": 0.01,
            "outcome_mean": 1.0,
            "record_ids": ["cache-record"],
        },
        "generated_tools": ["generated_terminal_action"],
        "generated_tool_events": [
            {"kind": "called", "tool": "generated_terminal_action"}
        ],
        "routing": {
            "selected_tool": "generated_terminal_action",
            "inventory": ["native_action", "generated_terminal_action"],
        },
        "messages": [transcript],
        "outcome_checks": [
            {
                "kind": "milestone",
                "score": 1.0,
                "observed_messages": ["generated terminal action completed"],
            }
        ],
    }
    focus_payload = {
        "mode": "paired",
        "summary": {
            "control_mean_similarity": 0.25,
            "candidate_mean_similarity": 0.5,
            "balanced_delta": 0.25,
            "balanced_lift_percent": 100.0,
            "control_mean_outcome_similarity": 0.0,
            "candidate_mean_outcome_similarity": 1.0,
            "balanced_outcome_delta": 1.0,
        },
        "control_cache": {
            "cached_control_tasks": 1,
            "fresh_control_tasks": 0,
            "task_level_fields": ["canonical_mean", "outcome_mean"],
            "baseline_count_and_variance_per_cached_task": {
                "direct_action": {"canonical_mean": 0.25}
            },
        },
        "metric_label": "Canonical Audit",
        "tasks": [task],
        "pairs": [
            {
                "scenario": "direct_action",
                "short_name": "direct action",
                "display_index": 1,
                "control": task,
                "candidate": task,
            }
        ],
    }

    exporters._write_task_compare_dashboard(
        dashboard_dir,
        run_root,
        {},
        focus_payload,
    )

    task_compare = json.loads(
        (dashboard_dir / "task_compare_data.json").read_text(encoding="utf-8")
    )
    forbidden_exact_keys = {
        "baseline_count_and_variance_per_cached_task",
        "balanced_delta",
        "balanced_lift_percent",
        "correctness_label",
        "evaluation",
        "exact_correct",
        "exact_success_rate",
        "outcome",
        "task_level_fields",
    }

    def assert_outcome_only(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).strip().lower().replace("-", "_")
                key_parts = normalized.split("_")
                field_path = (*path, str(key))
                assert normalized not in forbidden_exact_keys, field_path
                assert "canonical" not in normalized, field_path
                assert "milestone" not in normalized, field_path
                assert "minefield" not in normalized, field_path
                assert not ("reference" in normalized and "similarity" in normalized), (
                    field_path
                )
                assert not any(part.startswith("score") for part in key_parts), (
                    field_path
                )
                assert not (
                    normalized.endswith("similarity") and "outcome" not in key_parts
                ), field_path
                if normalized in {"kind", "label", "metric", "metric_label", "title"}:
                    label = item.strip().lower() if isinstance(item, str) else ""
                    label_words = set(label.split())
                    assert not label_words.intersection(
                        {"canonical", "score", "milestone", "minefield"}
                    ), field_path
                    assert "reference similarity" not in label, field_path
                assert_outcome_only(item, field_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                assert_outcome_only(item, (*path, str(index)))

    assert_outcome_only(task_compare)
    exported_task = task_compare["tasks"][0]
    assert exported_task["outcome_similarity"] == pytest.approx(1.0)
    assert exported_task["routing"] == task["routing"]
    assert exported_task["generated_tool_events"] == task["generated_tool_events"]
    assert exported_task["messages"] == [transcript]
    assert exported_task["outcome_checks"] == [
        {"observed_messages": ["generated terminal action completed"]}
    ]
    assert exported_task["control_cache"]["record_ids"] == ["cache-record"]
    helper = task_compare["tool_summary"]["tools"][0]
    assert helper["called_subset_mean_outcome_delta"] == pytest.approx(1.0)
    assert helper["outcome_gains"] == 1
    assert focus_payload["summary"]["control_mean_similarity"] == pytest.approx(0.25)
    assert task["milestones"] == [{"score": 0.25}]


def test_task_compare_tool_birth_count_uses_registry_for_resumed_runs(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    control = run_root / "control" / "control_run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    (registry / "registry_manifest.json").write_text(
        json.dumps(
            {
                "tools": {
                    "retained_helper": {
                        "tool": {
                            "spec": {"description": "Retained before checkpoint."},
                            "code": "def retained_helper():\n    return {}\n",
                        }
                    },
                    "new_helper": {
                        "tool": {
                            "spec": {"description": "Accepted after resume."},
                            "code": "def new_helper():\n    return {}\n",
                        }
                    },
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_summary(
        control,
        [
            {"name": "retained", "similarity": 0.0, "outcome_similarity": 0.0},
            {"name": "new", "similarity": 0.0, "outcome_similarity": 0.0},
        ],
    )
    _write_summary(
        candidate,
        [
            {
                "name": "retained",
                "similarity": 1.0,
                "outcome_similarity": 1.0,
            },
            {"name": "new", "similarity": 1.0, "outcome_similarity": 1.0},
        ],
    )
    (candidate / "tool_birth_events.jsonl").write_text(
        json.dumps({"accepted": True, "tool_name": "new_helper"}) + "\n",
        encoding="utf-8",
    )
    (candidate / "reuse_events.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"scenario": "retained", "tool_name": "retained_helper"}),
                json.dumps({"scenario": "new", "tool_name": "new_helper"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (candidate / "scenario_tool_selection.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "scenario": "retained",
                        "generated_tools_visible": ["retained_helper"],
                        "generated_tools_called": ["retained_helper"],
                    }
                ),
                json.dumps(
                    {
                        "scenario": "new",
                        "generated_tools_visible": ["new_helper"],
                        "generated_tools_called": ["new_helper"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="online_build_full",
        status="running",
        phase="comparison",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        generation_enabled=True,
        base_tool_policy="upstream",
        scenario_count=2,
        control_dir=control,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    tool_summary = task_compare["tool_summary"]
    assert task_compare["summary"]["accepted_tools"] == 1
    assert tool_summary["generated_tool_birth_event_count"] == 1
    assert tool_summary["generated_tool_birth_count"] == 2
    assert tool_summary["registry_tool_count"] == 2
    assert tool_summary["tool_count"] == 2
    assert tool_summary["called_tool_count"] == 2


def test_task_compare_tool_summary_backfills_stale_helper_contribution_births(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    control = run_root / "control" / "control_run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    (registry / "registry_manifest.json").write_text(
        json.dumps(
            {
                "tools": {
                    "helper": {
                        "tool": {
                            "spec": {
                                "family": "test_family",
                                "description": "Original helper.",
                                "positive_triggers": ["called tasks"],
                                "generalization_rationale": "The original pattern recurs.",
                            },
                            "code": "def helper():\n    return {'ok': True}\n",
                        },
                        "code_hash": "hash-helper",
                    },
                    "late_helper": {
                        "tool": {
                            "spec": {
                                "family": "test_family",
                                "description": "Late helper.",
                                "positive_triggers": ["late tasks"],
                                "negative_triggers": ["unsafe task"],
                                "generalization_rationale": "The late pattern recurs.",
                            },
                            "code": "def late_helper():\n    return {'late': True}\n",
                        },
                        "code_hash": "hash-late",
                    },
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_summary(
        control,
        [{"name": "called", "similarity": 0.0, "outcome_similarity": 0.0}],
    )
    _write_summary(
        candidate,
        [{"name": "called", "similarity": 1.0, "outcome_similarity": 1.0}],
    )
    (candidate / "tool_birth_events.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"accepted": True, "tool_name": "helper"}),
                json.dumps({"accepted": True, "tool_name": "late_helper"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (candidate / "reuse_events.jsonl").write_text(
        json.dumps({"scenario": "called", "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (run_root / "helper_contribution_summary.json").write_text(
        json.dumps(
            {
                "registry_size": 1,
                "helpers": {
                    "helper": {
                        "origin": "newly_generated",
                        "visible_count": 1,
                        "called_count": 1,
                        "visible_not_called_count": 0,
                        "failed_attempt_count": 0,
                        "called_subset": {
                            "scenario_count": 1,
                            "mean_canonical_delta": 1.0,
                            "mean_outcome_delta": 1.0,
                            "canonical_gains": 1,
                            "canonical_regressions": 0,
                            "outcome_gains": 1,
                            "outcome_regressions": 0,
                            "outcome_preserved": 0,
                        },
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="online_build_full",
        status="running",
        phase="comparison",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        generation_enabled=True,
        base_tool_policy="upstream",
        scenario_count=2,
        control_dir=control,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    tool_summary = task_compare["tool_summary"]
    assert tool_summary["generated_tool_birth_count"] == 2
    assert tool_summary["tool_count"] == 2
    assert [tool["name"] for tool in tool_summary["tools"]] == [
        "helper",
        "late_helper",
    ]
    assert tool_summary["tools"][0]["code"].startswith("def helper")
    assert tool_summary["tools"][0]["code_hash"] == "hash-helper"
    assert "Original helper." in tool_summary["tools"][0]["plain_language_explanation"]
    assert (
        "Why it exists: The original pattern recurs."
        in tool_summary["tools"][0]["plain_language_explanation"]
    )
    assert tool_summary["tools"][1]["code"].startswith("def late_helper")
    assert tool_summary["tools"][1]["description"] == "Late helper."
    assert (
        "It should avoid tasks matching: unsafe task."
        in tool_summary["tools"][1]["plain_language_explanation"]
    )
    assert tool_summary["tools"][1]["decision"] == "accepted; no natural call yet"


def test_task_focus_balanced_summary_uses_only_complete_pairs() -> None:
    pairs = [
        {
            "control": {
                "status": "complete",
                "similarity": 0.2,
                "outcome_similarity": 0.4,
            },
            "candidate": {
                "status": "complete",
                "similarity": 1.0,
                "outcome_similarity": 0.9,
            },
        },
        {
            "control": {
                "status": "complete",
                "similarity": 1.0,
                "outcome_similarity": 0.6,
            },
            "candidate": {
                "status": "complete",
                "similarity": 0.5,
                "outcome_similarity": 0.3,
            },
        },
        {
            "control": {
                "status": "complete",
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            },
            "candidate": {"status": "running"},
        },
    ]

    summary = exporters._balanced_pair_summary(pairs)

    assert summary["balanced_completed"] == 2
    assert summary["balanced_control_mean_similarity"] == pytest.approx(0.6)
    assert summary["balanced_candidate_mean_similarity"] == pytest.approx(0.75)
    assert summary["balanced_delta"] == pytest.approx(0.15)
    assert summary["balanced_lift_percent"] == pytest.approx(25.0)
    assert summary["balanced_control_mean_outcome_similarity"] == pytest.approx(0.5)
    assert summary["balanced_candidate_mean_outcome_similarity"] == pytest.approx(0.6)
    assert summary["balanced_outcome_delta"] == pytest.approx(0.1)


def test_task_focus_arm_progress_prefers_run_scenario_count_over_subset_plan() -> None:
    progress = exporters._arm_progress_status(
        Path("run"),
        "control",
        {
            "scenario_count": 290,
            "planned_scenario_count": 321,
            "run_status": "running",
        },
        500,
    )

    assert progress["completed_count"] == 290
    assert progress["scenario_count"] == 500


def test_task_focus_exports_guardrail_evidence_and_left_aligned_tool_messages(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    scenario = "guardrail_only_case"
    _write_live_summary(
        candidate,
        [
            {
                "name": scenario,
                "similarity": 0.0,
                "turn_count": 3,
                "categories": ["INSUFFICIENT_INFORMATION"],
                "milestone_similarity": 1.0,
                "minefield_similarity": 1.0,
                "milestone_mapping": {},
                "minefield_mapping": {"0": [1, 1.0]},
            }
        ],
    )
    trajectory = candidate / "trajectories" / scenario
    trajectory.mkdir(parents=True)
    (trajectory / "conversation.json").write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": 'search_reminder({"reminder_timestamp_lowerbound": 1714435200})',
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_reminder",
                                "arguments": '{"reminder_timestamp_lowerbound": 1714435200}',
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "search_reminder",
                    "content": "[]",
                    "tool_details": {
                        "minefield_matches": [
                            {
                                "minefield_index": 0,
                                "minefield_similarity": 1.0,
                                "minefield": {
                                    "snapshot_constraints": [
                                        {
                                            "database_namespace": "SANDBOX",
                                            "target_dataframe": [
                                                {
                                                    "sender": "EXECUTION_ENVIRONMENT",
                                                    "recipient": "AGENT",
                                                    "tool_trace": json.dumps(
                                                        [
                                                            {
                                                                "tool_name": "search_reminder",
                                                                "arguments": {
                                                                    "reminder_timestamp_lowerbound": 0
                                                                },
                                                            }
                                                        ]
                                                    ),
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
                {
                    "role": "assistant",
                    "content": "I found no reminders.",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="running",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="all_tools",
        scenario_count=1,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    task = task_focus["tasks"][0]
    guardrail = task["minefields"][0]
    evaluation = task["evaluation"]

    assert task["milestones"] == []
    assert guardrail["triggered"] is True
    assert guardrail["target_lines"] == [
        "search_reminder(reminder_timestamp_lowerbound=0)"
    ]
    assert guardrail["observed_lines"] == [
        'search_reminder({"reminder_timestamp_lowerbound": 1714435200})',
        "search_reminder: []",
    ]
    assert "Guardrail 1 triggered:" in task["outcome"]["observed_evidence"]
    assert (
        "Guardrail 1: avoid search_reminder(reminder_timestamp_lowerbound=0)"
        in task["outcome"]["expected_truth"]
    )
    assert evaluation["blocked_by_guardrail"] is True
    assert evaluation["forbidden_triggered"] == 1
    assert evaluation["checks"][0]["kind"] == "forbidden"
    assert evaluation["checks"][0]["status"] == "triggered"

    html = (index.parent / "task_focus.html").read_text(encoding="utf-8")
    assert ".msg.tool { justify-content: flex-start; }" in html
    assert "Model Provided" in html
    assert "Correct Answer" in html


def test_task_focus_exports_required_check_from_database_update(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    scenario = "required_state_case"
    _write_live_summary(
        candidate,
        [
            {
                "name": scenario,
                "similarity": 1.0,
                "turn_count": 2,
                "categories": ["SINGLE_TOOL_CALL"],
                "milestone_similarity": 1.0,
                "minefield_similarity": 0.0,
                "milestone_mapping": {"0": [1, 1.0]},
                "minefield_mapping": {},
            }
        ],
    )
    trajectory = candidate / "trajectories" / scenario
    trajectory.mkdir(parents=True)
    (trajectory / "conversation.json").write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": 'add_reminder({"content": "Buy chocolate milk"})',
                    "tool_calls": [
                        {
                            "function": {
                                "name": "add_reminder",
                                "arguments": '{"content": "Buy chocolate milk"}',
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "add_reminder",
                    "content": "'abc'",
                    "tool_details": {
                        "database_update": {
                            "REMINDER": [
                                {
                                    "reminder_id": "abc",
                                    "content": "Buy chocolate milk",
                                    "creation_timestamp": 1777543533.802935,
                                    "reminder_timestamp": 1711141200.0,
                                    "latitude": None,
                                    "longitude": None,
                                }
                            ]
                        },
                        "milestone_matches": [
                            {
                                "milestone_index": 0,
                                "milestone_similarity": 1.0,
                                "milestone": {
                                    "snapshot_constraints": [
                                        {
                                            "database_namespace": "REMINDER",
                                            "snapshot_constraint": "addition_similarity",
                                            "reference_milestone_node_index": None,
                                            "target_dataframe": [
                                                {
                                                    "content": "Buy chocolate milk",
                                                    "reminder_timestamp": 1711141200.0,
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ],
                    },
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="complete",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="all_tools",
        scenario_count=1,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    check = task_focus["tasks"][0]["evaluation"]["checks"][0]

    assert check["kind"] == "required"
    assert check["status"] == "matched"
    assert check["observed"] == [
        "REMINDER: content=Buy chocolate milk, reminder_timestamp=1711141200"
    ]
    assert check["expected"] == [
        "REMINDER: content=Buy chocolate milk, reminder_timestamp=1711141200"
    ]


def test_task_focus_shows_missed_state_update_values_from_later_tool(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    scenario = "missed_reminder_state_case"
    _write_live_summary(
        candidate,
        [
            {
                "name": scenario,
                "similarity": 0.333,
                "turn_count": 4,
                "categories": ["STATE_DEPENDENCY"],
                "milestone_similarity": 0.333,
                "minefield_similarity": 0.0,
                "milestone_mapping": {"0": [1, 0.0]},
                "minefield_mapping": {},
            }
        ],
    )
    trajectory = candidate / "trajectories" / scenario
    trajectory.mkdir(parents=True)
    (trajectory / "conversation.json").write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "get_current_timestamp({})",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_current_timestamp",
                                "arguments": "{}",
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "get_current_timestamp",
                    "content": "1777640519.228731",
                    "tool_details": {
                        "milestone_matches": [
                            {
                                "milestone_index": 0,
                                "milestone_similarity": 0.0,
                                "milestone": {
                                    "snapshot_constraints": [
                                        {
                                            "database_namespace": "REMINDER",
                                            "snapshot_constraint": "addition_similarity",
                                            "target_dataframe": [
                                                {
                                                    "content": "Buy chocolate milk",
                                                    "reminder_timestamp": 1777755600.0,
                                                    "latitude": 37.323498,
                                                    "longitude": -122.039665,
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
                {
                    "role": "assistant",
                    "content": (
                        'add_reminder({"content": '
                        '"Buy chocolate milk at Whole Foods.", '
                        '"reminder_timestamp": 1777766400})'
                    ),
                    "tool_calls": [
                        {
                            "function": {
                                "name": "add_reminder",
                                "arguments": json.dumps(
                                    {
                                        "content": (
                                            "Buy chocolate milk at Whole Foods."
                                        ),
                                        "reminder_timestamp": 1777766400,
                                    }
                                ),
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "add_reminder",
                    "content": "'abc'",
                    "tool_details": {
                        "database_update": {
                            "REMINDER": [
                                {
                                    "reminder_id": "abc",
                                    "content": "Buy chocolate milk at Whole Foods.",
                                    "reminder_timestamp": 1777766400.0,
                                    "latitude": None,
                                    "longitude": None,
                                }
                            ]
                        }
                    },
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="complete",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="all_tools",
        scenario_count=1,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    check = task_focus["tasks"][0]["evaluation"]["checks"][0]

    assert check["kind"] == "required"
    assert check["status"] == "missed"
    assert check["observed"] == [
        (
            "REMINDER: content=Buy chocolate milk at Whole Foods., "
            "reminder_timestamp=1777766400, latitude=null, longitude=null"
        )
    ]
    assert check["expected"] == [
        (
            "REMINDER: content=Buy chocolate milk, "
            "reminder_timestamp=1777755600, latitude=37.323, longitude=-122.04"
        )
    ]


def test_task_focus_shows_wrong_boolean_state_update(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    scenario = "wrong_setting_case"
    _write_live_summary(
        candidate,
        [
            {
                "name": scenario,
                "similarity": 0.0,
                "turn_count": 2,
                "categories": ["STATE_DEPENDENCY"],
                "milestone_similarity": 0.0,
                "minefield_similarity": 0.0,
                "milestone_mapping": {"0": [1, 0.0]},
                "minefield_mapping": {},
            }
        ],
    )
    trajectory = candidate / "trajectories" / scenario
    trajectory.mkdir(parents=True)
    (trajectory / "conversation.json").write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": 'set_wifi_status({"on": false})',
                    "tool_calls": [
                        {
                            "function": {
                                "name": "set_wifi_status",
                                "arguments": '{"on": false}',
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "set_wifi_status",
                    "content": "None",
                    "tool_details": {
                        "database_update": {
                            "SETTING": [
                                {
                                    "device_id": "device",
                                    "wifi": False,
                                    "low_battery_mode": False,
                                }
                            ]
                        },
                        "milestone_matches": [
                            {
                                "milestone_index": 0,
                                "milestone_similarity": 0.0,
                                "milestone": {
                                    "snapshot_constraints": [
                                        {
                                            "database_namespace": "SETTING",
                                            "snapshot_constraint": "snapshot_similarity",
                                            "target_dataframe": [{"wifi": True}],
                                        }
                                    ]
                                },
                            }
                        ],
                    },
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="complete",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="all_tools",
        scenario_count=1,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    check = task_focus["tasks"][0]["evaluation"]["checks"][0]

    assert check["status"] == "missed"
    assert check["observed"] == ["SETTING: wifi=false"]
    assert check["expected"] == ["SETTING: wifi=true"]


def test_task_focus_uses_attempted_tool_call_for_missed_required_tool_trace(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    scenario = "missed_tool_trace_case"
    _write_live_summary(
        candidate,
        [
            {
                "name": scenario,
                "similarity": 0.0,
                "turn_count": 4,
                "categories": ["STATE_DEPENDENCY"],
                "milestone_similarity": 0.0,
                "minefield_similarity": 0.0,
                "milestone_mapping": {"0": [1, 0.0]},
                "minefield_mapping": {},
            }
        ],
    )
    trajectory = candidate / "trajectories" / scenario
    trajectory.mkdir(parents=True)
    (trajectory / "conversation.json").write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": 'search_stock({"query": "Apple"})',
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_stock",
                                "arguments": '{"query": "Apple"}',
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "set_wifi_status",
                    "content": "None",
                    "tool_details": {
                        "milestone_matches": [
                            {
                                "milestone_index": 0,
                                "milestone_similarity": 0.0,
                                "milestone": {
                                    "snapshot_constraints": [
                                        {
                                            "database_namespace": "SANDBOX",
                                            "snapshot_constraint": "snapshot_similarity",
                                            "target_dataframe": [
                                                {
                                                    "sender": "EXECUTION_ENVIRONMENT",
                                                    "recipient": "AGENT",
                                                    "tool_trace": json.dumps(
                                                        {
                                                            "tool_name": "search_stock",
                                                            "arguments": {
                                                                "query": "Apple"
                                                            },
                                                        }
                                                    ),
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
                {
                    "role": "assistant",
                    "content": 'search_stock({"query": "Apple"})',
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_stock",
                                "arguments": '{"query": "Apple"}',
                            }
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "search_stock",
                    "content": "PermissionError: missing API key",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="complete",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="all_tools",
        scenario_count=1,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    check = task_focus["tasks"][0]["evaluation"]["checks"][0]

    assert check["kind"] == "required"
    assert check["status"] == "missed"
    assert check["observed"] == [
        'search_stock({"query": "Apple"})',
        "search_stock: PermissionError: missing API key",
    ]


def test_task_focus_fallback_matches_partial_milestone_from_expected_text(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    candidate = run_root / "candidate" / "candidate_run"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "live_result_summary.json").write_text(
        json.dumps(
            {
                "per_scenario_results": [
                    {
                        "name": "partial_text_match_case",
                        "categories": ["STATE_DEPENDENCY"],
                        "milestone_similarity": 0.9140840412743819,
                        "minefield_similarity": 0.0,
                        "milestone_mapping": {"0": [1, 0.9140840412743819]},
                        "minefield_mapping": {},
                        "turn_count": 1,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    trajectory = candidate / "trajectories" / "partial_text_match_case"
    trajectory.mkdir(parents=True)
    (trajectory / "conversation.json").write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": 'The todo item you made yesterday is: **"Buy tickets for Merrily next week."**',
                    "assistant_details": {
                        "milestone_matches": [
                            {
                                "milestone_index": 0,
                                "milestone_similarity": 0.9140840412743819,
                                "milestone": {
                                    "snapshot_constraints": [
                                        {
                                            "database_namespace": "SANDBOX",
                                            "snapshot_constraint": "snapshot_similarity",
                                            "target_dataframe": [
                                                {
                                                    "sender": "AGENT",
                                                    "recipient": "USER",
                                                    "content": "Buy tickets for Merrily next week.",
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    registry = run_root / "registry"
    registry.mkdir(parents=True)
    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="complete",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13_05_02_2026_19_54_54",
        generation_enabled=False,
        base_tool_policy="upstream",
        scenario_count=1,
        candidate_dir=candidate,
        registry_dir=registry,
    )
    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )

    check = task_focus["tasks"][0]["evaluation"]["checks"][0]
    assert check["status"] == "partial"
    assert check["observed"] == [
        'The todo item you made yesterday is: **"Buy tickets for Merrily next week."**'
    ]


def test_task_focus_resolves_arm_roots_and_renders_paired_compare(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    control_root = run_root / "control"
    candidate_root = run_root / "candidate"
    control = control_root / "control_run"
    candidate = candidate_root / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    control_root.mkdir(parents=True, exist_ok=True)
    candidate_root.mkdir(parents=True, exist_ok=True)
    (control_root / "sage_ts_run_manifest.json").write_text(
        json.dumps({"scenario_names": ["paired_case"]}) + "\n",
        encoding="utf-8",
    )
    (candidate_root / "sage_ts_run_manifest.json").write_text(
        json.dumps({"scenario_names": ["paired_case"]}) + "\n",
        encoding="utf-8",
    )
    (run_root / "control_arm_status.json").write_text(
        json.dumps(
            {
                "arm": "control",
                "status": "complete",
                "completed_count": 1,
                "scenario_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_root / "candidate_arm_status.json").write_text(
        json.dumps(
            {
                "arm": "candidate",
                "status": "running",
                "completed_count": 0,
                "scenario_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_live_summary(
        control,
        [
            {
                "name": "paired_case",
                "similarity": 0.5,
                "turn_count": 2,
                "categories": ["STATE_DEPENDENCY"],
                "milestone_similarity": 0.5,
                "minefield_similarity": 0.0,
                "milestone_mapping": {"0": [0, 0.5]},
                "minefield_mapping": {},
            }
        ],
    )
    _write_live_summary(
        candidate,
        [
            {
                "name": "paired_case",
                "similarity": 1.0,
                "turn_count": 3,
                "categories": ["STATE_DEPENDENCY"],
                "milestone_similarity": 1.0,
                "minefield_similarity": 0.0,
                "milestone_mapping": {"0": [0, 1.0]},
                "minefield_mapping": {},
            }
        ],
    )
    for run_dir, final_answer in (
        (control, "Baseline answer"),
        (candidate, "SAGE answer"),
    ):
        trajectory = run_dir / "trajectories" / "paired_case"
        trajectory.mkdir(parents=True)
        (trajectory / "conversation.json").write_text(
            json.dumps(
                [
                    {"role": "user", "content": "Question"},
                    {"role": "assistant", "content": final_answer},
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    index = write_protocol_dashboard(
        run_root,
        mode="transfer_40",
        status="running",
        phase="paired",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="all_tools",
        scenario_count=1,
        control_dir=control_root / "sage_ts_run_manifest.json",
        candidate_dir=candidate_root,
        registry_dir=registry,
        control_label="Policy selection",
        candidate_label="Auto selection",
    )

    task_focus = json.loads(
        (index.parent / "task_focus_data.json").read_text(encoding="utf-8")
    )
    assert {task["phase"] for task in task_focus["tasks"]} == {"control", "candidate"}
    pair = task_focus["pairs"][0]
    assert pair["control"]["scenario"] == "paired_case"
    assert pair["candidate"]["scenario"] == "paired_case"
    assert task_focus["arm_progress"]["control"]["status"] == "complete"
    assert task_focus["arm_progress"]["control"]["completed_count"] == 1
    assert task_focus["arm_progress"]["control"]["scenario_count"] == 1
    assert task_focus["arm_progress"]["candidate"]["status"] == "running"
    assert task_focus["arm_progress"]["candidate"]["completed_count"] == 0
    assert task_focus["arm_progress"]["candidate"]["scenario_count"] == 1
    assert task_focus["arm_labels"] == {
        "control": "Policy selection",
        "candidate": "Auto selection",
    }
    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    assert task_compare["arm_labels"] == task_focus["arm_labels"]

    html = (index.parent / "task_focus.html").read_text(encoding="utf-8")
    assert "paired-check-grid" in html
    assert "paired-chat" in html
    assert "Baseline Progress" in html
    assert "SAGE Progress" in html
    assert "status-pair" in html
