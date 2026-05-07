# mypy: ignore-errors
import json
from pathlib import Path

import pytest

from sage_ts.dashboard import exporters
from sage_ts.dashboard.exporters import write_protocol_dashboard


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


def _write_live_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "live_result_summary.json").write_text(
        json.dumps({"per_scenario_results": rows}) + "\n",
        encoding="utf-8",
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


def test_open_dashboard_falls_back_to_macos_open(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        exporters,
        "ensure_dashboard_server",
        lambda *, port: calls.append(("server", port)),
    )
    monkeypatch.setattr(
        exporters,
        "dashboard_url",
        lambda index_path, *, port: f"http://127.0.0.1:{port}/dashboard/index.html",
    )
    monkeypatch.setattr(exporters.webbrowser, "open_new_tab", lambda url: False)
    monkeypatch.setattr(exporters.sys, "platform", "darwin")
    monkeypatch.setattr(
        exporters.subprocess,
        "Popen",
        lambda args, **_kwargs: calls.append(("open", args)),
    )

    url = exporters.open_dashboard(tmp_path / "index.html", port=5520)

    assert url == "http://127.0.0.1:5520/dashboard/index.html"
    assert ("server", 5520) in calls
    assert ("open", ["open", url]) in calls


def test_open_dashboard_always_uses_macos_open(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        exporters,
        "ensure_dashboard_server",
        lambda *, port: calls.append(("server", port)),
    )
    monkeypatch.setattr(
        exporters,
        "dashboard_url",
        lambda index_path, *, port: f"http://127.0.0.1:{port}/dashboard/index.html",
    )
    monkeypatch.setattr(exporters.webbrowser, "open_new_tab", lambda url: True)
    monkeypatch.setattr(exporters.sys, "platform", "darwin")
    monkeypatch.setattr(
        exporters.subprocess,
        "Popen",
        lambda args, **_kwargs: calls.append(("open", args)),
    )

    url = exporters.open_dashboard(tmp_path / "index.html", port=5520)

    assert url == "http://127.0.0.1:5520/dashboard/index.html"
    assert ("open", ["open", url]) in calls


def test_write_protocol_dashboard_exports_paired_data(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    control = run_root / "control" / "control_run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    _write_summary(
        control,
        [
            {
                "name": "a",
                "similarity": 0.2,
                "turn_count": 6,
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
    _write_summary(
        candidate,
        [
            {
                "name": "a",
                "similarity": 1.0,
                "turn_count": 4,
                "categories": ["CANONICALIZATION"],
            },
            {"name": "b", "similarity": 0.5, "turn_count": 5, "categories": []},
        ],
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
    assert "control source: cached" in (index.parent / "index.html").read_text(
        encoding="utf-8"
    )


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

    html = (index.parent / "task_focus.html").read_text(encoding="utf-8")
    assert "paired-check-grid" in html
    assert "paired-chat" in html
    assert "Baseline Progress" in html
    assert "SAGE Progress" in html
    assert "status-pair" in html
