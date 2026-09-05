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
    assert index.name == "task_compare.html"
    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    assert task_compare["scenario_count"] == 2
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
    assert not (index.parent / "index.html").exists()
    assert not (index.parent / "data.json").exists()
    assert not (index.parent / "task_focus.html").exists()
    assert not (index.parent / "task_focus_data.json").exists()


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


def test_task_compare_balanced_summary_uses_only_complete_pairs() -> None:
    pairs = [
        {
            "control": {
                "status": "complete",
                "outcome_similarity": 0.4,
            },
            "candidate": {
                "status": "complete",
                "outcome_similarity": 0.9,
            },
        },
        {
            "control": {
                "status": "complete",
                "outcome_similarity": 0.6,
            },
            "candidate": {
                "status": "complete",
                "outcome_similarity": 0.3,
            },
        },
        {
            "control": {
                "status": "complete",
                "outcome_similarity": 0.0,
            },
            "candidate": {"status": "running"},
        },
    ]

    summary = exporters._balanced_pair_summary(pairs)

    assert summary["balanced_completed"] == 2
    assert summary["balanced_control_mean_outcome_similarity"] == pytest.approx(0.5)
    assert summary["balanced_candidate_mean_outcome_similarity"] == pytest.approx(0.6)
    assert summary["balanced_outcome_delta"] == pytest.approx(0.1)


def test_task_compare_arm_progress_prefers_run_scenario_count_over_subset_plan() -> (
    None
):
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


def test_task_compare_resolves_arm_roots_and_renders_paired_compare(
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
                "outcome_similarity": 0.25,
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
                "outcome_similarity": 0.75,
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

    task_compare = json.loads(
        (index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    assert {task["phase"] for task in task_compare["tasks"]} == {
        "control",
        "candidate",
    }
    pair = task_compare["pairs"][0]
    assert pair["control"]["scenario"] == "paired_case"
    assert pair["candidate"]["scenario"] == "paired_case"
    assert task_compare["arm_progress"]["control"]["status"] == "complete"
    assert task_compare["arm_progress"]["control"]["completed_count"] == 1
    assert task_compare["arm_progress"]["control"]["scenario_count"] == 1
    assert task_compare["arm_progress"]["candidate"]["status"] == "running"
    assert task_compare["arm_progress"]["candidate"]["completed_count"] == 0
    assert task_compare["arm_progress"]["candidate"]["scenario_count"] == 1
    assert task_compare["arm_labels"] == {
        "control": "Policy selection",
        "candidate": "Auto selection",
    }
    detached_index = write_protocol_dashboard(
        run_root / "actor_selection_dashboard",
        mode="sage_auto_selection",
        status="complete",
        phase="policy_vs_auto_outcome_comparison",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=False,
        base_tool_policy="all_tools",
        scenario_count=1,
        control_dir=control,
        candidate_dir=candidate,
        registry_dir=registry,
        control_label="SAGE policy selection",
        candidate_label="SAGE auto selection",
    )
    detached_compare = json.loads(
        (detached_index.parent / "task_compare_data.json").read_text(encoding="utf-8")
    )
    detached_pair = detached_compare["pairs"][0]
    assert detached_pair["control"]["phase"] == "control"
    assert detached_pair["candidate"]["phase"] == "candidate"
    assert detached_compare["summary"]["balanced_completed"] == 1
    assert detached_compare["summary"][
        "balanced_control_mean_outcome_similarity"
    ] == pytest.approx(0.25)
    assert detached_compare["summary"][
        "balanced_candidate_mean_outcome_similarity"
    ] == pytest.approx(0.75)

    assert (index.parent / "task_compare.html").exists()
    assert not (index.parent / "task_focus.html").exists()
