# mypy: ignore-errors
import json
from dataclasses import replace

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from tests.unit.test_candidate_gate import _state_spec


def _write_failure_memory(path, *, status="active_failure"):
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "mechanism_id": "wrong_service_order",
                        "candidate_name": "state_helper",
                        "failure_symptoms": [
                            "helper repeats old service ordering failure"
                        ],
                        "suspected_root_cause": "state incomplete before helper call",
                        "unblock_conditions": ["material repair evidence"],
                        "status": status,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_failure_memory_blocks_unrepaired_mechanism(tmp_path) -> None:
    memory = tmp_path / "failure_memory.json"
    _write_failure_memory(memory)
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        known_failure_mechanisms_addressed=("wrong_service_order",),
        reason_tool_is_decisive="It compresses service readiness decisions safely.",
    )

    decision = evaluate_candidate_gate(spec, failure_memory_path=memory)

    assert not decision.allowed
    assert decision.reason.startswith("unresolved_failure_memory")


def test_same_name_rediscovery_allowed_when_materially_repaired(tmp_path) -> None:
    memory = tmp_path / "failure_memory.json"
    _write_failure_memory(memory)
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        known_failure_mechanisms_addressed=("wrong_service_order",),
        reason_tool_is_decisive="It materially repairs wrong_service_order by requiring complete state and avoiding duplicate setters.",
    )

    decision = evaluate_candidate_gate(spec, failure_memory_path=memory)

    assert decision.allowed
