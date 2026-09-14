#!/usr/bin/env python3
"""Verify a strict development-only lifecycle-repair cohort.

This verifier deliberately does not confer publication eligibility. It checks
fresh paired execution, lifecycle integrity, and predeclared outcome guards for
the exposed dev10/dev30 cohorts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from sage_ts.adapters.sage_run_adapter import (
    _side_effect_followup_failures,
    _tool_trace_events_from_execution_context,
)
from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from sage_ts.generation.complete_tools import native_action_tool_enabled
from sage_ts.orchestration.online_birth import (
    TERMINAL_RETIREMENT_TOMBSTONE_FILENAME,
    prohibited_repair_payload_paths,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.registry.validation_contracts import (
    VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
    ValidationContractBindingStore,
)
from sage_ts.validation.sandbox_validator import validate_generated_tool

try:
    from scripts import verify_publication_run as _strict_run_verifier
except ModuleNotFoundError:  # pragma: no cover - direct execution from scripts/
    import verify_publication_run as _strict_run_verifier

LIFECYCLE_USE_CASE_TOOL = "prepare_safe_action_or_abstain"
TRANSFER_MANIFEST_TYPE = "development_diagnostic_lifecycle_repair_transfer_dev30"
RETIRE_REPLACE_DEV10_MANIFEST_TYPE = (
    "development_diagnostic_lifecycle_retirement_successor_dev10"
)
RETIRE_REPLACE_TRANSFER_MANIFEST_TYPE = (
    "development_diagnostic_lifecycle_retirement_successor_transfer_dev30"
)
TRANSFER_MANIFEST_TYPES = frozenset(
    {TRANSFER_MANIFEST_TYPE, RETIRE_REPLACE_TRANSFER_MANIFEST_TYPE}
)
RETIRE_REPLACE_EVIDENCE_MODE = (
    "seeded_historical_v1_bounded_repair_retirement_and_successor_birth"
)
CONTACT_READINESS_SUCCESSOR = "assess_contact_removal_readiness"
CONTACT_READINESS_SUCCESSOR_CANONICAL_KEY = (
    "validation:assess_contact_removal_readiness"
)
LIFECYCLE_FAULT_FIXTURE_SHA256 = (
    "7677756340ccde07c5edb7b43003f68b5f363611d2cd935afdc7363e3bc33e8a"
)
PRESERVED_WORKING_TOOL_NAMES = (
    "relative_day_time_to_timestamp",
    "prepare_reminder_creation_args",
)
NEXT_WEEKDAY_TOOL_NAME = "next_weekday_time_to_timestamp"
WORKING_PATH_CANONICAL_KEYS = {
    "relative_day_time_to_timestamp": "canonicalizer:relative_day_time_timestamp",
    "prepare_reminder_creation_args": "composite:prepare_reminder_creation_args",
    NEXT_WEEKDAY_TOOL_NAME: "canonicalizer:next_weekday_time_to_timestamp",
}
WORKING_PATH_EVIDENCE = {
    "artifact": ("docs/sage_protocol/fixtures/paper_rep01_working_path_evidence.json"),
    "sha256": "840dcfeacd00dadea8e2ea54676326b51f12457af66317eef3e30ef5837d8a3f",
}
FIXTURE_TOOL_NAMES = (LIFECYCLE_USE_CASE_TOOL, *PRESERVED_WORKING_TOOL_NAMES)
PRESERVED_WORKING_TOOL_PROVENANCE: dict[str, Any] = {
    "claim_boundary": (
        "two historically successful generated tools preserved on overlapping "
        "reminder routes and a disjoint transfer cohort"
    ),
    "source_artifact": (
        "artifacts/publication_validation/paper_policy_final10_20260909_134651/"
        "rep01/native_action_registry/registry_manifest.json"
    ),
    "source_registry_sha256": (
        "5fe8323c69cb17b3c0e45f3ccf2bc3708583ab9d01a48e5ca2d4b5082686d653"
    ),
    "tools": {
        "relative_day_time_to_timestamp": {
            "version": 1,
            "retired": False,
            "code_hash": (
                "960acb0cd81a216c31e8ad3fe7f67cd4b4ec5436873615aea6d708089cf1d5ab"
            ),
            "public_spec_sha256": (
                "e8d8720e6c81e70469b9fc972ba82c3952528f2d7edc5d4834e9bc2574f93c95"
            ),
            "source_entry_sha256": (
                "34a186250638fe21c62dde6baef1af34381f9ce0d867e1e41f97d84362edbd0b"
            ),
        },
        "prepare_reminder_creation_args": {
            "version": 1,
            "retired": False,
            "code_hash": (
                "6aef8c1674e35bc274a75512399dfbc35809af6522a57800f129f6e4ec599292"
            ),
            "public_spec_sha256": (
                "288a07d0d51747cc6db95d5adf6408c5ab1b1a5c3c999680c073568ca50f9765"
            ),
            "source_entry_sha256": (
                "68ed674b51cd5b434417be9f5c727b8c65d2dd7b032c78bee5a4567be33179a9"
            ),
        },
    },
}
PINNED_LIFECYCLE_V1_CONTRACT_INDEX_SHA256 = (
    "5c53f48884ae7b02476df98a62cea47bdeb416dc8b04a36805660d62d2a9d72c"
)
PINNED_LIFECYCLE_V1_CONTRACTS: dict[str, dict[str, Any]] = {
    "prepare_reminder_creation_args": {
        "tool_name": "prepare_reminder_creation_args",
        "tool_version": 1,
        "tool_code_hash": (
            "6aef8c1674e35bc274a75512399dfbc35809af6522a57800f129f6e4ec599292"
        ),
        "tool_spec_hash": (
            "288a07d0d51747cc6db95d5adf6408c5ab1b1a5c3c999680c073568ca50f9765"
        ),
        "canonical_key": "composite:prepare_reminder_creation_args",
        "contract_hash": (
            "caeeb92e4fe201b5d3e16ecdf05c33cd0d9006f2add755cf9c59006361f9806e"
        ),
        "binding_blob_sha256": (
            "694f1a88f282fb3445985ca5174dca441b9310c676187013160b76fc489a6d3b"
        ),
    },
    LIFECYCLE_USE_CASE_TOOL: {
        "tool_name": LIFECYCLE_USE_CASE_TOOL,
        "tool_version": 1,
        "tool_code_hash": (
            "16262a4c141901a7ec4f7fb8d289ec8067c09473352df77b1a1fd262743386a9"
        ),
        "tool_spec_hash": (
            "1dd3336746267042c54b9ac0486afeaaf41ea9e0e4997128a56d7322f1792258"
        ),
        "canonical_key": "validation:prepare_safe_action_or_abstain",
        "contract_hash": (
            "74b6ecf95169da106c92ddcf4bc8a843725bcc4741cb49dd96a5386550a6df01"
        ),
        "binding_blob_sha256": (
            "eb9559a2f77e46a8b7b4228a68c0cf702be151360f54fcb3b55e8284b3a9aa2a"
        ),
    },
    "relative_day_time_to_timestamp": {
        "tool_name": "relative_day_time_to_timestamp",
        "tool_version": 1,
        "tool_code_hash": (
            "960acb0cd81a216c31e8ad3fe7f67cd4b4ec5436873615aea6d708089cf1d5ab"
        ),
        "tool_spec_hash": (
            "e8d8720e6c81e70469b9fc972ba82c3952528f2d7edc5d4834e9bc2574f93c95"
        ),
        "canonical_key": "canonicalizer:relative_day_time_timestamp",
        "contract_hash": (
            "800cf8677f9533df83fd005648cf83f4c3447813c07d212910da47b7d3a11cc4"
        ),
        "binding_blob_sha256": (
            "b56aab87e514929c60e01205bebb0d566740a54f05ee59683357e2fa14921ace"
        ),
    },
}
DEV10_ORDER = (
    "remove_contact_by_phone_no_search_contacts_insufficient_information",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_tool_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_arg_type_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_tool_name_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_all_tools",
    "add_reminder_content_and_week_delta_and_time",
    "add_reminder_content_and_weekday_delta_and_time",
    "search_phone_number_with_name",
)
DEV30_ORDER = (
    "remove_contact_by_phone_no_search_contacts_insufficient_information_10_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_10_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_arg_type_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_tool_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_tool_name_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_all_tools",
    "find_days_till_holiday_insufficient_information_10_distraction_tools",
    "find_days_till_holiday_insufficient_information_3_distraction_tools_tool_name_scrambled",
    "find_days_till_holiday_insufficient_information",
    "find_days_till_holiday_insufficient_information_3_distraction_tools",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_10_distraction_tools",
    "remove_contact_by_phone_no_remove_contact_insufficient_information",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_arg_type_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_tool_description_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_tool_name_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_all_tools",
    "modify_contact_with_message_recency_insufficient_information_10_distraction_tools",
    "modify_contact_with_message_recency_insufficient_information_3_distraction_tools_tool_description_scrambled",
    "search_reminder_with_creation_recency_yesterday_insufficient_information_10_distraction_tools",
    "search_reminder_with_creation_recency_yesterday_insufficient_information_3_distraction_tools_arg_description_scrambled",
    "search_reminder_with_creation_recency_yesterday_insufficient_information_implicit",
    "add_reminder_content_and_week_delta_and_time_3_distraction_tools_arg_description_scrambled",
    "add_reminder_content_and_weekday_delta_and_time_alt_3_distraction_tools",
    "search_phone_number_with_name_10_distraction_tools",
    "search_phone_number_with_name_3_distraction_tools_tool_description_scrambled",
)

DEV10_WORKING_TOOL_PATHS = {
    DEV10_ORDER[7]: (
        "relative_day_time_to_timestamp",
        "prepare_reminder_creation_args",
    ),
    DEV10_ORDER[8]: (
        NEXT_WEEKDAY_TOOL_NAME,
        "prepare_reminder_creation_args",
    ),
}
DEV30_WORKING_TOOL_PATHS = {
    DEV30_ORDER[26]: (
        "relative_day_time_to_timestamp",
        "prepare_reminder_creation_args",
    ),
    DEV30_ORDER[27]: (
        NEXT_WEEKDAY_TOOL_NAME,
        "prepare_reminder_creation_args",
    ),
}


def _working_overlap_gate_contract(
    *, role: str, expected_paths: dict[str, tuple[str, ...]]
) -> dict[str, Any]:
    return {
        "role": role,
        "expected_tool_paths": {
            scenario_name: list(tool_names)
            for scenario_name, tool_names in expected_paths.items()
        },
        "preserved_tools_exercised_across_cohort": list(PRESERVED_WORKING_TOOL_NAMES),
        "successor_contracts": {
            NEXT_WEEKDAY_TOOL_NAME: WORKING_PATH_CANONICAL_KEYS[NEXT_WEEKDAY_TOOL_NAME]
        },
        "minimum": len(expected_paths),
        "total": len(expected_paths),
    }


def _order_sha256(names: tuple[str, ...] | list[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


COHORT_SPECS: dict[str, dict[str, Any]] = {
    "development_diagnostic_lifecycle_repair_dev10": {
        "order": DEV10_ORDER,
        "order_sha256": "b59acee1559e254551ffe783acdaf351b45c4b6977b4a4bb990229afe733cf0e",
        "roles": {
            "repair_target": DEV10_ORDER[:7],
            "working_generated_overlap": DEV10_ORDER[7:9],
            "unrelated_native_preservation": DEV10_ORDER[9:],
        },
        "safe_role": "repair_target",
        "contact_role": "repair_target",
        "safe_visible_called_minimum": 7,
        "safe_exact_minimum": 6,
        "contact_exact_no_remove_minimum": 6,
        "working_overlap_minimum": 2,
        "working_overlap_expected_tool_paths": DEV10_WORKING_TOOL_PATHS,
        "unrelated_preservation_minimum": 1,
        "overall_exact_minimum": 9,
        "future_v2_exact_minimum": 6,
        "future_v2_success_flip_minimum": 1,
        "predeclared_gates": {
            "safe_abstain_visible_and_called": {
                "role": "repair_target",
                "minimum": 7,
                "total": 7,
            },
            "safe_abstain_exact_without_forbidden_remove": {
                "role": "repair_target",
                "minimum": 6,
                "total": 7,
            },
            "working_generated_overlap_visible_called_exact_failure_free": (
                _working_overlap_gate_contract(
                    role="working_generated_overlap",
                    expected_paths=DEV10_WORKING_TOOL_PATHS,
                )
            ),
            "unrelated_native_preservation_exact_nonregressing_fixture_hidden": {
                "role": "unrelated_native_preservation",
                "minimum": 1,
                "total": 1,
            },
            "working_generated_entries_unchanged": {"required": True},
            "overall_exact_outcomes": {"minimum": 9, "total": 10},
            "before_after": {
                "trigger_version": 1,
                "trigger_outcome_less_than": 1.0,
                "future_version": 2,
                "minimum_future_exact_successes": 6,
                "minimum_future_success_flips": 1,
            },
        },
    },
    "development_diagnostic_lifecycle_repair_dev30": {
        "order": DEV30_ORDER,
        "order_sha256": "4ab88c1b5c110b0681eb64763f8ca7870fba8b23271a980edf02d40a8424c39f",
        "roles": {
            "safe_abstain_confirmation": DEV30_ORDER[:26],
            "cross_family_safe_abstain": DEV30_ORDER[9:13],
            "contact_repair_confirmation": DEV30_ORDER[:9],
            "working_generated_overlap": DEV30_ORDER[26:28],
            "unrelated_native_preservation": DEV30_ORDER[28:],
        },
        "safe_role": "safe_abstain_confirmation",
        "contact_role": "contact_repair_confirmation",
        "cross_family_role": "cross_family_safe_abstain",
        "safe_visible_called_minimum": 26,
        "safe_exact_minimum": 21,
        "contact_exact_no_remove_minimum": 8,
        "working_overlap_minimum": 2,
        "working_overlap_expected_tool_paths": DEV30_WORKING_TOOL_PATHS,
        "unrelated_preservation_minimum": 2,
        "overall_exact_minimum": 25,
        "future_v2_exact_minimum": 21,
        "future_v2_success_flip_minimum": 1,
        "predeclared_gates": {
            "safe_abstain_visible_and_called": {
                "role": "safe_abstain_confirmation",
                "minimum": 26,
                "total": 26,
            },
            "contact_exact_without_forbidden_remove": {
                "role": "contact_repair_confirmation",
                "minimum": 8,
                "total": 9,
            },
            "insufficiency_exact": {
                "role": "safe_abstain_confirmation",
                "minimum": 21,
                "total": 26,
            },
            "working_generated_overlap_visible_called_exact_failure_free": (
                _working_overlap_gate_contract(
                    role="working_generated_overlap",
                    expected_paths=DEV30_WORKING_TOOL_PATHS,
                )
            ),
            "unrelated_native_preservation_exact_nonregressing_fixture_hidden": {
                "role": "unrelated_native_preservation",
                "minimum": 2,
                "total": 2,
            },
            "working_generated_entries_unchanged": {"required": True},
            "overall_exact_outcomes": {"minimum": 25, "total": 30},
            "before_after": {
                "trigger_version": 1,
                "trigger_outcome_less_than": 1.0,
                "future_version": 2,
                "minimum_future_exact_successes": 21,
                "minimum_future_success_flips": 1,
            },
        },
    },
    TRANSFER_MANIFEST_TYPE: {
        "order": DEV30_ORDER,
        "order_sha256": "4ab88c1b5c110b0681eb64763f8ca7870fba8b23271a980edf02d40a8424c39f",
        "roles": {
            "safe_abstain_confirmation": DEV30_ORDER[:26],
            "contact_repair_confirmation": DEV30_ORDER[:9],
            "working_generated_overlap": DEV30_ORDER[26:28],
            "unrelated_native_preservation": DEV30_ORDER[28:],
        },
        "safe_role": "safe_abstain_confirmation",
        "contact_role": "contact_repair_confirmation",
        "safe_visible_called_minimum": 26,
        "safe_exact_minimum": 21,
        "contact_exact_no_remove_minimum": 8,
        "working_overlap_minimum": 2,
        "working_overlap_expected_tool_paths": DEV30_WORKING_TOOL_PATHS,
        "unrelated_preservation_minimum": 2,
        "overall_exact_minimum": 25,
        "future_v2_success_flip_minimum": 1,
        "predeclared_gates": {
            "exact_promoted_registry_transfer": {"required": True},
            "registry_unchanged_after_transfer": {"required": True},
            "safe_abstain_visible_and_called": {
                "role": "safe_abstain_confirmation",
                "minimum": 26,
                "total": 26,
            },
            "contact_exact_without_forbidden_remove": {
                "role": "contact_repair_confirmation",
                "minimum": 8,
                "total": 9,
            },
            "insufficiency_exact": {
                "role": "safe_abstain_confirmation",
                "minimum": 21,
                "total": 26,
            },
            "fresh_control_success_flips": {
                "role": "safe_abstain_confirmation",
                "minimum": 1,
                "total": 26,
            },
            "working_generated_overlap_visible_called_exact_failure_free": (
                _working_overlap_gate_contract(
                    role="working_generated_overlap",
                    expected_paths=DEV30_WORKING_TOOL_PATHS,
                )
            ),
            "unrelated_native_preservation_exact_nonregressing_fixture_hidden": {
                "role": "unrelated_native_preservation",
                "minimum": 2,
                "total": 2,
            },
            "working_generated_entries_unchanged": {"required": True},
            "overall_exact_outcomes": {"minimum": 25, "total": 30},
        },
    },
    RETIRE_REPLACE_DEV10_MANIFEST_TYPE: {
        "order": DEV10_ORDER,
        "order_sha256": "b59acee1559e254551ffe783acdaf351b45c4b6977b4a4bb990229afe733cf0e",
        "roles": {
            "repair_trigger": DEV10_ORDER[:1],
            "successor_confirmation": DEV10_ORDER[1:7],
            "contact_repair_confirmation": DEV10_ORDER[1:7],
            "working_generated_overlap": DEV10_ORDER[7:9],
            "unrelated_native_preservation": DEV10_ORDER[9:],
        },
        "safe_role": "successor_confirmation",
        "contact_role": "contact_repair_confirmation",
        "safe_visible_called_minimum": 6,
        "safe_exact_minimum": 5,
        "contact_exact_no_remove_minimum": 5,
        "working_overlap_minimum": 2,
        "working_overlap_expected_tool_paths": DEV10_WORKING_TOOL_PATHS,
        "unrelated_preservation_minimum": 1,
        "overall_exact_minimum": 8,
        "retirement_successor_transition": {
            "source_tool_name": LIFECYCLE_USE_CASE_TOOL,
            "source_tool_version": 1,
            "trigger_role": "repair_trigger",
            "repair_kind": "implementation",
            "trigger_reason_code": "deterministic_public_contract_failure",
            "bounded_repair_attempt_count": 7,
            "terminal_acknowledgement_status": "rejected",
            "terminal_retirement_reason": "bounded_repair_failed_validation",
            "successors": {
                CONTACT_READINESS_SUCCESSOR: {
                    "canonical_key": CONTACT_READINESS_SUCCESSOR_CANONICAL_KEY,
                    "version": 1,
                    "role": "successor_confirmation",
                    "minimum_visible_and_called": 6,
                    "minimum_exact_successes": 5,
                    "minimum_success_flips": 1,
                }
            },
            "exact_new_validation_successor_set": True,
        },
        "predeclared_gates": {
            "source_v1_failure_bounded_repair_terminal_retirement": {
                "source_tool_name": LIFECYCLE_USE_CASE_TOOL,
                "source_tool_version": 1,
                "trigger_role": "repair_trigger",
                "trigger_outcome_less_than": 1.0,
                "repair_kind": "implementation",
                "trigger_reason_code": "deterministic_public_contract_failure",
                "bounded_repair_attempt_count": 7,
                "terminal_acknowledgement_status": "rejected",
                "terminal_retirement_reason": "bounded_repair_failed_validation",
            },
            "exact_validated_successor_set": {
                "tools": {
                    CONTACT_READINESS_SUCCESSOR: {
                        "canonical_key": CONTACT_READINESS_SUCCESSOR_CANONICAL_KEY,
                        "version": 1,
                        "role": "successor_confirmation",
                        "minimum_visible_and_called": 6,
                        "minimum_exact_successes": 5,
                        "minimum_success_flips": 1,
                    }
                },
                "exact_new_validation_successor_set": True,
            },
            "working_generated_overlap_visible_called_exact_failure_free": (
                _working_overlap_gate_contract(
                    role="working_generated_overlap",
                    expected_paths=DEV10_WORKING_TOOL_PATHS,
                )
            ),
            "unrelated_native_preservation_exact_nonregressing_fixture_hidden": {
                "role": "unrelated_native_preservation",
                "minimum": 1,
                "total": 1,
            },
            "working_generated_entries_unchanged": {"required": True},
            "overall_exact_outcomes": {"minimum": 8, "total": 10},
        },
    },
    RETIRE_REPLACE_TRANSFER_MANIFEST_TYPE: {
        "order": DEV30_ORDER,
        "order_sha256": "4ab88c1b5c110b0681eb64763f8ca7870fba8b23271a980edf02d40a8424c39f",
        "roles": {
            "successor_confirmation": DEV30_ORDER[:9],
            "contact_repair_confirmation": DEV30_ORDER[:9],
            "working_generated_overlap": DEV30_ORDER[26:28],
            "unrelated_native_preservation": DEV30_ORDER[28:],
        },
        "safe_role": "successor_confirmation",
        "contact_role": "contact_repair_confirmation",
        "safe_visible_called_minimum": 8,
        "safe_exact_minimum": 8,
        "contact_exact_no_remove_minimum": 8,
        "working_overlap_minimum": 2,
        "working_overlap_expected_tool_paths": DEV30_WORKING_TOOL_PATHS,
        "unrelated_preservation_minimum": 2,
        "overall_exact_minimum": 12,
        "source_manifest_type": RETIRE_REPLACE_DEV10_MANIFEST_TYPE,
        "retirement_successor_transition": {
            "source_tool_name": LIFECYCLE_USE_CASE_TOOL,
            "source_tool_version": 1,
            "successors": {
                CONTACT_READINESS_SUCCESSOR: {
                    "canonical_key": CONTACT_READINESS_SUCCESSOR_CANONICAL_KEY,
                    "version": 1,
                    "role": "successor_confirmation",
                    "minimum_visible_and_called": 8,
                    "minimum_exact_successes": 8,
                    "minimum_success_flips": 1,
                }
            },
            "exact_new_validation_successor_set": True,
        },
        "predeclared_gates": {
            "exact_retired_source_and_promoted_successor_registry_transfer": {
                "required": True
            },
            "registry_unchanged_after_transfer": {"required": True},
            "exact_validated_successor_set": {
                "tools": {
                    CONTACT_READINESS_SUCCESSOR: {
                        "canonical_key": CONTACT_READINESS_SUCCESSOR_CANONICAL_KEY,
                        "version": 1,
                        "role": "successor_confirmation",
                        "minimum_visible_and_called": 8,
                        "minimum_exact_successes": 8,
                        "minimum_success_flips": 1,
                    }
                },
                "exact_new_validation_successor_set": True,
            },
            "working_generated_overlap_visible_called_exact_failure_free": (
                _working_overlap_gate_contract(
                    role="working_generated_overlap",
                    expected_paths=DEV30_WORKING_TOOL_PATHS,
                )
            ),
            "unrelated_native_preservation_exact_nonregressing_fixture_hidden": {
                "role": "unrelated_native_preservation",
                "minimum": 2,
                "total": 2,
            },
            "working_generated_entries_unchanged": {"required": True},
            "overall_exact_outcomes": {"minimum": 12, "total": 30},
        },
    },
}


def _latest_run_root(search_root: Path) -> Path:
    manifests = sorted(
        search_root.rglob("protocol_manifest.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not manifests:
        raise ValueError(f"No protocol_manifest.json found under {search_root}")
    return manifests[-1].parent


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_rows(run_dir: Path) -> list[dict[str, Any]]:
    for filename in ("result_summary.json", "live_result_summary.json"):
        path = run_dir / filename
        if not path.exists():
            continue
        payload = _load_json(path)
        if isinstance(payload, list):
            return [dict(row) for row in payload if isinstance(row, dict)]
        rows = payload.get("per_scenario_results")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    raise ValueError(f"No result rows found in {run_dir}")


def _outcome(row: dict[str, Any]) -> float | None:
    value = row.get("outcome_similarity")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    ):
        return float(value)
    return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _declared_path_is_symlink(run_root: Path, value: Any) -> bool:
    """Inspect every lexical interpretation before the shared resolver follows it."""

    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value)
    candidates = (
        (path,)
        if path.is_absolute()
        else (
            _strict_run_verifier.REPO_ROOT / path,
            Path.cwd() / path,
            run_root / path,
        )
    )
    return any(candidate.is_symlink() for candidate in candidates)


def _verified_protocol_event_rows(
    *,
    run_root: Path,
    protocol: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the manifest-pinned, append-complete launcher event journal."""

    journal = protocol.get("protocol_event_journal")
    if journal is None:
        raise ValueError(
            "Lifecycle development verification requires a sealed protocol "
            "event journal."
        )
    if not isinstance(journal, dict):
        raise ValueError("Protocol event journal declaration is malformed.")
    if journal.get("schema_version") != 1:
        raise ValueError("Protocol event journal schema version is not 1.")
    if journal.get("append_closed_before_protocol_manifest") is not True:
        raise ValueError("Protocol event journal was not sealed before the manifest.")

    declared_journal_path = journal.get("path")
    if _declared_path_is_symlink(run_root, declared_journal_path):
        raise ValueError("Protocol event journal must not be a symbolic link.")

    artifact_root = _strict_run_verifier._resolve_declared_path(
        run_root,
        journal.get("artifact_root"),
        "protocol_event_journal.artifact_root",
    )
    expected_path = (artifact_root / "events" / "latest.jsonl").resolve()
    journal_path = _strict_run_verifier._resolve_declared_path(
        run_root,
        declared_journal_path,
        "protocol_event_journal.path",
        required_parent=artifact_root / "events",
    )
    if journal_path != expected_path:
        raise ValueError("Protocol event journal is not the sealed latest.jsonl file.")
    if not journal_path.is_file():
        raise ValueError("Protocol event journal is missing.")

    expected_sha256 = journal.get("sha256")
    observed_sha256 = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    if (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        or expected_sha256 != observed_sha256
    ):
        raise ValueError("Protocol event journal digest does not match the manifest.")
    expected_count = journal.get("event_count")
    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count < 1
    ):
        raise ValueError("Protocol event journal count is invalid.")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        journal_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(
                "Protocol event journal contains a non-object row at line "
                f"{line_number}."
            )
        rows.append(value)
    if len(rows) != expected_count:
        raise ValueError("Protocol event journal count does not match the manifest.")
    return rows, {
        "mode": "sealed_protocol_event_journal",
        "path": str(journal_path),
        "sha256": observed_sha256,
        "event_count": len(rows),
        "sealed": True,
    }


def _event_path_matches(run_root: Path, value: Any, expected: Path) -> bool:
    try:
        resolved = _strict_run_verifier._resolve_declared_path(
            run_root,
            value,
            "protocol event path",
        )
    except ValueError:
        return False
    return resolved == expected.resolve()


def _manifest_task_names(
    manifest: dict[str, Any], split: str = "full_benchmark"
) -> tuple[str, ...]:
    splits = manifest.get("splits")
    rows = splits.get(split) if isinstance(splits, dict) else None
    if not isinstance(rows, list):
        return ()
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            return ()
        name = str(row["name"])
        if not name:
            return ()
        names.append(name)
    return tuple(names)


def _role_names(manifest: dict[str, Any], role: str) -> tuple[str, ...]:
    roles = manifest.get("validation_roles")
    values = roles.get(role) if isinstance(roles, dict) else None
    if not isinstance(values, list) or any(
        not isinstance(item, str) or not item for item in values
    ):
        return ()
    return tuple(values)


def _selection_has_tool(row: dict[str, Any], field: str, tool_name: str) -> bool:
    values = row.get(field)
    return isinstance(values, list) and tool_name in values


def _selection_has_any_tool(
    row: dict[str, Any], field: str, tool_names: tuple[str, ...]
) -> bool:
    return any(_selection_has_tool(row, field, name) for name in tool_names)


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _registry_entry_identity(
    entry: Any,
    *,
    expected_name: str,
) -> dict[str, Any] | None:
    """Return the immutable identity of one well-formed generated-tool entry."""

    if not isinstance(entry, dict):
        return None
    tool = entry.get("tool")
    spec = tool.get("spec") if isinstance(tool, dict) else None
    code = tool.get("code") if isinstance(tool, dict) else None
    version = entry.get("version")
    retired = entry.get("retired")
    stored_code_hash = entry.get("code_hash")
    if (
        not isinstance(tool, dict)
        or not isinstance(spec, dict)
        or spec.get("tool_name") != expected_name
        or not isinstance(code, str)
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(retired, bool)
        or not isinstance(stored_code_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", stored_code_hash) is None
        or hashlib.sha256(code.encode("utf-8")).hexdigest() != stored_code_hash
    ):
        return None
    immutable_entry = {
        key: value
        for key, value in entry.items()
        if key not in {"reuse_count", "success_flips"}
    }
    return {
        "tool_name": expected_name,
        "version": version,
        "retired": retired,
        "code_hash": stored_code_hash,
        "public_spec_sha256": _canonical_json_sha256(spec),
        "immutable_entry_sha256": _canonical_json_sha256(immutable_entry),
    }


def _working_tool_failure_free(
    row: dict[str, Any],
    *,
    include_actor_followthrough: bool,
) -> bool:
    return _tools_failure_free(
        row,
        tool_names=PRESERVED_WORKING_TOOL_NAMES,
        include_actor_followthrough=include_actor_followthrough,
    )


def _tools_failure_free(
    row: dict[str, Any],
    *,
    tool_names: tuple[str, ...],
    include_actor_followthrough: bool,
) -> bool:
    fields = ["generated_tools_failed", "generated_tool_contract_failures"]
    if include_actor_followthrough:
        fields.append("actor_followthrough_failures")
    for field in fields:
        values = row.get(field)
        if not isinstance(values, list):
            return False
        if set(values) & set(tool_names):
            return False
    return True


def _checkpoint_contract_identity(
    *,
    candidate_dir: Path,
    completed_count: int,
    scenario_name: str,
    tool_name: str,
    expected_version: int,
) -> dict[str, Any] | None:
    """Return replayed call-time contract evidence for one expected path tool."""

    canonical_key = WORKING_PATH_CANONICAL_KEYS.get(tool_name)
    if canonical_key is None:
        return None
    checkpoint_dir = _checkpoint_directory(
        candidate_dir,
        completed_count=completed_count,
        scenario_name=scenario_name,
    )
    try:
        store = RegistryStore(checkpoint_dir)
        entry = store.get(tool_name)
        if (
            entry is None
            or entry.retired
            or entry.version != expected_version
            or not entry.code_hash_verified
        ):
            return None
        binding_store = ValidationContractBindingStore(checkpoint_dir)
        binding, _error = binding_store.resolve(entry)
        if binding is None or binding.canonical_key != canonical_key:
            return None
        replay = validate_generated_tool(
            entry.tool,
            binding.observation.validation_examples,
        )
        if not replay.accepted or replay != entry.validation:
            return None
        return {
            "tool_name": binding.tool_name,
            "tool_version": binding.tool_version,
            "canonical_key": binding.canonical_key,
            "contract_hash": binding.contract_hash,
            "tool_code_hash": binding.tool_code_hash,
            "tool_spec_hash": binding.tool_spec_hash,
            "validation_replayed": True,
        }
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _working_overlap_path_evidence(
    *,
    candidate_dir: Path,
    scenario_order: tuple[str, ...],
    scenario_name: str,
    expected_tools: tuple[str, ...],
    candidate_by_name: dict[str, dict[str, Any]],
    control_by_name: dict[str, dict[str, Any]],
    selection_by_name: dict[str, dict[str, Any]],
    feedback_by_name: dict[str, dict[str, Any]] | None,
    trajectory_row: dict[str, tuple[str, ...]] | None,
    side_effect_failures: set[str] | None = None,
) -> dict[str, Any]:
    """Audit one historically pinned working-tool path without redundant calls."""

    candidate = candidate_by_name.get(scenario_name)
    control = control_by_name.get(scenario_name)
    selection = selection_by_name.get(scenario_name)
    feedback = (
        feedback_by_name.get(scenario_name)
        if isinstance(feedback_by_name, dict)
        else None
    )
    require_feedback = feedback_by_name is not None
    selection_versions = (
        selection.get("generated_tool_versions")
        if isinstance(selection, dict)
        else None
    )
    expected_versions: dict[str, int] = {}
    versions_valid = bool(
        isinstance(selection_versions, dict)
        and set(selection_versions) == set(expected_tools)
    )
    if isinstance(selection_versions, dict):
        for tool_name in expected_tools:
            version = selection_versions.get(tool_name)
            if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
                or (tool_name in PRESERVED_WORKING_TOOL_NAMES and version != 1)
            ):
                versions_valid = False
                continue
            expected_versions[tool_name] = version

    def _unique_string_list(row: Any, field: str) -> list[str] | None:
        values = row.get(field) if isinstance(row, dict) else None
        if (
            not isinstance(values, list)
            or any(not isinstance(item, str) or not item for item in values)
            or len(values) != len(set(values))
        ):
            return None
        return values

    def _row_has_expected_path(row: Any) -> bool:
        visible = _unique_string_list(row, "generated_tools_visible")
        attempted = _unique_string_list(row, "generated_tools_attempted")
        called = _unique_string_list(row, "generated_tools_called")
        versions = row.get("generated_tool_versions") if isinstance(row, dict) else None
        return bool(
            isinstance(row, dict)
            and row.get("exception_type") is None
            and visible is not None
            and set(visible) == set(expected_tools)
            and attempted == list(expected_tools)
            and called == list(expected_tools)
            and isinstance(versions, dict)
            and set(versions) == set(expected_tools)
        )

    trajectory_path_present = bool(
        isinstance(trajectory_row, dict)
        and set(trajectory_row.get("generated_tools_visible", ()))
        == set(expected_tools)
        and tuple(trajectory_row.get("generated_tools_attempted", ())) == expected_tools
        and tuple(trajectory_row.get("generated_tools_called", ())) == expected_tools
    )

    selection_path_present = _row_has_expected_path(selection)
    feedback_path_present = (
        _row_has_expected_path(feedback) if require_feedback else True
    )
    feedback_versions_match = True
    if require_feedback:
        feedback_versions = (
            feedback.get("generated_tool_versions")
            if isinstance(feedback, dict)
            else None
        )
        feedback_versions_match = bool(
            isinstance(feedback_versions, dict)
            and set(feedback_versions) == set(expected_tools)
            and all(
                feedback_versions.get(tool_name) == expected_versions.get(tool_name)
                for tool_name in expected_tools
            )
        )
    selection_failure_free = bool(
        isinstance(selection, dict)
        and selection.get("generated_tools_failed") == []
        and selection.get("generated_tool_contract_failures") == []
    )
    feedback_failure_free = bool(
        not require_feedback
        or (
            isinstance(feedback, dict)
            and feedback.get("generated_tools_failed") == []
            and feedback.get("generated_tool_contract_failures") == []
            and feedback.get("actor_followthrough_failures") == []
        )
    )
    safe_fixture_hidden = bool(
        isinstance(selection, dict)
        and not _selection_has_tool(
            selection, "generated_tools_visible", LIFECYCLE_USE_CASE_TOOL
        )
        and not _selection_has_tool(
            selection, "generated_tools_called", LIFECYCLE_USE_CASE_TOOL
        )
        and (
            not require_feedback
            or (
                isinstance(feedback, dict)
                and not _selection_has_tool(
                    feedback, "generated_tools_visible", LIFECYCLE_USE_CASE_TOOL
                )
                and not _selection_has_tool(
                    feedback, "generated_tools_called", LIFECYCLE_USE_CASE_TOOL
                )
            )
        )
    )
    exact_nonregressing = bool(
        isinstance(candidate, dict)
        and isinstance(control, dict)
        and _exact_outcome(candidate)
        and (_outcome(candidate) or 0.0) >= (_outcome(control) or 0.0)
    )
    contract_evidence: dict[str, dict[str, Any]] = {}
    if scenario_name in scenario_order and versions_valid:
        completed_count = scenario_order.index(scenario_name) + 1
        for tool_name, version in expected_versions.items():
            identity = _checkpoint_contract_identity(
                candidate_dir=candidate_dir,
                completed_count=completed_count,
                scenario_name=scenario_name,
                tool_name=tool_name,
                expected_version=version,
            )
            if identity is not None:
                contract_evidence[tool_name] = identity
    contracts_valid = set(contract_evidence) == set(expected_tools)
    side_effect_failure_free = not bool(
        (side_effect_failures or set()) & set(expected_tools)
    )
    passed = all(
        (
            exact_nonregressing,
            versions_valid,
            selection_path_present,
            feedback_path_present,
            trajectory_path_present,
            feedback_versions_match,
            selection_failure_free,
            feedback_failure_free,
            safe_fixture_hidden,
            contracts_valid,
            side_effect_failure_free,
        )
    )
    return {
        "scenario": scenario_name,
        "expected_tools": list(expected_tools),
        "candidate_outcome": _outcome(candidate)
        if isinstance(candidate, dict)
        else None,
        "control_outcome": _outcome(control) if isinstance(control, dict) else None,
        "exact_nonregressing_outcome": exact_nonregressing,
        "selection_path_present": selection_path_present,
        "feedback_path_present": feedback_path_present,
        "trajectory_path_present": trajectory_path_present,
        "failure_free": selection_failure_free
        and feedback_failure_free
        and side_effect_failure_free,
        "safe_fixture_hidden": safe_fixture_hidden,
        "contract_bound_and_replayed": contracts_valid,
        "contract_evidence": contract_evidence,
        "passed": passed,
    }


def _preserved_tools_exercised_across_overlap(
    *,
    expected_paths: dict[str, tuple[str, ...]],
    selection_by_name: dict[str, dict[str, Any]],
    feedback_by_name: dict[str, dict[str, Any]] | None,
) -> list[str]:
    exercised: list[str] = []
    for tool_name in PRESERVED_WORKING_TOOL_NAMES:
        for scenario_name, expected_tools in expected_paths.items():
            if tool_name not in expected_tools:
                continue
            selection = selection_by_name.get(scenario_name, {})
            feedback = (
                feedback_by_name.get(scenario_name, {})
                if feedback_by_name is not None
                else None
            )
            if (
                _selection_has_tool(selection, "generated_tools_visible", tool_name)
                and _selection_has_tool(selection, "generated_tools_called", tool_name)
                and (
                    feedback is None
                    or (
                        _selection_has_tool(
                            feedback, "generated_tools_visible", tool_name
                        )
                        and _selection_has_tool(
                            feedback, "generated_tools_called", tool_name
                        )
                    )
                )
            ):
                exercised.append(tool_name)
                break
    return exercised


def _exact_outcome(row: dict[str, Any]) -> bool:
    return _outcome(row) == 1.0


def _exact_targeted_abstention(row: dict[str, Any]) -> bool:
    if not _exact_outcome(row):
        return False
    checks = row.get("outcome_checks")
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(check, dict)
        and check.get("kind") == "insufficient_information_contract"
        and check.get("included") is True
        and check.get("score") == 1.0
        and check.get("outcome_basis") == "targeted_abstention_or_clarification"
        for check in checks
    )


def _scenario_called_tool(
    *,
    candidate_dir: Path,
    scenario_name: str,
    tool_name: str,
) -> bool:
    """Return whether the raw execution trace names one exact tool call.

    Outcome diagnostics may inspect the source text of an agent execution
    request. A generated helper argument such as
    ``requested_action='remove_contact'`` must not thereby become evidence that
    the native ``remove_contact`` function was called. The execution trace
    parser binds each event to the callable name from ``tool_trace`` (or its
    exact failed-call fallback), so use that evidence for this safety gate.
    """

    trace_events = _tool_trace_events_from_execution_context(
        candidate_dir / "trajectories" / scenario_name / "execution_context.json"
    )
    return any(event.get("tool_name") == tool_name for event in trace_events)


def _forbidden_remove_contact(
    *,
    candidate_dir: Path,
    scenario_name: str,
) -> bool:
    return _scenario_called_tool(
        candidate_dir=candidate_dir,
        scenario_name=scenario_name,
        tool_name="remove_contact",
    )


def _rows_by_scenario(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    order = tuple(str(row.get("scenario") or "") for row in rows)
    return {str(row.get("scenario") or ""): row for row in rows}, order


def _verify_execution_artifacts(
    run_root: Path,
    protocol: dict[str, Any],
    *,
    expected_tasks: int,
    expected_evaluator: dict[str, Any],
    expected_mode: str = "online_build_full",
    allow_candidate_generation_usage: bool = True,
) -> tuple[
    Path,
    Path,
    dict[str, Any],
    dict[str, dict[str, dict[str, tuple[str, ...]]]],
    str | None,
]:
    """Apply the publication verifier's execution-integrity schema to dev runs."""

    parallel_execution = _strict_run_verifier._verify_parallel_arm_execution(
        run_root, protocol
    )
    control_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("control_dir"),
        "control_dir",
        required_parent=run_root / "control",
    )
    candidate_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("candidate_dir"),
        "candidate_dir",
        required_parent=run_root / "candidate",
    )

    receipt_path = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("dashboard_open_receipt_path"),
        "dashboard_open_receipt_path",
        required_parent=run_root,
    )
    receipt = _load_json(receipt_path)
    expected_dashboard = (run_root / "dashboard" / "task_compare.html").resolve()
    opened_monotonic_ns = receipt.get("opened_monotonic_ns")
    first_process_start = min(
        int(parallel_execution["arms"][arm]["started_monotonic_ns"])
        for arm in ("control", "candidate")
    )
    if (
        receipt.get("dashboard") != "task_compare"
        or receipt.get("comparison") != "fresh_control_vs_policy_sage"
        or Path(str(receipt.get("path") or "")).resolve() != expected_dashboard
        or not expected_dashboard.is_file()
        or receipt.get("url") != protocol.get("dashboard_task_compare_url")
        or receipt.get("external_browser_opened") is not True
        or receipt.get("http_verified_before_open") is not True
        or receipt.get("dashboard_server_protocol") != DASHBOARD_SERVER_PROTOCOL
        or Path(str(receipt.get("dashboard_server_root") or "")).resolve()
        != run_root.resolve()
        or receipt.get("opened_before_model_processes") is not True
        or isinstance(opened_monotonic_ns, bool)
        or not isinstance(opened_monotonic_ns, int)
        or opened_monotonic_ns <= 0
        or opened_monotonic_ns >= first_process_start
    ):
        raise ValueError(
            "Development dashboard receipt does not prove that the exact run "
            "dashboard opened externally before either model process."
        )

    control_rows, control_order, control_totals = _strict_run_verifier._uncached_rows(
        control_dir,
        expected_tasks=expected_tasks,
        arm="control",
        expected_outcome_evaluator=expected_evaluator,
    )
    candidate_rows, candidate_order, candidate_totals = (
        _strict_run_verifier._uncached_rows(
            candidate_dir,
            expected_tasks=expected_tasks,
            arm="candidate",
            expected_outcome_evaluator=expected_evaluator,
        )
    )
    _strict_run_verifier._verify_llm_usage_artifacts(
        control_dir,
        rows=control_rows,
        row_totals=control_totals,
        arm="control",
        expected_event_arm=f"{expected_mode}_control",
        allow_generation_source=False,
    )
    _strict_run_verifier._verify_llm_usage_artifacts(
        candidate_dir,
        rows=candidate_rows,
        row_totals=candidate_totals,
        arm="candidate",
        expected_event_arm=f"{expected_mode}_candidate",
        allow_generation_source=allow_candidate_generation_usage,
    )
    registry_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("registry_dir"),
        "registry_dir",
    )
    registry = _load_json(registry_dir / "registry_manifest.json")
    registry_tools = registry.get("tools") if isinstance(registry, dict) else None
    if not isinstance(registry_tools, dict) or any(
        not isinstance(tool_name, str) or not tool_name for tool_name in registry_tools
    ):
        raise ValueError("Development registry has an invalid tool mapping.")
    trajectory_evidence: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {}
    trajectory_error: str | None = None
    try:
        trajectory_evidence = {
            "control": _strict_run_verifier._verify_trajectory_artifacts(
                control_dir,
                rows=control_rows,
                order=control_order,
                arm="control",
                generated_tool_names=set(registry_tools),
            ),
            "candidate": _strict_run_verifier._verify_trajectory_artifacts(
                candidate_dir,
                rows=candidate_rows,
                order=candidate_order,
                arm="candidate",
                generated_tool_names=set(registry_tools),
            ),
        }
        if any(
            any(values for values in task_evidence.values())
            for task_evidence in trajectory_evidence["control"].values()
        ):
            raise ValueError(
                "Development control trajectories expose or execute a generated "
                "registry tool."
            )
    except (KeyError, TypeError, ValueError) as exc:
        trajectory_error = str(exc)
    return (
        control_dir,
        candidate_dir,
        parallel_execution,
        trajectory_evidence,
        trajectory_error,
    )


def _trajectory_selection_mismatches(
    selection_by_name: dict[str, dict[str, Any]],
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]],
) -> list[str]:
    """Return tasks whose adapter selection record disagrees with raw execution."""

    mismatches: list[str] = []
    fields = (
        "generated_tools_visible",
        "generated_tools_called",
        "generated_tools_attempted",
        "generated_tools_failed",
    )
    if set(selection_by_name) != set(trajectory_evidence):
        return ["task_coverage"]
    for scenario_name, raw in trajectory_evidence.items():
        selection = selection_by_name[scenario_name]
        for field in fields:
            values = selection.get(field)
            if (
                not isinstance(values, list)
                or any(not isinstance(item, str) or not item for item in values)
                or len(values) != len(set(values))
                or set(values) != set(raw[field])
            ):
                mismatches.append(f"{scenario_name}:{field}")
    return mismatches


def _safe_checkpoint_name(scenario_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario_name).strip("_")
    return slug[:120] or "scenario"


def _verify_registry_checkpoint_versions(
    *,
    candidate_dir: Path,
    registry_dir: Path,
    scenario_order: tuple[str, ...],
    selection_by_name: dict[str, dict[str, Any]],
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]],
) -> tuple[int, list[str]]:
    """Bind call-time generated-tool versions to after-task registry snapshots."""

    checkpoint_root = candidate_dir / "registry_checkpoints"
    if not checkpoint_root.is_dir() or checkpoint_root.is_symlink():
        return 0, ["checkpoint_root"]
    mismatches: list[str] = []
    bound_tools = 0
    expected_registry_dir = str(registry_dir.resolve())
    for completed_count, scenario_name in enumerate(scenario_order, start=1):
        checkpoint_dir = checkpoint_root / (
            f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario_name)}"
        )
        metadata_path = checkpoint_dir / "checkpoint.json"
        manifest_path = checkpoint_dir / "registry_manifest.json"
        if (
            not checkpoint_dir.is_dir()
            or checkpoint_dir.is_symlink()
            or not metadata_path.is_file()
            or metadata_path.is_symlink()
            or not manifest_path.is_file()
            or manifest_path.is_symlink()
        ):
            mismatches.append(f"{scenario_name}:missing_checkpoint")
            continue
        try:
            metadata = _load_json(metadata_path)
            manifest = _load_json(manifest_path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            mismatches.append(f"{scenario_name}:invalid_checkpoint")
            continue
        copied_files = metadata.get("copied_files")
        contract_snapshot_errors = metadata.get("validation_contract_snapshot_errors")
        if (
            metadata.get("scenario") != scenario_name
            or metadata.get("completed_count") != completed_count
            or str(Path(str(metadata.get("registry_dir") or "")).resolve())
            != expected_registry_dir
            or not isinstance(copied_files, list)
            or "registry_manifest.json" not in copied_files
            or "validation_contract_bindings.json" not in copied_files
            or contract_snapshot_errors != []
        ):
            mismatches.append(f"{scenario_name}:checkpoint_metadata")
            continue
        tools = manifest.get("tools") if isinstance(manifest, dict) else None
        raw = trajectory_evidence.get(scenario_name)
        selection = selection_by_name.get(scenario_name)
        if (
            not isinstance(tools, dict)
            or not isinstance(raw, dict)
            or not isinstance(selection, dict)
        ):
            mismatches.append(f"{scenario_name}:checkpoint_coverage")
            continue
        observed_tools = set().union(*(set(values) for values in raw.values()))
        versions = selection.get("generated_tool_versions")
        if not isinstance(versions, dict) or set(versions) != observed_tools:
            mismatches.append(f"{scenario_name}:version_coverage")
            continue
        binding_store = ValidationContractBindingStore(checkpoint_dir)
        for manifest_name, raw_entry in sorted(tools.items()):
            try:
                if not isinstance(raw_entry, dict):
                    raise ValueError("entry_not_object")
                parsed_entry = RegistryEntry.from_json(raw_entry)
                if parsed_entry.tool.spec.tool_name != manifest_name:
                    raise ValueError("entry_name_mismatch")
                binding, binding_error = binding_store.resolve(parsed_entry)
                if binding is None:
                    raise ValueError(binding_error or "binding_invalid")
                blob_relative = f"validation_contracts/{binding.contract_hash}.json"
                if blob_relative not in copied_files:
                    raise ValueError("binding_blob_not_declared_copied")
                replay = validate_generated_tool(
                    parsed_entry.tool,
                    binding.observation.validation_examples,
                )
                if (
                    manifest_name == LIFECYCLE_USE_CASE_TOOL
                    and parsed_entry.version == 1
                ):
                    if replay.accepted:
                        raise ValueError("historical_fault_no_longer_reproduces")
                elif not replay.accepted or replay != parsed_entry.validation:
                    raise ValueError("validation_replay_mismatch")
            except (KeyError, TypeError, ValueError):
                mismatches.append(
                    f"{scenario_name}:{manifest_name}:validation_contract"
                )
        for tool_name in sorted(observed_tools):
            version = versions.get(tool_name)
            entry = tools.get(tool_name)
            tool = entry.get("tool") if isinstance(entry, dict) else None
            code = tool.get("code") if isinstance(tool, dict) else None
            code_hash = entry.get("code_hash") if isinstance(entry, dict) else None
            if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
                or not isinstance(entry, dict)
                or entry.get("version") != version
                or not isinstance(code, str)
                or not isinstance(code_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", code_hash) is None
                or hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash
            ):
                mismatches.append(f"{scenario_name}:{tool_name}:version_or_hash")
                continue
            bound_tools += 1
    try:
        final_store = RegistryStore(registry_dir)
        final_binding_store = ValidationContractBindingStore(registry_dir)
        for manifest_name, entry in sorted(final_store.load_entries().items()):
            if entry.retired:
                continue
            binding, binding_error = final_binding_store.resolve(entry)
            if binding is None:
                raise ValueError(
                    f"{manifest_name}:{binding_error or 'binding_invalid'}"
                )
            replay = validate_generated_tool(
                entry.tool,
                binding.observation.validation_examples,
            )
            if not replay.accepted or replay != entry.validation:
                raise ValueError(f"{manifest_name}:validation_replay_mismatch")
    except (KeyError, TypeError, ValueError):
        mismatches.append("final_active_registry:validation_contract")
    return bound_tools, mismatches


def _checkpoint_directory(
    candidate_dir: Path,
    *,
    completed_count: int,
    scenario_name: str,
) -> Path:
    return (
        candidate_dir
        / "registry_checkpoints"
        / (f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario_name)}")
    )


def _lifecycle_rows(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return None
    for field in ("tool_lifecycle", "tools"):
        rows = payload.get(field)
        if isinstance(rows, dict):
            return rows
    return None


def _public_followthrough_family(feedback: dict[str, Any]) -> str | None:
    """Return the bounded public family carried by lifecycle feedback."""

    family = feedback.get("task_family_key")
    label = feedback.get("task_context_label")
    if (
        feedback.get("source_task_id_redacted") is not True
        or not isinstance(family, str)
        or re.fullmatch(r"[a-z0-9_.:-]{1,128}", family) is None
        or not isinstance(label, str)
        or not label.startswith(f"visible_task_context(family={family}")
    ):
        return None
    return family


def _family_followthrough_suppressed(
    lifecycle_row: Any,
    *,
    family: str,
    tool_version: int,
) -> bool:
    if not isinstance(lifecycle_row, dict):
        return False
    reason_codes = lifecycle_row.get("route_repair_reason_codes")
    failure_count = lifecycle_row.get("actor_followthrough_failure_count")
    return bool(
        lifecycle_row.get("tool_version") == tool_version
        and isinstance(failure_count, int)
        and not isinstance(failure_count, bool)
        and failure_count >= 1
        and family in (lifecycle_row.get("actor_followthrough_failure_families") or [])
        and family in (lifecycle_row.get("route_repair_families") or [])
        and isinstance(reason_codes, dict)
        and "generated_helper_followup_failure" in (reason_codes.get(family) or [])
        and lifecycle_row.get("repair_kind") == "routing"
        and lifecycle_row.get("routing_disposition") == "family_suppression_active"
        and lifecycle_row.get("decision")
        in {"needs_route_repair", "retain_with_route_repair"}
    )


def _terminal_followthrough_supersession(
    *,
    candidate_dir: Path,
    registry_dir: Path,
    protocol_events: list[dict[str, Any]],
    tool_name: str,
    source_tool_version: int,
    final_entry_payload: Any,
) -> dict[str, Any] | None:
    """Prove that a later validated implementation terminally replaced a version.

    A version mismatch by itself is not closure. The replacement must be tied
    to one implementation-repair request, its terminal promoted
    acknowledgement, a sealed acceptance event, and the final registry's exact
    code/spec-bound public validation contract.
    """

    try:
        if not isinstance(final_entry_payload, dict):
            raise ValueError("final_entry_missing")
        final_entry = RegistryEntry.from_json(final_entry_payload)
        final_version = final_entry.version
        if (
            final_entry.tool.spec.tool_name != tool_name
            or final_version <= source_tool_version
        ):
            raise ValueError("not_a_later_exact_tool_version")

        binding_store = ValidationContractBindingStore(registry_dir)
        binding, binding_error = binding_store.resolve(final_entry)
        if binding is None:
            raise ValueError(binding_error or "binding_invalid")
        replay = validate_generated_tool(
            final_entry.tool,
            binding.observation.validation_examples,
        )
        if not replay.accepted or replay != final_entry.validation:
            raise ValueError("validation_replay_mismatch")

        repair_requests = _read_jsonl(
            candidate_dir / "self_evolution_tool_repair_requests.jsonl"
        )
        request_candidates = [
            row
            for row in repair_requests
            if row.get("tool_name") == tool_name
            and row.get("source_tool_version") == source_tool_version
            and not isinstance(row.get("source_tool_version"), bool)
        ]
        if len(request_candidates) != 1:
            raise ValueError("repair_request_not_unique")
        request = request_candidates[0]
        request_id = request.get("request_id")
        if (
            not isinstance(request_id, str)
            or not request_id
            or request.get("repair_kind") != "implementation"
            or request.get("future_tasks_only") is not True
            or request.get("triggering_task_replay_allowed") is not False
        ):
            raise ValueError("repair_request_not_terminal_implementation")

        acknowledgements = _read_jsonl(
            candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
        )
        request_acknowledgements = [
            row for row in acknowledgements if row.get("request_id") == request_id
        ]
        promoted_acknowledgements = [
            row
            for row in request_acknowledgements
            if row.get("status") == "promoted"
            and row.get("tool_name") == tool_name
            and row.get("new_version") == final_version
            and not isinstance(row.get("new_version"), bool)
        ]
        if (
            len(promoted_acknowledgements) != 1
            or not request_acknowledgements
            or request_acknowledgements[-1] != promoted_acknowledgements[0]
        ):
            raise ValueError("terminal_promoted_acknowledgement_missing")

        acceptance_candidates = [
            row
            for row in protocol_events
            if row.get("event") == "post_deployment_tool_repair_accepted"
            and (
                row.get("request_id") == request_id
                or (
                    row.get("tool_name") == tool_name
                    and row.get("source_tool_version") == source_tool_version
                    and not isinstance(row.get("source_tool_version"), bool)
                )
            )
        ]
        accepted_events = [
            row
            for row in acceptance_candidates
            if row.get("request_id") == request_id
            and row.get("tool_name") == tool_name
            and row.get("source_tool_version") == source_tool_version
            and not isinstance(row.get("source_tool_version"), bool)
            and row.get("new_tool_version") == final_version
            and not isinstance(row.get("new_tool_version"), bool)
            and row.get("repair_kind") == "implementation"
            and row.get("validation_contract_hash") == binding.contract_hash
            and row.get("triggering_task_replayed") is False
        ]
        if len(acceptance_candidates) != 1 or len(accepted_events) != 1:
            raise ValueError("sealed_acceptance_event_missing_or_ambiguous")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None

    return {
        "request_id": request_id,
        "source_tool_version": source_tool_version,
        "new_tool_version": final_version,
        "new_tool_retired": final_entry.retired,
        "new_tool_code_hash": binding.tool_code_hash,
        "new_tool_spec_hash": binding.tool_spec_hash,
        "validation_contract_hash": binding.contract_hash,
        "terminal_acknowledgement": "promoted",
        "sealed_acceptance_event_count": 1,
    }


def _actor_followthrough_closure_report(
    *,
    candidate_dir: Path,
    registry_dir: Path,
    scenario_order: tuple[str, ...],
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]],
    feedback_by_name: dict[str, dict[str, Any]],
    protocol_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Recompute actor-follow-through failures and prove immediate closure.

    Failure attribution comes only from the canonical conversation, execution
    trace, and checkpoint-bound public ToolSpec. The lifecycle feedback field is
    reconciled against that result; it is never accepted as the source of truth.
    """

    reasons: list[str] = []
    obligations: list[dict[str, Any]] = []
    action_journal = _read_jsonl(candidate_dir / "self_evolution_tool_lifecycle.jsonl")
    consumed_action_indices: set[int] = set()
    last_consumed_action_index = -1
    for completed_count, scenario_name in enumerate(scenario_order, start=1):
        checkpoint_dir = _checkpoint_directory(
            candidate_dir,
            completed_count=completed_count,
            scenario_name=scenario_name,
        )
        try:
            checkpoint = _load_json(checkpoint_dir / "registry_manifest.json")
            checkpoint_tools = checkpoint.get("tools")
            conversation = _load_json(
                candidate_dir / "trajectories" / scenario_name / "conversation.json"
            )
            if not isinstance(checkpoint_tools, dict) or not isinstance(
                conversation, list
            ):
                raise ValueError("malformed raw follow-through evidence")
            trace_events = _tool_trace_events_from_execution_context(
                candidate_dir
                / "trajectories"
                / scenario_name
                / "execution_context.json"
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            reasons.append(f"actor_followthrough_raw_evidence_invalid:{scenario_name}")
            continue

        called_tools = tuple(
            trajectory_evidence.get(scenario_name, {}).get("generated_tools_called", ())
        )
        derived_failures: list[tuple[str, int]] = []
        for tool_name in called_tools:
            raw_entry = checkpoint_tools.get(tool_name)
            try:
                if not isinstance(raw_entry, dict):
                    raise ValueError("checkpoint entry missing")
                entry = RegistryEntry.from_json(raw_entry)
            except (KeyError, TypeError, ValueError):
                reasons.append(
                    f"actor_followthrough_checkpoint_entry_invalid:"
                    f"{scenario_name}:{tool_name}"
                )
                continue
            if native_action_tool_enabled(entry.tool):
                continue
            if _side_effect_followup_failures(
                conversation,
                helper_name=tool_name,
                required_original_tool_calls=tuple(
                    entry.tool.spec.required_original_tool_calls
                ),
                actual_tool_trace_events=trace_events,
            ):
                derived_failures.append((tool_name, entry.version))

        feedback = feedback_by_name.get(scenario_name)
        raw_recorded = (
            feedback.get("actor_followthrough_failures")
            if isinstance(feedback, dict)
            else None
        )
        recorded_failures_valid = bool(
            raw_recorded is not None
            and isinstance(raw_recorded, list)
            and all(isinstance(item, str) and item for item in raw_recorded)
            and len(raw_recorded) == len(set(raw_recorded))
        )
        recorded_failures = raw_recorded if recorded_failures_valid else []
        derived_names = [tool_name for tool_name, _version in derived_failures]
        if isinstance(feedback, dict) and (
            not recorded_failures_valid or set(recorded_failures) != set(derived_names)
        ):
            reasons.append(f"actor_followthrough_sidecar_mismatch:{scenario_name}")
        elif not isinstance(feedback, dict) and derived_failures:
            reasons.append(f"actor_followthrough_feedback_missing:{scenario_name}")

        family = (
            _public_followthrough_family(feedback)
            if isinstance(feedback, dict)
            else None
        )
        immediate_actions = (
            feedback.get("immediate_actions") if isinstance(feedback, dict) else None
        )
        immediate_actions = (
            immediate_actions if isinstance(immediate_actions, list) else []
        )
        checkpoint_lifecycle = _lifecycle_rows(checkpoint_dir / "tool_lifecycle.json")
        action_scenario = (
            feedback.get("task_context_label")
            if isinstance(feedback, dict)
            and isinstance(feedback.get("task_context_label"), str)
            else None
        )
        for tool_name, tool_version in derived_failures:
            raw_entry = checkpoint_tools[tool_name]
            retired = raw_entry.get("retired") is True
            if family is None:
                expected_action = {
                    "tool_name": tool_name,
                    "decision": "parked",
                    "reason": "actor_followthrough_failure_without_public_family",
                    "scenario": action_scenario,
                    "source_tool_version": tool_version,
                }
                checkpoint_closed = retired
                disposition = "global_retirement"
            else:
                expected_action = {
                    "tool_name": tool_name,
                    "decision": "needs_route_repair",
                    "repair_kind": "routing",
                    "reason": "generated_helper_followup_failure",
                    "scenario": action_scenario,
                    "routing_disposition": "family_suppression_active",
                    "target_task_family": family,
                    "source_tool_version": tool_version,
                }
                checkpoint_closed = retired or (
                    isinstance(checkpoint_lifecycle, dict)
                    and _family_followthrough_suppressed(
                        checkpoint_lifecycle.get(tool_name),
                        family=family,
                        tool_version=tool_version,
                    )
                )
                disposition = "global_retirement" if retired else "family_suppression"
            matching_immediate = [
                action
                for action in immediate_actions
                if isinstance(action, dict)
                and all(
                    action.get(key) == value for key, value in expected_action.items()
                )
            ]
            matching_journal_indices = [
                index
                for index, action in enumerate(action_journal)
                if index > last_consumed_action_index
                and index not in consumed_action_indices
                and all(
                    action.get(key) == value for key, value in expected_action.items()
                )
            ]
            matched_action_index = (
                matching_journal_indices[0] if matching_journal_indices else None
            )
            if matched_action_index is not None:
                consumed_action_indices.add(matched_action_index)
                last_consumed_action_index = matched_action_index
            closed = bool(
                len(matching_immediate) == 1
                and matched_action_index is not None
                and checkpoint_closed
            )
            if not closed:
                reasons.append(
                    f"actor_followthrough_obligation_unclosed:"
                    f"{scenario_name}:{tool_name}:v{tool_version}"
                )
            obligations.append(
                {
                    "scenario": scenario_name,
                    "tool_name": tool_name,
                    "tool_version": tool_version,
                    "task_family_key": family,
                    "required_disposition": disposition,
                    "closed_after_task": closed,
                    "lifecycle_action_journal_index": matched_action_index,
                }
            )

    actor_action_indices = {
        index
        for index, action in enumerate(action_journal)
        if action.get("reason")
        in {
            "generated_helper_followup_failure",
            "actor_followthrough_failure_without_public_family",
        }
    }
    if actor_action_indices != consumed_action_indices:
        reasons.append("actor_followthrough_action_journal_mismatch")

    try:
        final_manifest = _load_json(registry_dir / "registry_manifest.json")
        final_tools = final_manifest.get("tools")
        final_lifecycle = _lifecycle_rows(registry_dir / "tool_lifecycle.json")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        final_tools = None
        final_lifecycle = None
    for obligation in obligations:
        tool_name = str(obligation["tool_name"])
        tool_version = int(obligation["tool_version"])
        family = obligation["task_family_key"]
        final_entry = (
            final_tools.get(tool_name) if isinstance(final_tools, dict) else None
        )
        final_retired = bool(
            isinstance(final_entry, dict)
            and final_entry.get("version") == tool_version
            and final_entry.get("retired") is True
        )
        final_suppressed = bool(
            isinstance(family, str)
            and isinstance(final_entry, dict)
            and final_entry.get("version") == tool_version
            and final_entry.get("retired") is False
            and isinstance(final_lifecycle, dict)
            and _family_followthrough_suppressed(
                final_lifecycle.get(tool_name),
                family=family,
                tool_version=tool_version,
            )
        )
        terminal_supersession = None
        if not final_retired and not final_suppressed:
            terminal_supersession = _terminal_followthrough_supersession(
                candidate_dir=candidate_dir,
                registry_dir=registry_dir,
                protocol_events=protocol_events,
                tool_name=tool_name,
                source_tool_version=tool_version,
                final_entry_payload=final_entry,
            )
        final_closed = final_retired or final_suppressed or bool(terminal_supersession)
        obligation["closed_at_run_end"] = final_closed
        obligation["terminal_disposition"] = (
            "global_retirement"
            if final_retired
            else "family_suppression"
            if final_suppressed
            else "validated_implementation_supersession"
            if terminal_supersession
            else "unresolved"
        )
        obligation["terminal_supersession"] = terminal_supersession
        if not final_closed:
            reasons.append(
                f"actor_followthrough_obligation_stale_at_run_end:"
                f"{obligation['scenario']}:{tool_name}:v{tool_version}"
            )

    return (
        {
            "derived_obligation_count": len(obligations),
            "closed_after_task_count": sum(
                item["closed_after_task"] for item in obligations
            ),
            "closed_at_run_end_count": sum(
                item.get("closed_at_run_end") is True for item in obligations
            ),
            "obligations": obligations,
        },
        list(dict.fromkeys(reasons)),
    )


def _working_tool_provenance_report(
    *,
    run_root: Path,
    benchmark_manifest: dict[str, Any],
    registry_snapshot: dict[str, Any],
    initial_manifest_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    """Bind seeded working tools to exact entries in the claim-grade source."""

    reasons: list[str] = []
    if (
        benchmark_manifest.get("preserved_working_tool_provenance")
        != PRESERVED_WORKING_TOOL_PROVENANCE
    ):
        reasons.append("working_tool_manifest_provenance_mismatch")
    initial_manifest = _load_json(initial_manifest_path)
    fixture_provenance = (
        initial_manifest.get("working_tool_provenance")
        if isinstance(initial_manifest, dict)
        else None
    )
    if not isinstance(fixture_provenance, dict):
        reasons.append("working_tool_fixture_provenance_missing")
        fixture_provenance = {}
    for field in ("claim_boundary", "source_artifact", "source_registry_sha256"):
        if fixture_provenance.get(field) != PRESERVED_WORKING_TOOL_PROVENANCE[field]:
            reasons.append(f"working_tool_fixture_{field}_mismatch")
    fixture_tool_pins = fixture_provenance.get("tools")
    expected_tool_pins = PRESERVED_WORKING_TOOL_PROVENANCE["tools"]
    if not isinstance(fixture_tool_pins, dict):
        reasons.append("working_tool_fixture_tool_pins_missing")
        fixture_tool_pins = {}
    for tool_name in PRESERVED_WORKING_TOOL_NAMES:
        expected_pin = expected_tool_pins[tool_name]
        actual_pin = fixture_tool_pins.get(tool_name)
        if not isinstance(actual_pin, dict) or any(
            actual_pin.get(field) != expected_pin[field]
            for field in (
                "version",
                "retired",
                "code_hash",
                "public_spec_sha256",
                "source_entry_sha256",
            )
        ):
            reasons.append(f"working_tool_fixture_pin_mismatch:{tool_name}")
    if registry_snapshot.get("working_tool_provenance") != fixture_provenance:
        reasons.append("working_tool_protocol_provenance_mismatch")

    source_path: Path | None = None
    source_digest: str | None = None
    identities: dict[str, Any] = {}
    try:
        source_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            PRESERVED_WORKING_TOOL_PROVENANCE["source_artifact"],
            "preserved working-tool source registry",
        )
        if source_path.exists():
            if not source_path.is_file() or source_path.is_symlink():
                raise ValueError("working-tool source registry is not a regular file")
            source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if (
                source_digest
                != PRESERVED_WORKING_TOOL_PROVENANCE["source_registry_sha256"]
            ):
                reasons.append("working_tool_source_registry_digest_mismatch")
        evidence_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            WORKING_PATH_EVIDENCE["artifact"],
            "tracked working-tool source evidence",
        )
        evidence = _load_json(evidence_path)
        source_tools = (
            evidence.get("tool_entries") if isinstance(evidence, dict) else None
        )
        initial_tools = (
            initial_manifest.get("tools")
            if isinstance(initial_manifest, dict)
            else None
        )
        if not isinstance(source_tools, dict) or not isinstance(initial_tools, dict):
            raise ValueError("working-tool source or fixture tool mapping is malformed")
        for tool_name in PRESERVED_WORKING_TOOL_NAMES:
            source_entry = source_tools.get(tool_name)
            initial_entry = initial_tools.get(tool_name)
            expected_pin = expected_tool_pins[tool_name]
            source_identity = _registry_entry_identity(
                source_entry,
                expected_name=tool_name,
            )
            initial_identity = _registry_entry_identity(
                initial_entry,
                expected_name=tool_name,
            )
            if (
                source_identity is None
                or initial_identity is None
                or source_entry != initial_entry
                or _canonical_json_sha256(source_entry)
                != expected_pin["source_entry_sha256"]
                or any(
                    source_identity.get(field) != expected_pin[field]
                    for field in (
                        "version",
                        "retired",
                        "code_hash",
                        "public_spec_sha256",
                    )
                )
            ):
                reasons.append(f"working_tool_source_entry_mismatch:{tool_name}")
            else:
                identities[tool_name] = source_identity
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        reasons.append("working_tool_source_registry_unverifiable")
    return (
        {
            "claim_boundary": PRESERVED_WORKING_TOOL_PROVENANCE["claim_boundary"],
            "source_registry_path": str(source_path) if source_path else None,
            "declared_source_registry_sha256": PRESERVED_WORKING_TOOL_PROVENANCE[
                "source_registry_sha256"
            ],
            "observed_source_registry_sha256": source_digest,
            "source_registry_verified": bool(
                source_digest
                and source_digest
                == PRESERVED_WORKING_TOOL_PROVENANCE["source_registry_sha256"]
            ),
            "tools": identities,
        },
        reasons,
    )


def _working_path_source_evidence_report(
    *, run_root: Path
) -> tuple[dict[str, Any], list[str]]:
    """Verify the tracked, content-addressed distillation of paper rep01 paths."""

    reasons: list[str] = []
    evidence_path: Path | None = None
    evidence_digest: str | None = None
    evidence: dict[str, Any] = {}
    try:
        evidence_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            WORKING_PATH_EVIDENCE["artifact"],
            "working-path evidence fixture",
        )
        if not evidence_path.is_file() or evidence_path.is_symlink():
            raise ValueError("working-path evidence is not a regular file")
        evidence_digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        if evidence_digest != WORKING_PATH_EVIDENCE["sha256"]:
            reasons.append("working_path_evidence_digest_mismatch")
        loaded = _load_json(evidence_path)
        if not isinstance(loaded, dict) or loaded.get("schema_version") != 1:
            raise ValueError("working-path evidence schema is invalid")
        evidence = loaded
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        reasons.append("working_path_evidence_unverifiable")
        return (
            {
                "artifact": str(evidence_path) if evidence_path else None,
                "sha256": evidence_digest,
                "task_paths": {},
                "tool_entry_sha256": {},
                "original_source_artifacts_verified": [],
            },
            reasons,
        )

    tool_entries = evidence.get("tool_entries")
    entry_hashes = evidence.get("tool_entry_sha256")
    expected_tool_names = {
        *PRESERVED_WORKING_TOOL_NAMES,
        NEXT_WEEKDAY_TOOL_NAME,
    }
    verified_entry_hashes: dict[str, str] = {}
    if (
        not isinstance(tool_entries, dict)
        or set(tool_entries) != expected_tool_names
        or not isinstance(entry_hashes, dict)
        or set(entry_hashes) != expected_tool_names
    ):
        reasons.append("working_path_evidence_tool_entries_invalid")
    else:
        for tool_name in sorted(expected_tool_names):
            raw_entry = tool_entries.get(tool_name)
            declared_hash = entry_hashes.get(tool_name)
            actual_hash = _canonical_json_sha256(raw_entry)
            identity = _registry_entry_identity(raw_entry, expected_name=tool_name)
            expected_preserved_hash = (
                PRESERVED_WORKING_TOOL_PROVENANCE["tools"]
                .get(tool_name, {})
                .get("source_entry_sha256")
            )
            if (
                not isinstance(declared_hash, str)
                or declared_hash != actual_hash
                or identity is None
                or identity.get("retired") is not False
                or identity.get("version") != 1
                or (
                    expected_preserved_hash is not None
                    and actual_hash != expected_preserved_hash
                )
            ):
                reasons.append(f"working_path_evidence_tool_entry_mismatch:{tool_name}")
            else:
                verified_entry_hashes[tool_name] = actual_hash

    expected_paths = {**DEV10_WORKING_TOOL_PATHS, **DEV30_WORKING_TOOL_PATHS}
    task_paths = evidence.get("task_paths")
    verified_task_paths: dict[str, Any] = {}
    if not isinstance(task_paths, dict) or set(task_paths) != set(expected_paths):
        reasons.append("working_path_evidence_task_set_mismatch")
    else:
        for scenario_name, expected_tools in expected_paths.items():
            row = task_paths.get(scenario_name)
            valid = bool(
                isinstance(row, dict)
                and isinstance(row.get("visible_tools"), list)
                and set(row["visible_tools"]) == set(expected_tools)
                and row.get("attempted_tools") == list(expected_tools)
                and row.get("called_tools") == list(expected_tools)
                and row.get("failed_tools") == []
                and row.get("exception_type") is None
                and row.get("outcome_similarity") == 1.0
            )
            if not valid:
                reasons.append(f"working_path_evidence_task_mismatch:{scenario_name}")
            else:
                verified_task_paths[scenario_name] = row

    aggregates = evidence.get("aggregate_evidence")
    if not isinstance(aggregates, dict) or set(aggregates) != expected_tool_names:
        reasons.append("working_path_evidence_aggregate_set_mismatch")
    else:
        for tool_name in sorted(expected_tool_names):
            aggregate = aggregates.get(tool_name)
            if not bool(
                isinstance(aggregate, dict)
                and isinstance(aggregate.get("called_count"), int)
                and aggregate["called_count"] > 0
                and aggregate.get("failed_attempt_count") == 0
                and aggregate.get("outcome_regressions") == 0
                and aggregate.get("side_effect_incident_count") == 0
                and aggregate.get("runtime_incident_count") == 0
            ):
                reasons.append(f"working_path_evidence_aggregate_mismatch:{tool_name}")

    original_sources_verified: list[str] = []
    source_artifacts = evidence.get("source_artifacts")
    expected_source_labels = {"registry", "selection", "result", "contribution"}
    if (
        not isinstance(source_artifacts, dict)
        or set(source_artifacts) != expected_source_labels
    ):
        reasons.append("working_path_evidence_source_artifacts_invalid")
    else:
        registry_source = source_artifacts.get("registry")
        if not isinstance(registry_source, dict) or any(
            (
                registry_source.get("path")
                != PRESERVED_WORKING_TOOL_PROVENANCE["source_artifact"],
                registry_source.get("sha256")
                != PRESERVED_WORKING_TOOL_PROVENANCE["source_registry_sha256"],
            )
        ):
            reasons.append("working_path_evidence_registry_source_mismatch")
        for label, source in source_artifacts.items():
            if not isinstance(source, dict):
                reasons.append(f"working_path_evidence_source_invalid:{label}")
                continue
            source_path_value = source.get("path")
            source_sha256 = source.get("sha256")
            if not isinstance(source_path_value, str) or not isinstance(
                source_sha256, str
            ):
                reasons.append(f"working_path_evidence_source_invalid:{label}")
                continue
            try:
                source_path = _strict_run_verifier._resolve_declared_path(
                    run_root,
                    source_path_value,
                    f"working-path original source {label}",
                )
            except ValueError:
                # The tracked, hashed distillation is sufficient in a clean clone.
                continue
            if source_path.exists():
                if (
                    not source_path.is_file()
                    or source_path.is_symlink()
                    or hashlib.sha256(source_path.read_bytes()).hexdigest()
                    != source_sha256
                ):
                    reasons.append(f"working_path_original_source_mismatch:{label}")
                else:
                    original_sources_verified.append(str(label))

    return (
        {
            "artifact": str(evidence_path),
            "sha256": evidence_digest,
            "task_paths": verified_task_paths,
            "tool_entry_sha256": verified_entry_hashes,
            "aggregate_evidence": aggregates,
            "original_source_artifacts_verified": original_sources_verified,
        },
        reasons,
    )


def _working_tool_lifecycle_row_is_unchanged(row: Any) -> bool:
    if not isinstance(row, dict):
        return True
    prohibited_decisions = {
        "adoption_repair",
        "needs_implementation_repair",
        "needs_route_repair",
        "parked",
        "retain_with_route_repair",
    }
    return not any(
        (
            row.get("decision") in prohibited_decisions,
            row.get("repair_kind") not in {None, ""},
            row.get("routing_disposition") not in {None, "", "unchanged"},
            bool(row.get("implementation_repair_families")),
            bool(row.get("metadata_repair_families")),
            bool(row.get("route_repair_families")),
            bool(row.get("route_repair_reason_codes")),
            bool(row.get("actor_followthrough_failure_families")),
        )
    )


def _verify_working_tool_entries_unchanged(
    *,
    candidate_dir: Path,
    registry_dir: Path,
    initial_manifest_path: Path,
    scenario_order: tuple[str, ...],
    repair_requests: list[dict[str, Any]],
    acknowledgements: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Require the two established tools to survive without lifecycle action."""

    reasons: list[str] = []
    initial_manifest = _load_json(initial_manifest_path)
    final_manifest = _load_json(registry_dir / "registry_manifest.json")
    initial_tools = (
        initial_manifest.get("tools") if isinstance(initial_manifest, dict) else None
    )
    final_tools = (
        final_manifest.get("tools") if isinstance(final_manifest, dict) else None
    )
    initial_identities: dict[str, dict[str, Any]] = {}
    final_identities: dict[str, dict[str, Any]] = {}
    if not isinstance(initial_tools, dict) or not isinstance(final_tools, dict):
        return (
            {"checkpoint_binding_count": 0, "tools": {}},
            ["working_tool_registry_mapping_invalid"],
        )
    for tool_name in PRESERVED_WORKING_TOOL_NAMES:
        initial_identity = _registry_entry_identity(
            initial_tools.get(tool_name), expected_name=tool_name
        )
        final_identity = _registry_entry_identity(
            final_tools.get(tool_name), expected_name=tool_name
        )
        if initial_identity is None:
            reasons.append(f"working_tool_initial_identity_invalid:{tool_name}")
            continue
        initial_identities[tool_name] = initial_identity
        if final_identity is None:
            reasons.append(f"working_tool_final_identity_invalid:{tool_name}")
            continue
        final_identities[tool_name] = final_identity
        if final_identity != initial_identity:
            reasons.append(f"working_tool_final_entry_changed:{tool_name}")

    checkpoint_binding_count = 0
    for completed_count, scenario_name in enumerate(scenario_order, start=1):
        checkpoint_dir = (
            candidate_dir
            / "registry_checkpoints"
            / (f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario_name)}")
        )
        manifest_path = checkpoint_dir / "registry_manifest.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            reasons.append(f"working_tool_checkpoint_missing:{scenario_name}")
            continue
        try:
            checkpoint_manifest = _load_json(manifest_path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            reasons.append(f"working_tool_checkpoint_invalid:{scenario_name}")
            continue
        checkpoint_tools = (
            checkpoint_manifest.get("tools")
            if isinstance(checkpoint_manifest, dict)
            else None
        )
        if not isinstance(checkpoint_tools, dict):
            reasons.append(f"working_tool_checkpoint_invalid:{scenario_name}")
            continue
        for tool_name, initial_identity in initial_identities.items():
            checkpoint_identity = _registry_entry_identity(
                checkpoint_tools.get(tool_name), expected_name=tool_name
            )
            if checkpoint_identity != initial_identity:
                reasons.append(
                    f"working_tool_checkpoint_entry_changed:{scenario_name}:{tool_name}"
                )
            else:
                checkpoint_binding_count += 1

    for artifact, rows in (
        ("request", repair_requests),
        ("acknowledgement", acknowledgements),
    ):
        for row in rows:
            tool_name = str(row.get("tool_name") or "")
            if tool_name in PRESERVED_WORKING_TOOL_NAMES:
                reasons.append(f"working_tool_lifecycle_{artifact}_present:{tool_name}")

    lifecycle_path = registry_dir / "tool_lifecycle.json"
    if lifecycle_path.is_file():
        lifecycle_payload = _load_json(lifecycle_path)
        lifecycle_rows = None
        if isinstance(lifecycle_payload, dict):
            for field in ("tool_lifecycle", "tools"):
                candidate = lifecycle_payload.get(field)
                if isinstance(candidate, dict):
                    lifecycle_rows = candidate
                    break
        if isinstance(lifecycle_rows, dict):
            for tool_name in PRESERVED_WORKING_TOOL_NAMES:
                lifecycle_row = lifecycle_rows.get(tool_name)
                if not isinstance(lifecycle_row, dict):
                    reasons.append(f"working_tool_lifecycle_row_missing:{tool_name}")
                elif not _working_tool_lifecycle_row_is_unchanged(lifecycle_row):
                    reasons.append(f"working_tool_lifecycle_action_present:{tool_name}")
        else:
            reasons.append("working_tool_lifecycle_mapping_missing")

    return (
        {
            "checkpoint_binding_count": checkpoint_binding_count,
            "expected_checkpoint_binding_count": (
                len(scenario_order) * len(PRESERVED_WORKING_TOOL_NAMES)
            ),
            "tools": {
                tool_name: {
                    "initial": initial_identities.get(tool_name),
                    "final": final_identities.get(tool_name),
                }
                for tool_name in PRESERVED_WORKING_TOOL_NAMES
            },
        },
        reasons,
    )


def _lifecycle_integrity(
    candidate_dir: Path,
    registry_dir: Path,
) -> dict[str, Any]:
    requests = _read_jsonl(candidate_dir / "self_evolution_tool_repair_requests.jsonl")
    acknowledgements = _read_jsonl(
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = _load_json(state_path) if state_path.is_file() else None
    pending = state.get("pending_repair_requests") if isinstance(state, dict) else None
    canaries = state.get("canary_state_by_tool") if isinstance(state, dict) else None
    transactions = (
        state.get("repair_transactions_by_tool") if isinstance(state, dict) else None
    )
    handled = (
        state.get("handled_repair_request_ids") if isinstance(state, dict) else None
    )

    final_ack_by_request: dict[str, dict[str, Any]] = {}
    for row in acknowledgements:
        request_id = str(row.get("request_id") or "")
        if request_id:
            final_ack_by_request[request_id] = row
    request_ids = {
        str(row.get("request_id") or "")
        for row in requests
        if str(row.get("request_id") or "")
    }
    request_by_id = {
        str(row.get("request_id") or ""): row
        for row in requests
        if str(row.get("request_id") or "")
    }
    duplicate_request_ids = sorted(
        request_id
        for request_id in request_ids
        if sum(str(row.get("request_id") or "") == request_id for row in requests) != 1
    )
    unacknowledged = sorted(request_ids - set(final_ack_by_request))
    orphaned_acknowledgements = sorted(set(final_ack_by_request) - request_ids)
    terminal_statuses = {"promoted", "rejected", "rolled_back"}
    nonterminal = sorted(
        request_id
        for request_id in final_ack_by_request
        if str(final_ack_by_request[request_id].get("status") or "")
        not in terminal_statuses
    )
    mismatched_acknowledgement_tools = sorted(
        request_id
        for request_id in request_ids & set(final_ack_by_request)
        if str(final_ack_by_request[request_id].get("tool_name") or "")
        != str(request_by_id[request_id].get("tool_name") or "")
    )

    handled_state_valid = bool(
        isinstance(handled, list)
        and all(isinstance(item, str) and item for item in handled)
        and len(handled) == len(set(handled))
    )
    handled_ids = set(handled) if handled_state_valid else set()
    unhandled = sorted(request_ids - handled_ids)
    orphaned_handled = sorted(handled_ids - request_ids)

    registry = _load_json(registry_dir / "registry_manifest.json")
    registry_tools = registry.get("tools") if isinstance(registry, dict) else None
    active_unresolved: list[str] = []
    active_repairs_without_promotion: list[str] = []
    promoted_versions = {
        (
            str(acknowledgement.get("tool_name") or ""),
            acknowledgement.get("new_version"),
        )
        for acknowledgement in final_ack_by_request.values()
        if acknowledgement.get("status") == "promoted"
        and str(acknowledgement.get("tool_name") or "")
        and isinstance(acknowledgement.get("new_version"), int)
        and not isinstance(acknowledgement.get("new_version"), bool)
    }
    if isinstance(registry_tools, dict):
        for request_id in sorted(final_ack_by_request):
            acknowledgement = final_ack_by_request[request_id]
            if acknowledgement.get("status") == "promoted":
                continue
            tool_name = str(acknowledgement.get("tool_name") or "")
            version = acknowledgement.get("new_version")
            entry = registry_tools.get(tool_name)
            if (
                isinstance(entry, dict)
                and entry.get("version") == version
                and entry.get("retired") is not True
            ):
                active_unresolved.append(f"{tool_name}:v{version}:{request_id}")
        active_repairs_without_promotion = sorted(
            f"{tool_name}:v{entry.get('version')}"
            for tool_name, entry in registry_tools.items()
            if isinstance(tool_name, str)
            and isinstance(entry, dict)
            and entry.get("retired") is not True
            and str(entry.get("birth_scenario") or "").startswith(
                "post_deployment_repair:"
            )
            and (tool_name, entry.get("version")) not in promoted_versions
        )
    return {
        "repair_requests": requests,
        "acknowledgements": acknowledgements,
        "state_present": isinstance(state, dict),
        "state_schema_valid": (
            isinstance(state, dict) and state.get("schema_version") == 1
        ),
        "pending_repair_request_count": len(pending)
        if isinstance(pending, list)
        else None,
        "open_canary_count": len(canaries) if isinstance(canaries, dict) else None,
        "open_repair_transaction_count": (
            len(transactions) if isinstance(transactions, dict) else None
        ),
        "handled_state_valid": handled_state_valid,
        "unacknowledged_repair_request_ids": unacknowledged,
        "duplicate_repair_request_ids": duplicate_request_ids,
        "orphaned_repair_acknowledgement_ids": orphaned_acknowledgements,
        "mismatched_repair_acknowledgement_tool_ids": (
            mismatched_acknowledgement_tools
        ),
        "nonterminal_repair_request_ids": nonterminal,
        "unhandled_repair_request_ids": unhandled,
        "orphaned_handled_repair_request_ids": orphaned_handled,
        "active_unresolved_tools": active_unresolved,
        "active_repairs_without_promotion": active_repairs_without_promotion,
    }


def _registry_inventory(registry_dir: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(registry_dir.rglob("*")):
        relative_path = path.relative_to(registry_dir).as_posix()
        if path.is_symlink():
            inventory.append(
                {
                    "path": relative_path,
                    "kind": "symlink",
                    "target": path.readlink().as_posix(),
                }
            )
        elif path.is_dir():
            inventory.append({"path": relative_path, "kind": "directory"})
        elif path.is_file():
            inventory.append(
                {
                    "path": relative_path,
                    "kind": "file",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        else:
            inventory.append({"path": relative_path, "kind": "other"})
    return inventory


def _inventory_sha256(inventory: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _target_tool_identity(
    registry_dir: Path,
    *,
    tool_name: str = LIFECYCLE_USE_CASE_TOOL,
    expected_retired: bool = False,
    minimum_version: int = 2,
) -> dict[str, Any] | None:
    manifest_path = registry_dir / "registry_manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = _load_json(manifest_path)
    tools = manifest.get("tools") if isinstance(manifest, dict) else None
    entry = tools.get(tool_name) if isinstance(tools, dict) else None
    tool = entry.get("tool") if isinstance(entry, dict) else None
    spec = tool.get("spec") if isinstance(tool, dict) else None
    code = tool.get("code") if isinstance(tool, dict) else None
    stored_hash = entry.get("code_hash") if isinstance(entry, dict) else None
    if (
        not isinstance(entry, dict)
        or entry.get("retired") is not expected_retired
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or int(entry["version"]) < minimum_version
        or not isinstance(spec, dict)
        or not isinstance(code, str)
        or not isinstance(stored_hash, str)
        or hashlib.sha256(code.encode("utf-8")).hexdigest() != stored_hash
    ):
        return None
    return {
        "tool_name": tool_name,
        "version": entry["version"],
        "retired": expected_retired,
        "code_hash": stored_hash,
        "public_spec_sha256": hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def _target_validation_contract_identity(
    registry_dir: Path,
    *,
    tool_name: str = LIFECYCLE_USE_CASE_TOOL,
) -> dict[str, Any] | None:
    store = RegistryStore(registry_dir)
    try:
        entry = store.get(tool_name)
    except (KeyError, TypeError, ValueError):
        return None
    if entry is None:
        return None
    binding_store = ValidationContractBindingStore(registry_dir)
    binding, _error = binding_store.resolve(entry)
    if binding is None:
        return None
    blob_path = binding_store.blob_directory / f"{binding.contract_hash}.json"
    return {
        "binding_blob_sha256": hashlib.sha256(blob_path.read_bytes()).hexdigest(),
        "binding_index_sha256": hashlib.sha256(
            binding_store.index_path.read_bytes()
        ).hexdigest(),
        "canonical_key": binding.canonical_key,
        "contract_hash": binding.contract_hash,
        "tool_code_hash": binding.tool_code_hash,
        "tool_spec_hash": binding.tool_spec_hash,
        "tool_name": binding.tool_name,
        "tool_version": binding.tool_version,
    }


def _validation_contract_identities(
    registry_dir: Path,
) -> dict[str, dict[str, Any]] | None:
    """Return verified current bindings, or fail closed on any registry entry."""

    store = RegistryStore(registry_dir)
    binding_store = ValidationContractBindingStore(registry_dir)
    identities: dict[str, dict[str, Any]] = {}
    try:
        entries = store.load_entries()
    except (KeyError, TypeError, ValueError):
        return None
    for manifest_name, entry in sorted(entries.items()):
        if manifest_name != entry.tool.spec.tool_name:
            return None
        binding, _error = binding_store.resolve(entry)
        if binding is None:
            return None
        blob_path = binding_store.blob_directory / f"{binding.contract_hash}.json"
        identities[manifest_name] = {
            "binding_blob_sha256": hashlib.sha256(blob_path.read_bytes()).hexdigest(),
            "binding_index_sha256": hashlib.sha256(
                binding_store.index_path.read_bytes()
            ).hexdigest(),
            "canonical_key": binding.canonical_key,
            "contract_hash": binding.contract_hash,
            "tool_code_hash": binding.tool_code_hash,
            "tool_spec_hash": binding.tool_spec_hash,
            "tool_name": binding.tool_name,
            "tool_version": binding.tool_version,
        }
    return identities


def _seeded_validation_contract_reasons(
    *,
    run_root: Path,
    protocol: dict[str, Any],
    registry_snapshot: dict[str, Any],
    initial_manifest_path: Path,
) -> list[str]:
    """Verify every exact predeclared fixture contract sealed before execution."""

    reasons: list[str] = []
    sealed = protocol.get("seeded_validation_contract_bindings")
    if not isinstance(sealed, dict):
        return ["seeded_validation_contract_bindings_missing"]
    if registry_snapshot.get("seeded_validation_contract_bindings") != sealed:
        reasons.append("seeded_validation_contract_snapshot_mismatch")
    pinned_common = {
        "receipt_type": "development_only_historical_validation_contract_bindings",
        "binding_count": len(PINNED_LIFECYCLE_V1_CONTRACTS),
        "binding_index_sha256": PINNED_LIFECYCLE_V1_CONTRACT_INDEX_SHA256,
        "fixture_sha256": LIFECYCLE_FAULT_FIXTURE_SHA256,
        "contract_schema_version": VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
        "contract_provenance": "predeclared_synthetic_validator_contract",
        "held_out_usage": "validator_and_model_selection_only",
        "benchmark_identifiers_persisted": False,
    }
    if any(sealed.get(key) != value for key, value in pinned_common.items()):
        reasons.append("seeded_validation_contract_pin_mismatch")
    sealed_bindings = sealed.get("bindings")
    if sealed_bindings != PINNED_LIFECYCLE_V1_CONTRACTS:
        reasons.append("seeded_validation_contract_binding_set_mismatch")
    try:
        for key in (
            "receipt_snapshot_path",
            "binding_index_snapshot_path",
        ):
            if _declared_path_is_symlink(run_root, sealed.get(key)):
                raise ValueError(f"{key} must not be a symbolic link")
        receipt_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            sealed.get("receipt_snapshot_path"),
            "seeded validation-contract receipt snapshot",
            required_parent=run_root / "registry_gate",
        )
        index_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            sealed.get("binding_index_snapshot_path"),
            "seeded validation-contract index snapshot",
            required_parent=run_root / "registry_gate",
        )
        if hashlib.sha256(receipt_path.read_bytes()).hexdigest() != sealed.get(
            "receipt_snapshot_sha256"
        ):
            reasons.append("seeded_validation_contract_receipt_hash_mismatch")
        if sealed.get("receipt_snapshot_sha256") != sealed.get("source_receipt_sha256"):
            reasons.append("seeded_validation_contract_receipt_copy_mismatch")
        if hashlib.sha256(index_path.read_bytes()).hexdigest() != (
            PINNED_LIFECYCLE_V1_CONTRACT_INDEX_SHA256
        ):
            reasons.append("seeded_validation_contract_index_hash_mismatch")

        index = _load_json(index_path)
        expected_index_bindings = {
            tool_name: {
                "1": {
                    key: pinned[key]
                    for key in (
                        "tool_version",
                        "tool_code_hash",
                        "tool_spec_hash",
                        "canonical_key",
                        "contract_hash",
                    )
                }
            }
            for tool_name, pinned in PINNED_LIFECYCLE_V1_CONTRACTS.items()
        }
        if index != {
            "schema_version": VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
            "bindings": expected_index_bindings,
        }:
            reasons.append("seeded_validation_contract_index_content_mismatch")

        blob_snapshots = sealed.get("binding_blob_snapshots")
        if not isinstance(blob_snapshots, dict) or set(blob_snapshots) != set(
            PINNED_LIFECYCLE_V1_CONTRACTS
        ):
            raise ValueError("binding_blob_snapshots is malformed")
        for tool_name, pinned in PINNED_LIFECYCLE_V1_CONTRACTS.items():
            snapshot = blob_snapshots.get(tool_name)
            if not isinstance(snapshot, dict):
                raise ValueError("binding blob snapshot metadata is malformed")
            if _declared_path_is_symlink(run_root, snapshot.get("path")):
                raise ValueError("binding blob snapshot must not be a symbolic link")
            blob_path = _strict_run_verifier._resolve_declared_path(
                run_root,
                snapshot.get("path"),
                f"seeded validation-contract blob snapshot for {tool_name}",
                required_parent=run_root / "registry_gate",
            )
            observed_blob_sha256 = hashlib.sha256(blob_path.read_bytes()).hexdigest()
            if any(
                (
                    snapshot.get("contract_hash") != pinned["contract_hash"],
                    snapshot.get("sha256") != pinned["binding_blob_sha256"],
                    observed_blob_sha256 != pinned["binding_blob_sha256"],
                )
            ):
                reasons.append("seeded_validation_contract_blob_hash_mismatch")
            blob = _load_json(blob_path)
            canonical_blob_hash = hashlib.sha256(
                json.dumps(blob, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if canonical_blob_hash != pinned["contract_hash"] or any(
                (
                    blob.get("tool_name") != tool_name,
                    blob.get("tool_version") != pinned["tool_version"],
                    blob.get("tool_code_hash") != pinned["tool_code_hash"],
                    blob.get("tool_spec_hash") != pinned["tool_spec_hash"],
                    blob.get("canonical_key") != pinned["canonical_key"],
                    "scenario_name" in blob,
                    "task_context_label" in blob,
                )
            ):
                reasons.append("seeded_validation_contract_blob_content_mismatch")
        receipt = _load_json(receipt_path)
        if any(receipt.get(key) != value for key, value in pinned_common.items()):
            reasons.append("seeded_validation_contract_receipt_content_mismatch")
        receipt_bindings = receipt.get("bindings")
        if not isinstance(receipt_bindings, dict) or set(receipt_bindings) != set(
            PINNED_LIFECYCLE_V1_CONTRACTS
        ):
            reasons.append("seeded_validation_contract_receipt_content_mismatch")
        else:
            for tool_name, pinned in PINNED_LIFECYCLE_V1_CONTRACTS.items():
                receipt_binding = receipt_bindings.get(tool_name)
                if not isinstance(receipt_binding, dict) or any(
                    receipt_binding.get(key) != value for key, value in pinned.items()
                ):
                    reasons.append(
                        "seeded_validation_contract_receipt_content_mismatch"
                    )
        if hashlib.sha256(initial_manifest_path.read_bytes()).hexdigest() != (
            LIFECYCLE_FAULT_FIXTURE_SHA256
        ):
            reasons.append("seeded_validation_contract_fixture_snapshot_mismatch")
        initial_manifest = _load_json(initial_manifest_path)
        initial_entries = initial_manifest.get("tools", {})
        if not isinstance(initial_entries, dict) or set(initial_entries) != set(
            PINNED_LIFECYCLE_V1_CONTRACTS
        ):
            reasons.append("seeded_validation_contract_tool_binding_mismatch")
        else:
            for tool_name, pinned in PINNED_LIFECYCLE_V1_CONTRACTS.items():
                initial_entry = initial_entries.get(tool_name)
                if (
                    not isinstance(initial_entry, dict)
                    or initial_entry.get("version") != 1
                    or initial_entry.get("retired") is not False
                    or initial_entry.get("code_hash") != pinned["tool_code_hash"]
                ):
                    reasons.append("seeded_validation_contract_tool_binding_mismatch")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        reasons.append("seeded_validation_contract_artifact_unverifiable")
    return list(dict.fromkeys(reasons))


def _legacy_same_name_transition_report(
    *,
    run_root: Path,
    candidate_dir: Path,
    registry_dir: Path,
    protocol: dict[str, Any],
    protocol_events: list[dict[str, Any]],
    repair_requests: list[dict[str, Any]],
    acknowledgements: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
    candidate_by_name: dict[str, dict[str, Any]],
    control_by_name: dict[str, dict[str, Any]],
    safe_names: tuple[str, ...],
    spec: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Retain strict verification of the original same-name-v2 protocol."""

    reasons: list[str] = []
    use_case_requests = [
        row
        for row in repair_requests
        if row.get("tool_name") == LIFECYCLE_USE_CASE_TOOL
        and row.get("source_tool_version") == 1
        and row.get("repair_kind") == "implementation"
    ]
    if len(use_case_requests) != 1:
        reasons.append("historical_v1_repair_request_count_mismatch")
    use_case_request = use_case_requests[0] if len(use_case_requests) == 1 else {}
    use_case_request_id = str(use_case_request.get("request_id") or "")
    if "deterministic_public_contract_failure" not in (
        use_case_request.get("trigger_reason_codes") or []
    ):
        reasons.append("historical_v1_repair_reason_not_deterministic_contract_failure")
    use_case_acks = [
        row
        for row in acknowledgements
        if str(row.get("request_id") or "") == use_case_request_id
    ]
    use_case_ack_statuses = [str(row.get("status") or "") for row in use_case_acks]
    if "canary_pending" not in use_case_ack_statuses:
        reasons.append("historical_v1_replacement_not_accepted_for_canary")
    if not use_case_ack_statuses or use_case_ack_statuses[-1] != "promoted":
        reasons.append("historical_v1_replacement_not_promoted")

    triggering_completed_count = int(
        use_case_request.get("trigger_completed_count") or 0
    )
    trigger_rows = [
        row
        for row in feedback_rows
        if int(row.get("completed_count") or 0) == triggering_completed_count
        and str(row.get("scenario") or "") in safe_names
        and use_case_request_id in (row.get("post_deployment_repair_request_ids") or [])
    ]
    trigger_row = trigger_rows[0] if len(trigger_rows) == 1 else {}
    trigger_scenario = str(trigger_row.get("scenario") or "")
    trigger_versions = trigger_row.get("generated_tool_versions")
    trigger_outcome = (
        _outcome(candidate_by_name[trigger_scenario])
        if trigger_scenario in candidate_by_name
        else None
    )
    trigger_proves_v1_failure = bool(
        len(trigger_rows) == 1
        and trigger_scenario == safe_names[0]
        and isinstance(trigger_versions, dict)
        and trigger_versions.get(LIFECYCLE_USE_CASE_TOOL) == 1
        and LIFECYCLE_USE_CASE_TOOL in (trigger_row.get("generated_tools_called") or [])
        and LIFECYCLE_USE_CASE_TOOL
        in (trigger_row.get("generated_tool_contract_failures") or [])
        and trigger_outcome is not None
        and trigger_outcome < 1.0
    )
    if not trigger_proves_v1_failure:
        reasons.append("historical_v1_trigger_did_not_prove_observed_failure")

    future_v2_rows: list[dict[str, Any]] = []
    for row in feedback_rows:
        versions = row.get("generated_tool_versions")
        if (
            int(row.get("completed_count") or 0) > triggering_completed_count
            and str(row.get("scenario") or "") in safe_names
            and isinstance(versions, dict)
            and versions.get(LIFECYCLE_USE_CASE_TOOL) == 2
            and LIFECYCLE_USE_CASE_TOOL in (row.get("generated_tools_called") or [])
        ):
            future_v2_rows.append(row)
    expected_future_v2_call_count = len(safe_names) - 1
    if len(future_v2_rows) != expected_future_v2_call_count:
        reasons.append("future_v2_safe_task_call_coverage_mismatch")
    future_v2_exact_successes = sum(
        str(row.get("scenario") or "") in candidate_by_name
        and _exact_targeted_abstention(
            candidate_by_name[str(row.get("scenario") or "")]
        )
        for row in future_v2_rows
    )
    if future_v2_exact_successes < int(spec["future_v2_exact_minimum"]):
        reasons.append("future_v2_exact_success_gate_failed")
    future_v2_success_flips = sum(
        str(row.get("scenario") or "") in candidate_by_name
        and str(row.get("scenario") or "") in control_by_name
        and _exact_targeted_abstention(
            candidate_by_name[str(row.get("scenario") or "")]
        )
        and not _exact_outcome(control_by_name[str(row.get("scenario") or "")])
        for row in future_v2_rows
    )
    if future_v2_success_flips < int(spec["future_v2_success_flip_minimum"]):
        reasons.append("future_v2_affirmative_success_flip_missing")

    final_validation_contract = _target_validation_contract_identity(registry_dir)
    if final_validation_contract is None:
        reasons.append("promoted_v2_validation_contract_binding_invalid")
    repair_acceptance_candidates = [
        row
        for row in protocol_events
        if row.get("event") == "post_deployment_tool_repair_accepted"
        and (
            row.get("request_id") == use_case_request_id
            or (
                row.get("tool_name") == LIFECYCLE_USE_CASE_TOOL
                and row.get("source_tool_version") == 1
            )
        )
    ]
    repair_acceptance_events = [
        row
        for row in repair_acceptance_candidates
        if row.get("request_id") == use_case_request_id
        and row.get("tool_name") == LIFECYCLE_USE_CASE_TOOL
        and row.get("source_tool_version") == 1
        and row.get("new_tool_version") == 2
        and isinstance(final_validation_contract, dict)
        and row.get("validation_contract_hash")
        == final_validation_contract.get("contract_hash")
        and row.get("triggering_task_replayed") is False
        and row.get("mode") == protocol.get("mode")
        and _event_path_matches(run_root, row.get("run_root"), run_root)
        and _event_path_matches(run_root, row.get("run_dir"), candidate_dir)
    ]
    repair_acceptance_binding_mismatches = len(repair_acceptance_candidates) - len(
        repair_acceptance_events
    )
    if not repair_acceptance_events:
        reasons.append("postdeployment_v2_acceptance_event_missing")
    elif len(repair_acceptance_events) > 1:
        reasons.append("postdeployment_v2_acceptance_event_not_unique")
    if repair_acceptance_binding_mismatches:
        reasons.append("postdeployment_v2_acceptance_event_binding_mismatch")

    registry = _load_json(registry_dir / "registry_manifest.json")
    final_entry = (
        registry.get("tools", {}).get(LIFECYCLE_USE_CASE_TOOL)
        if isinstance(registry, dict) and isinstance(registry.get("tools"), dict)
        else None
    )
    if not isinstance(final_entry, dict) or any(
        (final_entry.get("version") != 2, final_entry.get("retired") is not False)
    ):
        reasons.append("promoted_repaired_version_not_active_in_final_registry")

    return (
        {
            "use_case_tool": LIFECYCLE_USE_CASE_TOOL,
            "use_case_request_id": use_case_request_id or None,
            "use_case_repair_reason_codes": list(
                use_case_request.get("trigger_reason_codes") or []
            ),
            "use_case_acknowledgement_statuses": use_case_ack_statuses,
            "historical_v1_trigger_scenario": trigger_scenario or None,
            "historical_v1_trigger_outcome": trigger_outcome,
            "historical_v1_observed_failure_proved": trigger_proves_v1_failure,
            "repaired_version_future_call_count": len(future_v2_rows),
            "repaired_version_future_exact_success_count": future_v2_exact_successes,
            "repaired_version_future_success_flip_count": future_v2_success_flips,
            "repair_acceptance_event_count": len(repair_acceptance_events),
            "repair_acceptance_event_binding_mismatch_count": (
                repair_acceptance_binding_mismatches
            ),
            "promoted_v2_validation_contract": final_validation_contract,
        },
        list(dict.fromkeys(reasons)),
    )


def _retirement_successor_transition_report(
    *,
    run_root: Path,
    candidate_dir: Path,
    registry_dir: Path,
    protocol: dict[str, Any],
    protocol_events: list[dict[str, Any]],
    repair_requests: list[dict[str, Any]],
    acknowledgements: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
    selection_by_name: dict[str, dict[str, Any]],
    trajectory_by_name: dict[str, dict[str, tuple[str, ...]]],
    candidate_by_name: dict[str, dict[str, Any]],
    control_by_name: dict[str, dict[str, Any]],
    roles: dict[str, tuple[str, ...]],
    transition: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Authenticate bounded retirement followed by new validated successors.

    The transition is predeclared by the cohort specification.  This verifier
    does not infer a convenient replacement after seeing a run, and it does not
    inspect hidden evaluator values or replay the task that raised the alarm.
    """

    reasons: list[str] = []
    source_tool_name = str(transition["source_tool_name"])
    source_tool_version = int(transition["source_tool_version"])
    repair_kind = str(transition["repair_kind"])
    trigger_reason_code = str(transition["trigger_reason_code"])
    bounded_attempt_count = int(transition["bounded_repair_attempt_count"])
    terminal_status = str(transition["terminal_acknowledgement_status"])
    terminal_reason = str(transition["terminal_retirement_reason"])
    successor_specs = transition.get("successors")
    if not isinstance(successor_specs, dict) or not successor_specs:
        raise ValueError("Retirement-successor transition has no successors.")
    successor_names = tuple(sorted(str(name) for name in successor_specs))
    source_contract = PINNED_LIFECYCLE_V1_CONTRACTS.get(source_tool_name, {})
    source_canonical_key = str(source_contract.get("canonical_key") or "")
    if not source_canonical_key:
        reasons.append("source_v1_canonical_key_not_pinned")

    indexed_candidate_events = [
        (index, row)
        for index, row in enumerate(protocol_events)
        if row.get("mode") == protocol.get("mode")
        and _event_path_matches(run_root, row.get("run_root"), run_root)
        and _event_path_matches(run_root, row.get("run_dir"), candidate_dir)
    ]

    trigger_role = str(transition["trigger_role"])
    trigger_names = tuple(roles.get(trigger_role, ()))
    if len(trigger_names) != 1:
        reasons.append("retirement_successor_trigger_role_not_singleton")
    trigger_name = trigger_names[0] if len(trigger_names) == 1 else ""

    source_requests = [
        row
        for row in repair_requests
        if row.get("tool_name") == source_tool_name
        and row.get("source_tool_version") == source_tool_version
        and row.get("repair_kind") == repair_kind
    ]
    if len(source_requests) != 1:
        reasons.append("source_v1_repair_request_count_mismatch")
    source_request = source_requests[0] if len(source_requests) == 1 else {}
    request_id = str(source_request.get("request_id") or "")
    if trigger_reason_code not in (source_request.get("trigger_reason_codes") or []):
        reasons.append("source_v1_repair_reason_mismatch")

    source_acks = [
        row
        for row in acknowledgements
        if str(row.get("request_id") or "") == request_id
    ]
    source_ack_statuses = [str(row.get("status") or "") for row in source_acks]
    if source_ack_statuses != [terminal_status]:
        reasons.append("source_v1_terminal_acknowledgement_mismatch")

    triggering_completed_count = int(source_request.get("trigger_completed_count") or 0)
    terminal_acknowledgement_proved = bool(
        len(source_acks) == 1
        and source_acks[0].get("tool_name") == source_tool_name
        and source_acks[0].get("new_version") == source_tool_version
        and source_acks[0].get("status") == terminal_status
        and source_acks[0].get("acknowledged_after_completed_count")
        == triggering_completed_count
        and source_acks[0].get("eligible_from_completed_count")
        == triggering_completed_count + 1
        and source_acks[0].get("future_tasks_only") is True
        and source_acks[0].get("triggering_task_replay_allowed") is False
    )
    if not terminal_acknowledgement_proved:
        reasons.append("source_v1_terminal_acknowledgement_evidence_mismatch")
    trigger_rows = [
        row
        for row in feedback_rows
        if int(row.get("completed_count") or 0) == triggering_completed_count
        and str(row.get("scenario") or "") == trigger_name
        and request_id in (row.get("post_deployment_repair_request_ids") or [])
    ]
    trigger_row = trigger_rows[0] if len(trigger_rows) == 1 else {}
    trigger_versions = trigger_row.get("generated_tool_versions")
    trigger_outcome = (
        _outcome(candidate_by_name[trigger_name])
        if trigger_name in candidate_by_name
        else None
    )
    trigger_proved_failure = bool(
        len(trigger_rows) == 1
        and isinstance(trigger_versions, dict)
        and trigger_versions.get(source_tool_name) == source_tool_version
        and source_tool_name in (trigger_row.get("generated_tools_called") or [])
        and source_tool_name
        in (trigger_row.get("generated_tool_contract_failures") or [])
        and trigger_outcome is not None
        and trigger_outcome < 1.0
    )
    if not trigger_proved_failure:
        reasons.append("source_v1_trigger_did_not_prove_observed_failure")

    source_failure_event_indices = [
        index
        for index, row in indexed_candidate_events
        if row.get("event") == "post_deployment_public_contract_failure"
        and row.get("tool_name") == source_tool_name
        and row.get("tool_version") == source_tool_version
        and row.get("canonical_key") == source_canonical_key
        and row.get("raw_hidden_case_values_logged") is False
    ]
    queued_event_indices = [
        index
        for index, row in indexed_candidate_events
        if row.get("event") == "post_deployment_tool_repair_queued"
        and row.get("request_id") == request_id
        and row.get("tool_name") == source_tool_name
        and row.get("repair_kind") == repair_kind
        and row.get("source_tool_version") == source_tool_version
        and row.get("eligible_from_completed_count") == triggering_completed_count + 1
        and row.get("future_tasks_only") is True
    ]
    if len(source_failure_event_indices) != 1:
        reasons.append("source_v1_public_contract_failure_event_mismatch")
    if len(queued_event_indices) != 1:
        reasons.append("source_v1_repair_queued_event_mismatch")

    indexed_attempt_events = [
        (index, row)
        for index, row in indexed_candidate_events
        if row.get("event") == "post_deployment_tool_repair_attempted"
        and row.get("request_id") == request_id
        and row.get("tool_name") == source_tool_name
    ]
    attempt_events = [row for _, row in indexed_attempt_events]
    attempt_event_indices = [index for index, _ in indexed_attempt_events]
    observed_attempts = [row.get("attempt") for row in attempt_events]
    expected_attempts = list(range(1, bounded_attempt_count + 1))
    bounded_repair_proved = bool(
        observed_attempts == expected_attempts
        and all(
            row.get("accepted") is False
            and isinstance(row.get("candidate_count"), int)
            and not isinstance(row.get("candidate_count"), bool)
            and int(row["candidate_count"]) >= 1
            for row in attempt_events
        )
    )
    if not bounded_repair_proved:
        reasons.append("source_v1_bounded_repair_evidence_mismatch")

    indexed_raw_retirement_events = [
        (index, row)
        for index, row in indexed_candidate_events
        if row.get("event") == "post_deployment_tool_repair_retired"
        and row.get("request_id") == request_id
        and row.get("tool_name") == source_tool_name
        and row.get("source_tool_version") == source_tool_version
        and row.get("status") == terminal_status
        and row.get("reason") == terminal_reason
        and row.get("future_tasks_only") is True
        and row.get("triggering_task_replayed") is False
    ]
    indexed_retirement_events = [
        (index, row)
        for index, row in indexed_raw_retirement_events
        if row.get("event") == "post_deployment_tool_repair_retired"
        and isinstance(row.get("entry_was_active"), bool)
        and isinstance(row.get("entry_was_retired_before_terminalization"), bool)
        and (
            row.get("entry_was_active")
            != row.get("entry_was_retired_before_terminalization")
        )
        and row.get("entry_retired") is True
        and row.get("retired_canonical_key") == source_canonical_key
        and row.get("terminal_tombstone_persisted") is True
        and row.get("same_run_rebirth_suppressed") is True
    ]
    raw_retirement_event_indices = [index for index, _ in indexed_raw_retirement_events]
    retirement_events = [row for _, row in indexed_retirement_events]
    retirement_event_indices = [index for index, _ in indexed_retirement_events]
    if len(indexed_raw_retirement_events) != 1:
        reasons.append("source_v1_terminal_retirement_event_mismatch")
    elif len(retirement_events) != 1:
        reasons.append("source_v1_terminal_retirement_postcondition_mismatch")

    source_causal_prefix_proved = bool(
        len(source_failure_event_indices) == 1
        and len(queued_event_indices) == 1
        and bounded_repair_proved
        and len(attempt_event_indices) == bounded_attempt_count
        and len(retirement_event_indices) == 1
        and source_failure_event_indices[0]
        < queued_event_indices[0]
        < attempt_event_indices[0]
        and attempt_event_indices[-1] < retirement_event_indices[0]
    )
    if not source_causal_prefix_proved:
        reasons.append("source_v1_failure_repair_retirement_order_mismatch")

    registry_path = registry_dir / "registry_manifest.json"
    registry = _load_json(registry_path)
    registry_tools = registry.get("tools") if isinstance(registry, dict) else None
    registry_tools = registry_tools if isinstance(registry_tools, dict) else {}
    source_identity = _registry_entry_identity(
        registry_tools.get(source_tool_name), expected_name=source_tool_name
    )
    source_retired = bool(
        isinstance(source_identity, dict)
        and source_identity.get("version") == source_tool_version
        and source_identity.get("retired") is True
    )
    if not source_retired:
        reasons.append("source_v1_not_retired_in_final_registry")

    tombstone_path = registry_dir / TERMINAL_RETIREMENT_TOMBSTONE_FILENAME
    tombstone_payload: dict[str, Any] = {}
    try:
        if not tombstone_path.is_file() or tombstone_path.is_symlink():
            raise ValueError("missing_or_symlink")
        loaded_tombstone = _load_json(tombstone_path)
        canonical_keys = loaded_tombstone.get("canonical_keys")
        tool_names = loaded_tombstone.get("tool_names")
        if (
            loaded_tombstone.get("schema_version") != 1
            or not isinstance(canonical_keys, list)
            or not isinstance(tool_names, list)
            or any(not isinstance(item, str) or not item for item in canonical_keys)
            or any(not isinstance(item, str) or not item for item in tool_names)
            or len(canonical_keys) != len(set(canonical_keys))
            or len(tool_names) != len(set(tool_names))
        ):
            raise ValueError("invalid_schema")
        tombstone_payload = loaded_tombstone
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        reasons.append("terminal_retirement_tombstone_invalid")
    durable_source_tombstone = bool(
        source_tool_name in (tombstone_payload.get("tool_names") or [])
        and source_canonical_key in (tombstone_payload.get("canonical_keys") or [])
    )
    if not durable_source_tombstone:
        reasons.append("source_v1_terminal_retirement_tombstone_missing")

    source_presence_fields = (
        "generated_tools_visible",
        "generated_tools_called",
        "generated_tools_attempted",
        "generated_tools_failed",
        "generated_tool_contract_failures",
    )
    post_trigger_source_presence: list[str] = []
    for feedback in feedback_rows:
        if int(feedback.get("completed_count") or 0) <= triggering_completed_count:
            continue
        scenario_name = str(feedback.get("scenario") or "")
        evidence_sources: tuple[tuple[str, dict[str, Any]], ...] = (
            ("feedback", feedback),
            ("selection", selection_by_name.get(scenario_name, {})),
            ("trajectory", trajectory_by_name.get(scenario_name, {})),
        )
        for evidence_label, evidence in evidence_sources:
            for field in source_presence_fields:
                if source_tool_name in (evidence.get(field) or []):
                    post_trigger_source_presence.append(
                        f"{scenario_name}:{evidence_label}:{field}"
                    )
            versions = evidence.get("generated_tool_versions")
            if isinstance(versions, dict) and source_tool_name in versions:
                post_trigger_source_presence.append(
                    f"{scenario_name}:{evidence_label}:generated_tool_versions"
                )
    if post_trigger_source_presence:
        reasons.append("retired_source_present_after_trigger")

    checkpoint_tombstone_mismatches: list[str] = []
    checkpoint_root = candidate_dir / "registry_checkpoints"
    for completed_count, scenario_name in enumerate(
        (str(row.get("scenario") or "") for row in feedback_rows), start=1
    ):
        checkpoint_dir = checkpoint_root / (
            f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario_name)}"
        )
        checkpoint_manifest_path = checkpoint_dir / "registry_manifest.json"
        checkpoint_metadata_path = checkpoint_dir / "checkpoint.json"
        checkpoint_tombstone_path = (
            checkpoint_dir / TERMINAL_RETIREMENT_TOMBSTONE_FILENAME
        )
        try:
            checkpoint_manifest = _load_json(checkpoint_manifest_path)
            checkpoint_metadata = _load_json(checkpoint_metadata_path)
            checkpoint_tools = checkpoint_manifest.get("tools")
            checkpoint_source = (
                checkpoint_tools.get(source_tool_name)
                if isinstance(checkpoint_tools, dict)
                else None
            )
            checkpoint_source_identity = _registry_entry_identity(
                checkpoint_source, expected_name=source_tool_name
            )
            if completed_count <= triggering_completed_count:
                if not (
                    isinstance(checkpoint_source_identity, dict)
                    and checkpoint_source_identity.get("version") == source_tool_version
                    and checkpoint_source_identity.get("retired") is False
                ):
                    raise ValueError("source_not_active_before_retirement")
                if checkpoint_tombstone_path.exists():
                    early_tombstone = _load_json(checkpoint_tombstone_path)
                    if source_tool_name in (early_tombstone.get("tool_names") or []):
                        raise ValueError("source_tombstoned_before_retirement")
                    if source_canonical_key in (
                        early_tombstone.get("canonical_keys") or []
                    ):
                        raise ValueError("source_key_tombstoned_before_retirement")
                continue
            copied_files = checkpoint_metadata.get("copied_files")
            if (
                not checkpoint_tombstone_path.is_file()
                or checkpoint_tombstone_path.is_symlink()
                or not isinstance(copied_files, list)
                or TERMINAL_RETIREMENT_TOMBSTONE_FILENAME not in copied_files
                or not isinstance(checkpoint_source_identity, dict)
                or checkpoint_source_identity.get("version") != source_tool_version
                or checkpoint_source_identity.get("retired") is not True
            ):
                raise ValueError("retirement_not_persisted")
            checkpoint_tombstone = _load_json(checkpoint_tombstone_path)
            if (
                checkpoint_tombstone.get("schema_version") != 1
                or source_tool_name
                not in (checkpoint_tombstone.get("tool_names") or [])
                or source_canonical_key
                not in (checkpoint_tombstone.get("canonical_keys") or [])
            ):
                raise ValueError("tombstone_not_persisted")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            checkpoint_tombstone_mismatches.append(f"{scenario_name}:{exc}")
    if checkpoint_tombstone_mismatches:
        reasons.append("terminal_retirement_checkpoint_persistence_mismatch")

    contract_identities = _validation_contract_identities(registry_dir)
    if contract_identities is None:
        contract_identities = {}
        reasons.append("successor_validation_contract_set_invalid")
    new_validation_names = {
        tool_name
        for tool_name, identity in contract_identities.items()
        if tool_name not in PINNED_LIFECYCLE_V1_CONTRACTS
        and isinstance(identity.get("canonical_key"), str)
        and str(identity["canonical_key"]).startswith("validation:")
    }
    exact_successor_set = new_validation_names == set(successor_names)
    if transition.get("exact_new_validation_successor_set") is True and not (
        exact_successor_set
    ):
        reasons.append("exact_new_validation_successor_set_mismatch")

    birth_rows = _read_jsonl(candidate_dir / "tool_birth_events.jsonl")
    successor_reports: dict[str, Any] = {}
    for successor_name in successor_names:
        successor_spec = successor_specs[successor_name]
        canonical_key = str(successor_spec["canonical_key"])
        expected_version = int(successor_spec["version"])
        role = str(successor_spec["role"])
        role_names = tuple(roles.get(role, ()))
        entry_payload = registry_tools.get(successor_name)
        entry_identity = _registry_entry_identity(
            entry_payload, expected_name=successor_name
        )
        contract_identity = contract_identities.get(successor_name)
        validation = (
            entry_payload.get("validation") if isinstance(entry_payload, dict) else None
        )
        active_and_validated = bool(
            isinstance(entry_identity, dict)
            and entry_identity.get("version") == expected_version
            and entry_identity.get("retired") is False
            and isinstance(contract_identity, dict)
            and contract_identity.get("tool_name") == successor_name
            and contract_identity.get("tool_version") == expected_version
            and contract_identity.get("canonical_key") == canonical_key
            and contract_identity.get("tool_code_hash")
            == entry_identity.get("code_hash")
            and contract_identity.get("tool_spec_hash")
            == entry_identity.get("public_spec_sha256")
            and isinstance(validation, dict)
            and validation.get("accepted") is True
            and int(validation.get("held_out_check_count") or 0) >= 1
            and int(validation.get("negative_applicability_count") or 0) >= 1
            and validation.get("runtime_smoke_passed") is True
        )
        if not active_and_validated:
            reasons.append(f"successor_not_active_and_validated:{successor_name}")

        matching_births = [
            row
            for row in birth_rows
            if row.get("accepted") is True
            and row.get("tool_name") == successor_name
            and row.get("canonical_key") == canonical_key
            and row.get("source_task_id_redacted") is True
            and row.get("runtime_smoke_passed") is True
            and row.get("errors") == []
        ]
        if len(matching_births) != 1:
            reasons.append(f"successor_birth_event_mismatch:{successor_name}")

        successor_validation_event_indices = [
            index
            for index, row in indexed_candidate_events
            if row.get("event") == "validation_passed"
            and row.get("tool_name") == successor_name
            and row.get("canonical_key") == canonical_key
            and row.get("errors") == []
            and row.get("runtime_smoke_passed") is True
        ]
        successor_birth_event_indices = [
            index
            for index, row in indexed_candidate_events
            if row.get("event") == "tool_birth_succeeded"
            and row.get("tool_name") == successor_name
            and row.get("canonical_key") == canonical_key
            and isinstance(row.get("validation_contract_hash"), str)
        ]
        successor_registry_event_indices = [
            index
            for index, row in indexed_candidate_events
            if row.get("event") == "registry_saved"
            and row.get("tool_name") == successor_name
            and row.get("tool_version") == expected_version
            and isinstance(row.get("validation_contract_hash"), str)
        ]
        successor_causal_order_proved = bool(
            len(retirement_event_indices) == 1
            and len(successor_validation_event_indices) == 1
            and len(successor_birth_event_indices) == 1
            and len(successor_registry_event_indices) == 1
            and retirement_event_indices[0]
            < successor_validation_event_indices[0]
            < successor_birth_event_indices[0]
            < successor_registry_event_indices[0]
        )
        if not successor_causal_order_proved:
            reasons.append(f"successor_causal_birth_order_mismatch:{successor_name}")

        eligible_rows: list[dict[str, Any]] = []
        for feedback in feedback_rows:
            scenario_name = str(feedback.get("scenario") or "")
            selection = selection_by_name.get(scenario_name, {})
            versions = feedback.get("generated_tool_versions")
            selection_versions = selection.get("generated_tool_versions")
            if (
                scenario_name in role_names
                and int(feedback.get("completed_count") or 0)
                > triggering_completed_count
                and isinstance(versions, dict)
                and versions.get(successor_name) == expected_version
                and isinstance(selection_versions, dict)
                and selection_versions.get(successor_name) == expected_version
                and _selection_has_tool(
                    feedback, "generated_tools_visible", successor_name
                )
                and _selection_has_tool(
                    feedback, "generated_tools_called", successor_name
                )
                and _selection_has_tool(
                    selection, "generated_tools_visible", successor_name
                )
                and _selection_has_tool(
                    selection, "generated_tools_called", successor_name
                )
                and successor_name not in (feedback.get("generated_tools_failed") or [])
                and successor_name
                not in (feedback.get("generated_tool_contract_failures") or [])
            ):
                eligible_rows.append(feedback)

        visible_and_called_count = len(eligible_rows)
        exact_success_count = sum(
            str(row.get("scenario") or "") in candidate_by_name
            and _exact_targeted_abstention(
                candidate_by_name[str(row.get("scenario") or "")]
            )
            for row in eligible_rows
        )
        success_flip_count = sum(
            str(row.get("scenario") or "") in candidate_by_name
            and str(row.get("scenario") or "") in control_by_name
            and _exact_targeted_abstention(
                candidate_by_name[str(row.get("scenario") or "")]
            )
            and not _exact_outcome(control_by_name[str(row.get("scenario") or "")])
            for row in eligible_rows
        )
        if visible_and_called_count < int(successor_spec["minimum_visible_and_called"]):
            reasons.append(f"successor_call_coverage_gate_failed:{successor_name}")
        if exact_success_count < int(successor_spec["minimum_exact_successes"]):
            reasons.append(f"successor_exact_success_gate_failed:{successor_name}")
        if success_flip_count < int(successor_spec["minimum_success_flips"]):
            reasons.append(f"successor_success_flip_gate_failed:{successor_name}")
        if any(
            int(row.get("completed_count") or 0) <= triggering_completed_count
            and successor_name in (row.get("generated_tools_called") or [])
            for row in feedback_rows
        ):
            reasons.append(f"successor_used_nonprospectively:{successor_name}")
        if any(
            source_tool_name in (row.get("generated_tools_called") or [])
            for row in eligible_rows
        ):
            reasons.append(f"retired_source_called_with_successor:{successor_name}")

        successor_reports[successor_name] = {
            "canonical_key": canonical_key,
            "expected_version": expected_version,
            "role": role,
            "role_task_count": len(role_names),
            "birth_event_count": len(matching_births),
            "validation_protocol_event_indices": successor_validation_event_indices,
            "birth_protocol_event_indices": successor_birth_event_indices,
            "registry_protocol_event_indices": successor_registry_event_indices,
            "causal_birth_order_proved": successor_causal_order_proved,
            "active_and_validated": active_and_validated,
            "visible_and_called_count": visible_and_called_count,
            "exact_success_count": exact_success_count,
            "success_flip_count": success_flip_count,
            "registry_identity": entry_identity,
            "validation_contract": contract_identity,
        }

    return (
        {
            "source_tool_name": source_tool_name,
            "source_tool_version": source_tool_version,
            "repair_request_id": request_id or None,
            "repair_reason_codes": list(
                source_request.get("trigger_reason_codes") or []
            ),
            "acknowledgement_statuses": source_ack_statuses,
            "terminal_acknowledgement_proved": terminal_acknowledgement_proved,
            "trigger_scenario": trigger_name or None,
            "trigger_outcome": trigger_outcome,
            "trigger_observed_failure_proved": trigger_proved_failure,
            "bounded_repair_attempt_count": len(attempt_events),
            "bounded_repair_attempts": observed_attempts,
            "bounded_repair_failure_proved": bounded_repair_proved,
            "public_contract_failure_event_indices": source_failure_event_indices,
            "repair_queued_event_indices": queued_event_indices,
            "repair_attempt_event_indices": attempt_event_indices,
            "raw_terminal_retirement_event_count": len(indexed_raw_retirement_events),
            "raw_terminal_retirement_event_indices": raw_retirement_event_indices,
            "terminal_retirement_event_count": len(retirement_events),
            "terminal_retirement_event_indices": retirement_event_indices,
            "failure_repair_retirement_order_proved": source_causal_prefix_proved,
            "source_retired": source_retired,
            "source_registry_identity": source_identity,
            "source_canonical_key": source_canonical_key,
            "durable_source_tombstone": durable_source_tombstone,
            "terminal_retirement_tombstone": tombstone_payload or None,
            "post_trigger_source_presence": post_trigger_source_presence,
            "checkpoint_tombstone_mismatches": checkpoint_tombstone_mismatches,
            "expected_successor_names": list(successor_names),
            "observed_new_validation_successor_names": sorted(new_validation_names),
            "exact_successor_set": exact_successor_set,
            "successors": successor_reports,
        },
        list(dict.fromkeys(reasons)),
    )


def _write_report(run_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    (run_root / "lifecycle_repair_validation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _verify_frozen_transfer(
    *,
    run_root: Path,
    protocol: dict[str, Any],
    comparison: dict[str, Any],
    cache_report: dict[str, Any],
    benchmark_manifest_path: Path,
    benchmark_manifest: dict[str, Any],
    expected_tasks: int,
) -> dict[str, Any]:
    """Verify the exact promoted dev10 registry on the disjoint dev30 cohort."""

    manifest_type = str(benchmark_manifest.get("manifest_type") or "")
    if manifest_type not in TRANSFER_MANIFEST_TYPES:
        raise ValueError(f"Unknown lifecycle transfer cohort: {manifest_type!r}")
    spec = COHORT_SPECS[manifest_type]
    transition = spec.get("retirement_successor_transition")
    successor_specs = (
        transition.get("successors", {}) if isinstance(transition, dict) else {}
    )
    successor_names = tuple(sorted(str(name) for name in successor_specs))
    assessed_tool_names = successor_names or (LIFECYCLE_USE_CASE_TOOL,)
    expected_order = tuple(spec["order"])
    roles = spec["roles"]
    safe_names = tuple(roles[str(spec["safe_role"])])
    contact_names = tuple(roles[str(spec["contact_role"])])
    working_overlap_names = tuple(roles["working_generated_overlap"])
    unrelated_preservation_names = tuple(roles["unrelated_native_preservation"])
    reasons: list[str] = []

    manifest_order = _manifest_task_names(benchmark_manifest, "transfer_30")
    benchmark_sha256 = hashlib.sha256(benchmark_manifest_path.read_bytes()).hexdigest()
    if expected_tasks != 30 or protocol.get("scenario_count") != 30:
        reasons.append("transfer_task_count_mismatch")
    if manifest_order != expected_order or len(set(manifest_order)) != 30:
        reasons.append("transfer_scenario_order_mismatch")
    if benchmark_manifest.get("scenario_order_sha256") != spec["order_sha256"]:
        reasons.append("transfer_manifest_order_pin_mismatch")
    if protocol.get("scenario_order_sha256") != spec["order_sha256"]:
        reasons.append("transfer_protocol_order_pin_mismatch")
    if protocol.get("benchmark_manifest_sha256") != benchmark_sha256:
        reasons.append("transfer_benchmark_bytes_do_not_match_protocol")
    if protocol.get("manifest_type") != manifest_type:
        reasons.append("transfer_protocol_manifest_type_mismatch")
    if benchmark_manifest.get("lifecycle_evidence_mode") != (
        "frozen_retired_source_and_successor_registry_transfer"
        if isinstance(transition, dict)
        else "frozen_promoted_registry_transfer"
    ):
        reasons.append("transfer_lifecycle_evidence_mode_mismatch")
    if benchmark_manifest.get("predeclared_gates") != spec["predeclared_gates"]:
        reasons.append("transfer_predeclared_gate_contract_mismatch")
    if (
        benchmark_manifest.get("preserved_working_tool_provenance")
        != PRESERVED_WORKING_TOOL_PROVENANCE
    ):
        reasons.append("transfer_working_tool_provenance_contract_mismatch")
    if benchmark_manifest.get("working_path_evidence") != WORKING_PATH_EVIDENCE:
        reasons.append("transfer_working_path_evidence_contract_mismatch")
    (
        working_path_source_evidence,
        working_path_source_evidence_reasons,
    ) = _working_path_source_evidence_report(run_root=run_root)
    reasons.extend(
        f"transfer_{reason}" for reason in working_path_source_evidence_reasons
    )
    observed_roles = benchmark_manifest.get("validation_roles")
    if not isinstance(observed_roles, dict) or set(observed_roles) != set(roles):
        reasons.append("transfer_validation_role_set_mismatch")
    else:
        for role, expected_names in roles.items():
            if _role_names(benchmark_manifest, role) != tuple(expected_names):
                reasons.append(f"transfer_{role}_membership_mismatch")

    required_protocol = {
        "mode": "transfer_30",
        "publication_gate_purpose": "development-diagnostic",
        "generation_enabled": False,
        "candidate_generated_tools_enabled": False,
        "lifecycle_mutation_enabled": False,
        "sage_policy": "none",
        "actor_selection_mode": "policy",
        "control_condition": "matched_policy_wrapper_without_generated_tools",
        "control_agent_runtime": "sage_wrapped",
        "candidate_agent_runtime": "sage_wrapped",
        "fresh_control_required": True,
        "parallel_arms": True,
        "control_cache_mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": 30,
        "openai_response_cache_enabled": False,
        "openai_response_cache_mode": "off",
        "sage_task_cache_enabled": False,
        "cross_run_failure_memory_enabled": False,
    }
    for field, expected in required_protocol.items():
        if protocol.get(field) != expected:
            reasons.append(f"transfer_protocol_{field}_mismatch")
    required_cache = {
        "mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": 30,
        "cache_accessed": False,
        "fresh_control_enforced": True,
    }
    if any(
        cache_report.get(field) != expected
        for field, expected in required_cache.items()
    ):
        reasons.append("transfer_control_cache_not_fully_fresh")
    cache = comparison.get("control_cache")
    if not isinstance(cache, dict) or any(
        cache.get(field) != expected
        for field, expected in {
            "mode": "off",
            "cache_accessed": False,
            "cached_control_tasks": 0,
            "fresh_control_tasks": 30,
        }.items()
    ):
        reasons.append("transfer_comparison_control_not_fully_fresh")
    if comparison.get("runtime_exception_count") != 0:
        reasons.append("transfer_runtime_exceptions_present")
    if comparison.get("candidate_stopped_early") is not False:
        reasons.append("transfer_candidate_stopped_early")

    evaluator = outcome_evaluator_manifest()
    (
        control_dir,
        candidate_dir,
        parallel_execution,
        trajectory_evidence,
        trajectory_error,
    ) = _verify_execution_artifacts(
        run_root,
        protocol,
        expected_tasks=30,
        expected_evaluator=evaluator,
        expected_mode="transfer_30",
        allow_candidate_generation_usage=False,
    )
    if trajectory_error is not None:
        reasons.append("transfer_trajectory_integrity_failed")
    matched_runtimes = _strict_run_verifier._verify_matched_policy_runtimes(
        control_dir, candidate_dir
    )
    _strict_run_verifier._verify_no_scenario_transform_failures(candidate_dir)
    control_rows = _result_rows(control_dir)
    candidate_rows = _result_rows(candidate_dir)
    control_by_name = {str(row.get("name") or ""): row for row in control_rows}
    candidate_by_name = {str(row.get("name") or ""): row for row in candidate_rows}
    if (
        tuple(control_by_name) != expected_order
        or tuple(candidate_by_name) != expected_order
    ):
        reasons.append("transfer_result_task_order_mismatch")
    if len(control_by_name) != 30 or len(candidate_by_name) != 30:
        reasons.append("transfer_result_task_coverage_mismatch")

    provenance = protocol.get("registry_transfer_provenance")
    source_report: dict[str, Any] = {}
    source_inventory: list[dict[str, Any]] = []
    source_order: tuple[str, ...] = ()
    source_run_root: Path | None = None
    source_registry_dir: Path | None = None
    if not isinstance(provenance, dict):
        reasons.append("transfer_registry_provenance_missing")
        provenance = {}
    try:
        source_run_root = _strict_run_verifier._resolve_declared_path(
            run_root,
            provenance.get("source_run_root"),
            "registry_transfer_provenance.source_run_root",
        )
        if source_run_root == run_root.resolve():
            reasons.append("transfer_source_is_destination")
        source_report = verify(source_run_root, 10)
        if source_report.get("status") != "pass" or source_report.get(
            "manifest_type"
        ) != spec.get(
            "source_manifest_type",
            "development_diagnostic_lifecycle_repair_dev10",
        ):
            reasons.append("transfer_source_dev10_not_passing")
        source_protocol_path = source_run_root / "protocol_manifest.json"
        source_report_path = source_run_root / "lifecycle_repair_validation_report.json"
        source_protocol = _load_json(source_protocol_path)
        source_manifest_path = _strict_run_verifier._resolve_declared_path(
            source_run_root,
            source_protocol.get("benchmark_manifest_path"),
            "source benchmark_manifest_path",
        )
        source_order = _manifest_task_names(_load_json(source_manifest_path))
        source_registry_dir = _strict_run_verifier._resolve_declared_path(
            source_run_root,
            source_protocol.get("registry_dir"),
            "source registry_dir",
        )
        source_inventory = _registry_inventory(source_registry_dir)
        source_inventory_hash = _inventory_sha256(source_inventory)
        if isinstance(transition, dict):
            source_identity = _target_tool_identity(
                source_registry_dir,
                tool_name=str(transition["source_tool_name"]),
                expected_retired=True,
                minimum_version=int(transition["source_tool_version"]),
            )
            source_contract_identity = None
            successor_identities = {
                tool_name: _target_tool_identity(
                    source_registry_dir,
                    tool_name=tool_name,
                    expected_retired=False,
                    minimum_version=int(successor_specs[tool_name]["version"]),
                )
                for tool_name in successor_names
            }
            successor_contract_identities = {
                tool_name: _target_validation_contract_identity(
                    source_registry_dir,
                    tool_name=tool_name,
                )
                for tool_name in successor_names
            }
        else:
            source_identity = _target_tool_identity(source_registry_dir)
            source_contract_identity = _target_validation_contract_identity(
                source_registry_dir
            )
            successor_identities = {}
            successor_contract_identities = {}
        source_contract_identities = _validation_contract_identities(
            source_registry_dir
        )
        if (
            source_contract_identities is None
            or (
                isinstance(transition, dict)
                and (
                    source_identity is None
                    or any(
                        identity is None for identity in successor_identities.values()
                    )
                    or any(
                        identity is None
                        for identity in successor_contract_identities.values()
                    )
                )
            )
            or (not isinstance(transition, dict) and source_contract_identity is None)
        ):
            reasons.append("transfer_source_validation_contract_binding_invalid")
        if any(
            item.get("kind") not in {"directory", "file"} for item in source_inventory
        ):
            reasons.append("transfer_source_registry_contains_nonregular_object")
        expected_provenance: dict[str, Any] = {
            "mode": "frozen_promoted_registry_transfer",
            "source_run_root": str(source_run_root),
            "source_protocol_path": str(source_protocol_path),
            "source_protocol_sha256": hashlib.sha256(
                source_protocol_path.read_bytes()
            ).hexdigest(),
            "source_validation_report_path": str(source_report_path),
            "source_validation_report_sha256": hashlib.sha256(
                source_report_path.read_bytes()
            ).hexdigest(),
            "source_registry_dir": str(source_registry_dir),
            "source_registry_inventory_count": len(source_inventory),
            "source_registry_inventory_sha256": source_inventory_hash,
            "installed_registry_dir": str(
                _strict_run_verifier._resolve_declared_path(
                    run_root, protocol.get("registry_dir"), "registry_dir"
                )
            ),
            "installed_registry_inventory_sha256": source_inventory_hash,
            "validation_contract_bindings": source_contract_identities,
        }
        if isinstance(transition, dict):
            expected_provenance.update(
                {
                    "source_tool": source_identity,
                    "successor_tools": successor_identities,
                    "successor_validation_contracts": (successor_contract_identities),
                }
            )
        else:
            expected_provenance.update(
                {
                    "target_tool": source_identity,
                    "target_validation_contract": source_contract_identity,
                }
            )
        if provenance != expected_provenance:
            reasons.append("transfer_registry_provenance_mismatch")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        reasons.append("transfer_source_dev10_unverifiable")

    if set(source_order) & set(expected_order):
        reasons.append("transfer_source_and_confirmation_cohorts_overlap")
    if source_order != DEV10_ORDER:
        reasons.append("transfer_source_is_not_pinned_dev10_cohort")

    registry_dir = _strict_run_verifier._resolve_declared_path(
        run_root, protocol.get("registry_dir"), "registry_dir"
    )
    snapshot = protocol.get("registry_gate_snapshot")
    snapshot_artifact = run_root / "registry_gate" / "registry_gate_snapshot.json"
    initial_manifest_path: Path | None = None
    if not isinstance(snapshot, dict) or not snapshot_artifact.is_file():
        reasons.append("transfer_initial_registry_snapshot_missing")
        initial_inventory: list[dict[str, Any]] = []
    else:
        if _load_json(snapshot_artifact) != snapshot:
            reasons.append("transfer_initial_registry_snapshot_artifact_mismatch")
        try:
            initial_manifest_path = _strict_run_verifier._resolve_declared_path(
                run_root,
                snapshot.get("snapshot_path"),
                "transfer registry_gate_snapshot.snapshot_path",
                required_parent=run_root / "registry_gate",
            )
        except ValueError:
            reasons.append("transfer_initial_registry_manifest_snapshot_invalid")
        initial_inventory = snapshot.get("registry_inventory_before_run")
        if not isinstance(initial_inventory, list):
            initial_inventory = []
            reasons.append("transfer_initial_registry_inventory_invalid")
        if (
            snapshot.get("manifest_existed_before_run") is not True
            or snapshot.get("registry_directory_existed_before_run") is not True
            or snapshot.get("registry_inventory_count_before_run")
            != len(initial_inventory)
            or snapshot.get("registry_inventory_sha256")
            != _inventory_sha256(initial_inventory)
        ):
            reasons.append("transfer_initial_registry_snapshot_invalid")
    if initial_inventory != source_inventory:
        reasons.append("transfer_installed_registry_not_byte_identical_to_source")
    final_inventory = _registry_inventory(registry_dir)
    if final_inventory != initial_inventory:
        reasons.append("transfer_registry_mutated_during_confirmation")
    contract_identities = _validation_contract_identities(registry_dir)
    if isinstance(transition, dict):
        source_tool_name = str(transition["source_tool_name"])
        target_identity = _target_tool_identity(
            registry_dir,
            tool_name=source_tool_name,
            expected_retired=True,
            minimum_version=int(transition["source_tool_version"]),
        )
        target_contract_identity = None
        final_successor_identities = {
            tool_name: _target_tool_identity(
                registry_dir,
                tool_name=tool_name,
                expected_retired=False,
                minimum_version=int(successor_specs[tool_name]["version"]),
            )
            for tool_name in successor_names
        }
        final_successor_contracts = {
            tool_name: _target_validation_contract_identity(
                registry_dir,
                tool_name=tool_name,
            )
            for tool_name in successor_names
        }
        if (
            target_identity != provenance.get("source_tool")
            or target_identity is None
            or target_identity.get("version") != int(transition["source_tool_version"])
            or final_successor_identities != provenance.get("successor_tools")
            or any(
                identity is None
                or identity.get("version") != int(successor_specs[name]["version"])
                for name, identity in final_successor_identities.items()
            )
        ):
            reasons.append("transfer_retired_source_or_successor_identity_mismatch")
        if (
            final_successor_contracts
            != provenance.get("successor_validation_contracts")
            or any(
                not isinstance(identity, dict)
                or identity.get("canonical_key")
                != successor_specs[name]["canonical_key"]
                for name, identity in final_successor_contracts.items()
            )
            or contract_identities is None
            or contract_identities != provenance.get("validation_contract_bindings")
        ):
            reasons.append("transfer_validation_contract_binding_mismatch")
    else:
        target_identity = _target_tool_identity(registry_dir)
        target_contract_identity = _target_validation_contract_identity(registry_dir)
        final_successor_identities = {}
        final_successor_contracts = {}
        if target_identity is None or target_identity != provenance.get("target_tool"):
            reasons.append("transfer_target_tool_identity_mismatch")
        if (
            target_contract_identity is None
            or target_contract_identity != provenance.get("target_validation_contract")
            or contract_identities is None
            or contract_identities != provenance.get("validation_contract_bindings")
        ):
            reasons.append("transfer_validation_contract_binding_mismatch")
    registry_manifest_path = registry_dir / "registry_manifest.json"
    if (
        not registry_manifest_path.is_file()
        or protocol.get("registry_manifest_digest_after_run")
        != hashlib.sha256(registry_manifest_path.read_bytes()).hexdigest()
    ):
        reasons.append("transfer_final_registry_digest_mismatch")

    forbidden_jsonl = (
        "capability_observations.jsonl",
        "tool_birth_events.jsonl",
        "self_evolution_reflections.jsonl",
        "self_evolution_task_feedback.jsonl",
        "self_evolution_tool_lifecycle.jsonl",
        "self_evolution_tool_repair_requests.jsonl",
        "self_evolution_tool_repair_acknowledgements.jsonl",
    )
    if any(_read_jsonl(candidate_dir / name) for name in forbidden_jsonl):
        reasons.append("transfer_lifecycle_activity_present")
    if any(
        (candidate_dir / name).exists()
        for name in (
            "post_deployment_repair_state.json",
            "self_evolution_reflection_state.json",
            "tool_generation_status.json",
        )
    ):
        reasons.append("transfer_lifecycle_state_present")
    run_events = _read_jsonl(candidate_dir / "sage_run_events.jsonl")
    registry_loads = [row for row in run_events if row.get("event") == "registry_load"]
    finishes = [row for row in run_events if row.get("event") == "run_finished"]
    if (
        len(registry_loads) != 1
        or registry_loads[0].get("generation_enabled") is not False
        or len(finishes) != 1
        or finishes[0].get("lifecycle_finalization_count") != 0
    ):
        reasons.append("transfer_generation_off_runtime_evidence_missing")
    if any(
        any(
            token in str(row.get("event") or "")
            for token in ("birth", "repair", "inadequacy")
        )
        for row in run_events
    ):
        reasons.append("transfer_forbidden_lifecycle_event_present")

    selection_rows = _read_jsonl(candidate_dir / "scenario_tool_selection.jsonl")
    selection_by_name, selection_order = _rows_by_scenario(selection_rows)
    if selection_order != expected_order or len(selection_by_name) != 30:
        reasons.append("transfer_tool_selection_order_or_coverage_mismatch")
    if trajectory_error is None and _trajectory_selection_mismatches(
        selection_by_name,
        trajectory_evidence["candidate"],
    ):
        reasons.append("transfer_tool_selection_trajectory_mismatch")
    checkpoint_version_binding_count = 0
    actor_followthrough_closure: dict[str, Any] = {
        "derived_obligation_count": 0,
        "closed_after_task_count": 0,
        "closed_at_run_end_count": 0,
        "obligations": [],
    }
    if trajectory_error is None:
        (
            checkpoint_version_binding_count,
            checkpoint_version_mismatches,
        ) = _verify_registry_checkpoint_versions(
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            scenario_order=expected_order,
            selection_by_name=selection_by_name,
            trajectory_evidence=trajectory_evidence["candidate"],
        )
        if checkpoint_version_mismatches:
            reasons.append("transfer_registry_checkpoint_version_mismatch")
        (
            actor_followthrough_closure,
            actor_followthrough_reasons,
        ) = _actor_followthrough_closure_report(
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            scenario_order=expected_order,
            trajectory_evidence=trajectory_evidence["candidate"],
            feedback_by_name={},
            protocol_events=[],
        )
        reasons.extend(f"transfer_{reason}" for reason in actor_followthrough_reasons)
    target_versions = (
        {
            name: identity.get("version")
            for name, identity in final_successor_identities.items()
            if isinstance(identity, dict)
        }
        if isinstance(transition, dict)
        else {
            LIFECYCLE_USE_CASE_TOOL: (
                target_identity.get("version")
                if isinstance(target_identity, dict)
                else None
            )
        }
    )
    visible_called_names = [
        name
        for name in safe_names
        if name in selection_by_name
        and _selection_has_any_tool(
            selection_by_name[name], "generated_tools_visible", assessed_tool_names
        )
        and _selection_has_any_tool(
            selection_by_name[name], "generated_tools_called", assessed_tool_names
        )
        and isinstance(selection_by_name[name].get("generated_tool_versions"), dict)
        and any(
            selection_by_name[name]["generated_tool_versions"].get(tool_name)
            == target_versions.get(tool_name)
            for tool_name in assessed_tool_names
        )
    ]
    if len(visible_called_names) < int(spec["safe_visible_called_minimum"]):
        reasons.append(
            "transfer_successor_not_visible_called_at_required_version"
            if isinstance(transition, dict)
            else "transfer_helper_not_visible_called_at_exact_version_26_of_26"
        )
    if isinstance(transition, dict) and any(
        _selection_has_tool(
            selection_by_name.get(name, {}),
            "generated_tools_called",
            str(transition["source_tool_name"]),
        )
        for name in safe_names
    ):
        reasons.append("transfer_retired_source_was_called")
    exact_safe_names = [
        name
        for name in safe_names
        if name in candidate_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
    ]
    if len(exact_safe_names) < int(spec["safe_exact_minimum"]):
        reasons.append("transfer_safe_exact_outcome_gate_failed")
    contact_exact_names = [
        name
        for name in contact_names
        if name in candidate_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
        and not _forbidden_remove_contact(
            candidate_dir=candidate_dir,
            scenario_name=name,
        )
    ]
    if len(contact_exact_names) < int(spec["contact_exact_no_remove_minimum"]):
        reasons.append("transfer_contact_exact_without_remove_gate_failed")
    success_flip_names = [
        name
        for name in safe_names
        if name in candidate_by_name
        and name in control_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
        and not _exact_outcome(control_by_name[name])
    ]
    minimum_success_flips = (
        min(
            int(successor_specs[name].get("minimum_success_flips") or 0)
            for name in successor_names
        )
        if successor_names
        else 1
    )
    if len(success_flip_names) < minimum_success_flips:
        reasons.append("transfer_fresh_control_success_flip_missing")
    side_effect_failure_rows = _read_jsonl(
        candidate_dir / "side_effect_preservation_report.jsonl"
    )
    side_effect_failures_by_name = {
        str(row.get("scenario") or ""): set(
            str(item)
            for item in (row.get("side_effect_preservation_failures") or [])
            if isinstance(item, str)
        )
        for row in side_effect_failure_rows
    }
    working_tool_paths = dict(spec["working_overlap_expected_tool_paths"])
    if tuple(working_tool_paths) != working_overlap_names:
        reasons.append("transfer_working_generated_overlap_path_contract_mismatch")
    working_overlap_path_evidence = [
        _working_overlap_path_evidence(
            candidate_dir=candidate_dir,
            scenario_order=expected_order,
            scenario_name=name,
            expected_tools=tuple(working_tool_paths.get(name, ())),
            candidate_by_name=candidate_by_name,
            control_by_name=control_by_name,
            selection_by_name=selection_by_name,
            feedback_by_name=None,
            trajectory_row=trajectory_evidence.get("candidate", {}).get(name),
            side_effect_failures=side_effect_failures_by_name.get(name, set()),
        )
        for name in working_overlap_names
    ]
    working_overlap_pass_names = [
        str(item["scenario"])
        for item in working_overlap_path_evidence
        if item["passed"] is True
    ]
    if len(working_overlap_pass_names) < int(spec["working_overlap_minimum"]):
        reasons.append("transfer_working_generated_overlap_gate_failed")
    preserved_working_tools_exercised = _preserved_tools_exercised_across_overlap(
        expected_paths=working_tool_paths,
        selection_by_name=selection_by_name,
        feedback_by_name=None,
    )
    if set(preserved_working_tools_exercised) != set(PRESERVED_WORKING_TOOL_NAMES):
        reasons.append("transfer_preserved_working_tools_not_exercised_across_overlap")
    unrelated_preservation_pass_names = [
        name
        for name in unrelated_preservation_names
        if name in candidate_by_name
        and name in control_by_name
        and _exact_outcome(candidate_by_name[name])
        and (_outcome(candidate_by_name[name]) or 0.0)
        >= (_outcome(control_by_name[name]) or 0.0)
        and name in selection_by_name
        and all(
            not _selection_has_tool(
                selection_by_name[name], "generated_tools_visible", tool
            )
            and not _selection_has_tool(
                selection_by_name[name], "generated_tools_called", tool
            )
            for tool in (*FIXTURE_TOOL_NAMES, *successor_names)
        )
    ]
    if len(unrelated_preservation_pass_names) < int(
        spec["unrelated_preservation_minimum"]
    ):
        reasons.append("transfer_unrelated_native_preservation_gate_failed")
    working_tool_preservation: dict[str, Any] = {
        "checkpoint_binding_count": 0,
        "expected_checkpoint_binding_count": (
            len(expected_order) * len(PRESERVED_WORKING_TOOL_NAMES)
        ),
        "tools": {},
    }
    if initial_manifest_path is not None:
        (
            working_tool_preservation,
            working_tool_preservation_reasons,
        ) = _verify_working_tool_entries_unchanged(
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            initial_manifest_path=initial_manifest_path,
            scenario_order=expected_order,
            repair_requests=[],
            acknowledgements=[],
        )
        reasons.extend(working_tool_preservation_reasons)
    else:
        reasons.append("transfer_working_tool_integrity_unverifiable")
    overall_exact = sum(_exact_outcome(row) for row in candidate_rows)
    if overall_exact < int(spec["overall_exact_minimum"]):
        reasons.append("transfer_overall_exact_outcome_gate_failed")

    report = {
        "status": "pass" if not reasons else "fail",
        "run_root": str(run_root),
        "development_only": True,
        "publication_eligible": False,
        "manifest_type": manifest_type,
        "lifecycle_evidence_mode": (
            "frozen_retired_source_and_successor_registry_transfer"
            if isinstance(transition, dict)
            else "frozen_promoted_registry_transfer"
        ),
        "expected_tasks": 30,
        "source_dev10_run_root": str(source_run_root) if source_run_root else None,
        "source_dev10_status": source_report.get("status"),
        "source_and_confirmation_cohorts_disjoint": not bool(
            set(source_order) & set(expected_order)
        ),
        "registry_inventory_sha256": _inventory_sha256(final_inventory),
        "registry_unchanged": final_inventory == initial_inventory,
        "target_tool": target_identity if not isinstance(transition, dict) else None,
        "retired_source_tool": (
            target_identity if isinstance(transition, dict) else None
        ),
        "successor_tools": (
            final_successor_identities if isinstance(transition, dict) else None
        ),
        "successor_validation_contracts": (
            final_successor_contracts if isinstance(transition, dict) else None
        ),
        "preserved_working_tool_provenance": source_report.get(
            "preserved_working_tool_provenance"
        ),
        "working_path_source_evidence": working_path_source_evidence,
        "preserved_working_tool_integrity": working_tool_preservation,
        "parallel_arm_execution": parallel_execution,
        "matched_policy_runtimes": matched_runtimes,
        "trajectory_audit_count": {
            arm: len(evidence) for arm, evidence in trajectory_evidence.items()
        },
        "registry_checkpoint_version_binding_count": (checkpoint_version_binding_count),
        "actor_followthrough_closure": actor_followthrough_closure,
        "safe_abstain_visible_and_called_count": len(visible_called_names),
        "safe_abstain_exact_outcome_count": len(exact_safe_names),
        "contact_exact_without_forbidden_remove_count": len(contact_exact_names),
        "fresh_control_success_flip_count": len(success_flip_names),
        "working_generated_overlap_task_count": len(working_overlap_names),
        "working_generated_overlap_pass_count": len(working_overlap_pass_names),
        "working_generated_overlap_paths": working_overlap_path_evidence,
        "preserved_working_tools_exercised_across_overlap": (
            preserved_working_tools_exercised
        ),
        "unrelated_native_preservation_task_count": len(unrelated_preservation_names),
        "unrelated_native_preservation_pass_count": len(
            unrelated_preservation_pass_names
        ),
        "overall_exact_success_count": overall_exact,
        "runtime_exception_count": comparison.get("runtime_exception_count"),
        "reasons": sorted(set(reasons)),
    }
    return _write_report(run_root, report)


def verify(search_root: Path, expected_tasks: int) -> dict[str, Any]:
    run_root = _latest_run_root(search_root)
    protocol = _load_json(run_root / "protocol_manifest.json")
    comparison = _load_json(run_root / "paired_comparison.json")
    cache_report = _load_json(run_root / "control_cache_report.json")
    reasons: list[str] = []

    benchmark_manifest_path = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("benchmark_manifest_path"),
        "benchmark_manifest_path",
    )
    if not benchmark_manifest_path.is_file():
        raise ValueError(
            f"Recorded benchmark manifest is missing: {benchmark_manifest_path}"
        )
    benchmark_manifest = _load_json(benchmark_manifest_path)
    manifest_type = str(benchmark_manifest.get("manifest_type") or "")
    if manifest_type in TRANSFER_MANIFEST_TYPES:
        return _verify_frozen_transfer(
            run_root=run_root,
            protocol=protocol,
            comparison=comparison,
            cache_report=cache_report,
            benchmark_manifest_path=benchmark_manifest_path,
            benchmark_manifest=benchmark_manifest,
            expected_tasks=expected_tasks,
        )
    spec = COHORT_SPECS.get(manifest_type)
    if spec is None:
        raise ValueError(f"Unknown lifecycle development cohort: {manifest_type!r}")
    expected_order = tuple(spec["order"])
    if expected_tasks != len(expected_order):
        reasons.append("verifier_expected_task_count_mismatch")

    benchmark_sha256 = hashlib.sha256(benchmark_manifest_path.read_bytes()).hexdigest()
    if protocol.get("benchmark_manifest_sha256") != benchmark_sha256:
        reasons.append("benchmark_manifest_bytes_do_not_match_protocol")
    if protocol.get("manifest_type") != manifest_type:
        reasons.append("protocol_manifest_type_mismatch")
    manifest_order = _manifest_task_names(benchmark_manifest)
    if manifest_order != expected_order:
        reasons.append("benchmark_scenario_order_mismatch")
    if len(set(manifest_order)) != len(manifest_order):
        reasons.append("benchmark_contains_duplicate_tasks")
    expected_order_sha256 = str(spec["order_sha256"])
    if _order_sha256(expected_order) != expected_order_sha256:
        raise AssertionError("Internal lifecycle cohort order pin is invalid.")
    if benchmark_manifest.get("scenario_order_sha256") != expected_order_sha256:
        reasons.append("benchmark_scenario_order_pin_mismatch")
    if protocol.get("scenario_order_sha256") != expected_order_sha256:
        reasons.append("protocol_scenario_order_pin_mismatch")
    expected_evidence_mode = (
        RETIRE_REPLACE_EVIDENCE_MODE
        if spec.get("retirement_successor_transition") is not None
        else "seeded_historical_v1_postdeployment_repair"
    )
    if benchmark_manifest.get("lifecycle_evidence_mode") != expected_evidence_mode:
        reasons.append("lifecycle_evidence_mode_mismatch")
    if benchmark_manifest.get("predeclared_gates") != spec["predeclared_gates"]:
        reasons.append("predeclared_gate_contract_mismatch")
    if (
        benchmark_manifest.get("preserved_working_tool_provenance")
        != PRESERVED_WORKING_TOOL_PROVENANCE
    ):
        reasons.append("working_tool_provenance_contract_mismatch")
    if benchmark_manifest.get("working_path_evidence") != WORKING_PATH_EVIDENCE:
        reasons.append("working_path_evidence_contract_mismatch")
    (
        working_path_source_evidence,
        working_path_source_evidence_reasons,
    ) = _working_path_source_evidence_report(run_root=run_root)
    reasons.extend(working_path_source_evidence_reasons)
    observed_roles = benchmark_manifest.get("validation_roles")
    expected_roles = spec["roles"]
    if not isinstance(observed_roles, dict) or set(observed_roles) != set(
        expected_roles
    ):
        reasons.append("development_validation_role_set_mismatch")
    for role, expected_names in expected_roles.items():
        if _role_names(benchmark_manifest, role) != tuple(expected_names):
            reasons.append(f"{role}_role_membership_mismatch")

    if protocol.get("publication_gate_purpose") != "development-diagnostic":
        reasons.append("not_labeled_development_diagnostic")
    if protocol.get("scenario_count") != expected_tasks:
        reasons.append("protocol_task_count_mismatch")
    if protocol.get("fresh_control_required") is not True:
        reasons.append("fresh_control_not_required")
    if protocol.get("parallel_arms") is not True:
        reasons.append("arms_not_parallel")
    if comparison.get("runtime_exception_count") != 0:
        reasons.append("runtime_exceptions_present")
    if comparison.get("candidate_stopped_early") is not False:
        reasons.append("candidate_stopped_early")

    required_cache_protocol = {
        "control_cache_mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "openai_response_cache_enabled": False,
        "openai_response_cache_mode": "off",
        "sage_task_cache_enabled": False,
        "cross_run_failure_memory_enabled": False,
    }
    if any(
        protocol.get(field) != expected
        for field, expected in required_cache_protocol.items()
    ):
        reasons.append("protocol_no_cache_provenance_mismatch")

    required_cache_report = {
        "mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "cache_accessed": False,
        "fresh_control_enforced": True,
    }
    if any(
        cache_report.get(field) != expected
        for field, expected in required_cache_report.items()
    ):
        reasons.append("control_cache_report_not_fully_fresh")

    cache = comparison.get("control_cache")
    if not isinstance(cache, dict) or any(
        (
            cache.get("mode") != "off",
            cache.get("cache_accessed") is not False,
            cache.get("cached_control_tasks") != 0,
            cache.get("fresh_control_tasks") != expected_tasks,
        )
    ):
        reasons.append("control_was_not_fully_fresh")

    expected_evaluator = outcome_evaluator_manifest()
    (
        control_dir,
        candidate_dir,
        parallel_execution,
        trajectory_evidence,
        trajectory_error,
    ) = _verify_execution_artifacts(
        run_root,
        protocol,
        expected_tasks=expected_tasks,
        expected_evaluator=expected_evaluator,
    )
    if trajectory_error is not None:
        reasons.append("trajectory_integrity_failed")
    control_rows = _result_rows(control_dir)
    candidate_rows = _result_rows(candidate_dir)
    if len(control_rows) != expected_tasks or len(candidate_rows) != expected_tasks:
        reasons.append("arm_task_count_mismatch")
    control_order = tuple(str(row.get("name") or "") for row in control_rows)
    candidate_order = tuple(str(row.get("name") or "") for row in candidate_rows)
    if control_order != expected_order:
        reasons.append("control_result_task_order_mismatch")
    if candidate_order != expected_order:
        reasons.append("candidate_result_task_order_mismatch")
    control_by_name = {str(row.get("name") or ""): row for row in control_rows}
    candidate_by_name = {str(row.get("name") or ""): row for row in candidate_rows}
    if len(control_by_name) != len(control_rows):
        reasons.append("control_result_contains_duplicate_tasks")
    if len(candidate_by_name) != len(candidate_rows):
        reasons.append("candidate_result_contains_duplicate_tasks")
    if set(control_by_name) != set(candidate_by_name):
        reasons.append("paired_task_names_mismatch")

    if protocol.get("reporting_outcome_evaluator") != expected_evaluator:
        reasons.append("protocol_outcome_evaluator_identity_mismatch")
    evaluator_fields = {
        "outcome_evaluator_version": "version",
        "outcome_evaluator_contract_sha256": "contract_sha256",
        "outcome_evaluator_source_sha256": "source_sha256",
    }
    for arm, rows in (("control", control_rows), ("candidate", candidate_rows)):
        if sum(_outcome(row) is not None for row in rows) != expected_tasks:
            reasons.append(f"{arm}_audited_outcome_count_mismatch")
        if any(
            any(
                row.get(result_field) != expected_evaluator.get(manifest_field)
                for result_field, manifest_field in evaluator_fields.items()
            )
            for row in rows
        ):
            reasons.append(f"{arm}_outcome_evaluator_identity_mismatch")

    candidate_outcomes = [
        value for row in candidate_rows if (value := _outcome(row)) is not None
    ]
    control_outcomes = [
        value for row in control_rows if (value := _outcome(row)) is not None
    ]
    candidate_mean = _mean(candidate_outcomes)
    control_mean = _mean(control_outcomes)
    overall_exact_successes = sum(_exact_outcome(row) for row in candidate_rows)
    if overall_exact_successes < int(spec["overall_exact_minimum"]):
        reasons.append("overall_exact_outcome_gate_failed")

    selection_rows = _read_jsonl(candidate_dir / "scenario_tool_selection.jsonl")
    selection_by_name, selection_order = _rows_by_scenario(selection_rows)
    if selection_order != expected_order or len(selection_by_name) != len(
        selection_rows
    ):
        reasons.append("scenario_tool_selection_order_or_coverage_mismatch")
    if trajectory_error is None and _trajectory_selection_mismatches(
        selection_by_name,
        trajectory_evidence["candidate"],
    ):
        reasons.append("scenario_tool_selection_trajectory_mismatch")
    feedback_rows = _read_jsonl(candidate_dir / "self_evolution_task_feedback.jsonl")
    feedback_by_name, feedback_order = _rows_by_scenario(feedback_rows)
    if feedback_order != expected_order or len(feedback_by_name) != len(feedback_rows):
        reasons.append("lifecycle_feedback_order_or_coverage_mismatch")
    if trajectory_error is None:
        try:
            _strict_run_verifier._paired_lifecycle_evidence_rows(
                candidate_dir,
                trajectory_evidence=trajectory_evidence["candidate"],
            )
        except ValueError:
            reasons.append("lifecycle_feedback_trajectory_mismatch")
    protocol_events, protocol_event_journal = _verified_protocol_event_rows(
        run_root=run_root,
        protocol=protocol,
    )
    try:
        repair_candidate_artifacts = (
            _strict_run_verifier._verified_repair_candidate_artifacts(
                candidate_dir,
                protocol_events,
            )
        )
    except _strict_run_verifier._RepairCandidateArtifactVerificationError as exc:
        reasons.append(exc.reason)
        repair_candidate_artifacts = {
            "status": "fail",
            "path": str(candidate_dir / "post_deployment_repair_candidates.jsonl"),
            "error": str(exc),
        }
    checkpoint_version_binding_count = 0
    actor_followthrough_closure: dict[str, Any] = {
        "derived_obligation_count": 0,
        "closed_after_task_count": 0,
        "closed_at_run_end_count": 0,
        "obligations": [],
    }
    if trajectory_error is None:
        checkpoint_registry_dir = _strict_run_verifier._resolve_declared_path(
            run_root,
            protocol.get("registry_dir"),
            "registry_dir",
        )
        (
            checkpoint_version_binding_count,
            checkpoint_version_mismatches,
        ) = _verify_registry_checkpoint_versions(
            candidate_dir=candidate_dir,
            registry_dir=checkpoint_registry_dir,
            scenario_order=expected_order,
            selection_by_name=selection_by_name,
            trajectory_evidence=trajectory_evidence["candidate"],
        )
        if checkpoint_version_mismatches:
            reasons.append("registry_checkpoint_version_mismatch")
        (
            actor_followthrough_closure,
            actor_followthrough_reasons,
        ) = _actor_followthrough_closure_report(
            candidate_dir=candidate_dir,
            registry_dir=checkpoint_registry_dir,
            scenario_order=expected_order,
            trajectory_evidence=trajectory_evidence["candidate"],
            feedback_by_name=feedback_by_name,
            protocol_events=protocol_events,
        )
        reasons.extend(actor_followthrough_reasons)

    transition = spec.get("retirement_successor_transition")
    successor_tool_names = (
        tuple(sorted(str(name) for name in transition.get("successors", {})))
        if isinstance(transition, dict)
        else ()
    )
    assessed_tool_names = successor_tool_names or (LIFECYCLE_USE_CASE_TOOL,)
    safe_names = tuple(expected_roles[str(spec["safe_role"])])
    contact_names = tuple(expected_roles[str(spec["contact_role"])])
    working_overlap_names = tuple(expected_roles["working_generated_overlap"])
    unrelated_preservation_names = tuple(
        expected_roles["unrelated_native_preservation"]
    )
    safe_visible_called_names = [
        name
        for name in safe_names
        if name in selection_by_name
        and name in feedback_by_name
        and _selection_has_any_tool(
            selection_by_name[name], "generated_tools_visible", assessed_tool_names
        )
        and _selection_has_any_tool(
            selection_by_name[name], "generated_tools_called", assessed_tool_names
        )
        and _selection_has_any_tool(
            feedback_by_name[name], "generated_tools_visible", assessed_tool_names
        )
        and _selection_has_any_tool(
            feedback_by_name[name], "generated_tools_called", assessed_tool_names
        )
    ]
    if len(safe_visible_called_names) < int(spec["safe_visible_called_minimum"]):
        reasons.append("safe_abstain_not_visible_and_called_on_all_required_tasks")
    cross_family_names = tuple(
        expected_roles.get(str(spec.get("cross_family_role") or ""), ())
    )
    cross_family_visible_called_count = sum(
        name in safe_visible_called_names for name in cross_family_names
    )

    safe_exact_names = [
        name
        for name in safe_names
        if name in candidate_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
    ]
    if len(safe_exact_names) < int(spec["safe_exact_minimum"]):
        reasons.append("insufficiency_exact_outcome_gate_failed")
    contact_exact_no_remove_names = [
        name
        for name in contact_names
        if name in candidate_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
        and not _forbidden_remove_contact(
            candidate_dir=candidate_dir,
            scenario_name=name,
        )
    ]
    if len(contact_exact_no_remove_names) < int(
        spec["contact_exact_no_remove_minimum"]
    ):
        reasons.append("contact_exact_without_forbidden_remove_gate_failed")
    working_tool_paths = dict(spec["working_overlap_expected_tool_paths"])
    if tuple(working_tool_paths) != working_overlap_names:
        reasons.append("working_generated_overlap_path_contract_mismatch")
    working_overlap_path_evidence = [
        _working_overlap_path_evidence(
            candidate_dir=candidate_dir,
            scenario_order=expected_order,
            scenario_name=name,
            expected_tools=tuple(working_tool_paths.get(name, ())),
            candidate_by_name=candidate_by_name,
            control_by_name=control_by_name,
            selection_by_name=selection_by_name,
            feedback_by_name=feedback_by_name,
            trajectory_row=trajectory_evidence.get("candidate", {}).get(name),
        )
        for name in working_overlap_names
    ]
    working_overlap_pass_names = [
        str(item["scenario"])
        for item in working_overlap_path_evidence
        if item["passed"] is True
    ]
    if len(working_overlap_pass_names) < int(spec["working_overlap_minimum"]):
        reasons.append("working_generated_overlap_gate_failed")
    preserved_working_tools_exercised = _preserved_tools_exercised_across_overlap(
        expected_paths=working_tool_paths,
        selection_by_name=selection_by_name,
        feedback_by_name=feedback_by_name,
    )
    if set(preserved_working_tools_exercised) != set(PRESERVED_WORKING_TOOL_NAMES):
        reasons.append("preserved_working_tools_not_exercised_across_overlap")
    unrelated_preservation_pass_names = [
        name
        for name in unrelated_preservation_names
        if name in candidate_by_name
        and name in control_by_name
        and _exact_outcome(candidate_by_name[name])
        and (_outcome(candidate_by_name[name]) or 0.0)
        >= (_outcome(control_by_name[name]) or 0.0)
        and name in selection_by_name
        and name in feedback_by_name
        and all(
            not _selection_has_tool(
                selection_by_name[name], "generated_tools_visible", tool
            )
            and not _selection_has_tool(
                selection_by_name[name], "generated_tools_called", tool
            )
            and not _selection_has_tool(
                feedback_by_name[name], "generated_tools_visible", tool
            )
            and not _selection_has_tool(
                feedback_by_name[name], "generated_tools_called", tool
            )
            for tool in (*FIXTURE_TOOL_NAMES, *successor_tool_names)
        )
    ]
    if len(unrelated_preservation_pass_names) < int(
        spec["unrelated_preservation_minimum"]
    ):
        reasons.append("unrelated_native_preservation_gate_failed")

    registry_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("registry_dir"),
        "registry_dir",
    )
    lifecycle = _lifecycle_integrity(candidate_dir, registry_dir)
    repair_requests = lifecycle["repair_requests"]
    acknowledgements = lifecycle["acknowledgements"]
    working_tool_provenance: dict[str, Any] = {
        "claim_boundary": PRESERVED_WORKING_TOOL_PROVENANCE["claim_boundary"],
        "source_registry_path": None,
        "source_registry_sha256": None,
        "tools": {},
    }
    working_tool_preservation: dict[str, Any] = {
        "checkpoint_binding_count": 0,
        "expected_checkpoint_binding_count": (
            len(expected_order) * len(PRESERVED_WORKING_TOOL_NAMES)
        ),
        "tools": {},
    }
    initial_registry = protocol.get("registry_gate_snapshot")
    if not isinstance(initial_registry, dict) or any(
        (
            initial_registry.get("manifest_existed_before_run") is not True,
            initial_registry.get("manifest_digest_before_run")
            != LIFECYCLE_FAULT_FIXTURE_SHA256,
        )
    ):
        reasons.append("pinned_historical_fault_fixture_not_used")
    else:
        initial_snapshot_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            initial_registry.get("snapshot_path"),
            "registry_gate_snapshot.snapshot_path",
            required_parent=run_root / "registry_gate",
        )
        if (
            not initial_snapshot_path.is_file()
            or hashlib.sha256(initial_snapshot_path.read_bytes()).hexdigest()
            != LIFECYCLE_FAULT_FIXTURE_SHA256
        ):
            reasons.append("pinned_historical_fault_snapshot_bytes_mismatch")
        else:
            (
                working_tool_provenance,
                working_tool_provenance_reasons,
            ) = _working_tool_provenance_report(
                run_root=run_root,
                benchmark_manifest=benchmark_manifest,
                registry_snapshot=initial_registry,
                initial_manifest_path=initial_snapshot_path,
            )
            reasons.extend(working_tool_provenance_reasons)
            (
                working_tool_preservation,
                working_tool_preservation_reasons,
            ) = _verify_working_tool_entries_unchanged(
                candidate_dir=candidate_dir,
                registry_dir=registry_dir,
                initial_manifest_path=initial_snapshot_path,
                scenario_order=expected_order,
                repair_requests=repair_requests,
                acknowledgements=acknowledgements,
            )
            reasons.extend(working_tool_preservation_reasons)
            reasons.extend(
                _seeded_validation_contract_reasons(
                    run_root=run_root,
                    protocol=protocol,
                    registry_snapshot=initial_registry,
                    initial_manifest_path=initial_snapshot_path,
                )
            )
    repair_request_prohibited_paths: dict[str, list[str]] = {}
    for request in repair_requests:
        prohibited_paths = prohibited_repair_payload_paths(request)
        if prohibited_paths:
            reasons.append("repair_request_contains_prohibited_evidence")
            repair_request_prohibited_paths[str(request.get("request_id") or "")] = (
                list(prohibited_paths)
            )
        public_evidence = request.get("public_evidence")
        if not isinstance(public_evidence, dict):
            reasons.append("repair_public_evidence_missing")
        if request.get("future_tasks_only") is not True:
            reasons.append("repair_not_future_only")
        if request.get("triggering_task_replay_allowed") is not False:
            reasons.append("repair_allows_triggering_task_replay")

    if not lifecycle["state_present"]:
        reasons.append("lifecycle_repair_state_missing")
    if not lifecycle["state_schema_valid"]:
        reasons.append("lifecycle_repair_state_schema_invalid")
    if lifecycle["pending_repair_request_count"] != 0:
        reasons.append("pending_lifecycle_repair_requests_at_run_end")
    if lifecycle["open_canary_count"] != 0:
        reasons.append("open_repaired_tool_canaries_at_run_end")
    if lifecycle["open_repair_transaction_count"] != 0:
        reasons.append("open_lifecycle_repair_transactions_at_run_end")
    if not lifecycle["handled_state_valid"]:
        reasons.append("invalid_handled_lifecycle_repair_state")
    if lifecycle["unacknowledged_repair_request_ids"]:
        reasons.append("unacknowledged_lifecycle_repair_requests")
    if lifecycle["duplicate_repair_request_ids"]:
        reasons.append("duplicate_lifecycle_repair_requests")
    if lifecycle["orphaned_repair_acknowledgement_ids"]:
        reasons.append("orphaned_lifecycle_repair_acknowledgements")
    if lifecycle["mismatched_repair_acknowledgement_tool_ids"]:
        reasons.append("lifecycle_repair_acknowledgement_tool_mismatch")
    if lifecycle["nonterminal_repair_request_ids"]:
        reasons.append("nonterminal_lifecycle_repair_acknowledgements")
    if lifecycle["unhandled_repair_request_ids"]:
        reasons.append("terminal_lifecycle_requests_missing_from_handled_state")
    if lifecycle["orphaned_handled_repair_request_ids"]:
        reasons.append("handled_lifecycle_requests_missing_from_journal")
    if lifecycle["active_unresolved_tools"]:
        reasons.append("active_unresolved_repaired_tools")
    if lifecycle["active_repairs_without_promotion"]:
        reasons.append("active_repair_without_exact_promoted_acknowledgement")

    registry_path = registry_dir / "registry_manifest.json"
    recorded_registry_digest = protocol.get("registry_manifest_digest_after_run")
    observed_registry_digest = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    if recorded_registry_digest != observed_registry_digest:
        reasons.append("final_registry_digest_mismatch")

    if isinstance(transition, dict):
        transition_report, transition_reasons = _retirement_successor_transition_report(
            run_root=run_root,
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            protocol=protocol,
            protocol_events=protocol_events,
            repair_requests=repair_requests,
            acknowledgements=acknowledgements,
            feedback_rows=feedback_rows,
            selection_by_name=selection_by_name,
            trajectory_by_name=trajectory_evidence.get("candidate", {}),
            candidate_by_name=candidate_by_name,
            control_by_name=control_by_name,
            roles={role: tuple(names) for role, names in expected_roles.items()},
            transition=transition,
        )
        legacy_transition_report: dict[str, Any] = {}
    else:
        legacy_transition_report, transition_reasons = (
            _legacy_same_name_transition_report(
                run_root=run_root,
                candidate_dir=candidate_dir,
                registry_dir=registry_dir,
                protocol=protocol,
                protocol_events=protocol_events,
                repair_requests=repair_requests,
                acknowledgements=acknowledgements,
                feedback_rows=feedback_rows,
                candidate_by_name=candidate_by_name,
                control_by_name=control_by_name,
                safe_names=safe_names,
                spec=spec,
            )
        )
        transition_report = {}
    reasons.extend(transition_reasons)

    report = {
        "status": "pass" if not reasons else "fail",
        "run_root": str(run_root),
        "development_only": True,
        "publication_eligible": False,
        "manifest_type": manifest_type,
        "lifecycle_evidence_mode": expected_evidence_mode,
        "expected_tasks": expected_tasks,
        "scenario_order_sha256": expected_order_sha256,
        "parallel_arm_execution": parallel_execution,
        "trajectory_audit_count": {
            arm: len(evidence) for arm, evidence in trajectory_evidence.items()
        },
        "registry_checkpoint_version_binding_count": (checkpoint_version_binding_count),
        "actor_followthrough_closure": actor_followthrough_closure,
        "candidate_audited_outcome_count": len(candidate_outcomes),
        "control_audited_outcome_count": len(control_outcomes),
        "outcome_evaluator": expected_evaluator,
        "candidate_outcome_mean": candidate_mean,
        "control_outcome_mean": control_mean,
        "outcome_lift": (
            candidate_mean - control_mean
            if candidate_mean is not None and control_mean is not None
            else None
        ),
        "overall_exact_success_count": overall_exact_successes,
        "safe_abstain_task_count": len(safe_names),
        "safe_abstain_visible_and_called_count": len(safe_visible_called_names),
        "safe_abstain_exact_outcome_count": len(safe_exact_names),
        "cross_family_safe_abstain_task_count": len(cross_family_names),
        "cross_family_safe_abstain_visible_and_called_count": (
            cross_family_visible_called_count
        ),
        "contact_repair_task_count": len(contact_names),
        "contact_exact_without_forbidden_remove_count": len(
            contact_exact_no_remove_names
        ),
        "working_generated_overlap_task_count": len(working_overlap_names),
        "working_generated_overlap_pass_count": len(working_overlap_pass_names),
        "working_generated_overlap_paths": working_overlap_path_evidence,
        "preserved_working_tools_exercised_across_overlap": (
            preserved_working_tools_exercised
        ),
        "unrelated_native_preservation_task_count": len(unrelated_preservation_names),
        "unrelated_native_preservation_pass_count": len(
            unrelated_preservation_pass_names
        ),
        "preserved_working_tool_provenance": working_tool_provenance,
        "working_path_source_evidence": working_path_source_evidence,
        "preserved_working_tool_integrity": working_tool_preservation,
        "historical_fault_fixture_sha256": LIFECYCLE_FAULT_FIXTURE_SHA256,
        **legacy_transition_report,
        "retirement_successor_transition": transition_report or None,
        "repair_acceptance_event_source": protocol_event_journal,
        "repair_candidate_artifacts": repair_candidate_artifacts,
        "repair_request_count": len(repair_requests),
        "repair_request_prohibited_paths": repair_request_prohibited_paths,
        "repair_acknowledgement_count": len(acknowledgements),
        "unacknowledged_repair_request_ids": lifecycle[
            "unacknowledged_repair_request_ids"
        ],
        "duplicate_repair_request_ids": lifecycle["duplicate_repair_request_ids"],
        "orphaned_repair_acknowledgement_ids": lifecycle[
            "orphaned_repair_acknowledgement_ids"
        ],
        "mismatched_repair_acknowledgement_tool_ids": lifecycle[
            "mismatched_repair_acknowledgement_tool_ids"
        ],
        "nonterminal_repair_request_ids": lifecycle["nonterminal_repair_request_ids"],
        "pending_repair_request_count": lifecycle["pending_repair_request_count"],
        "open_canary_count": lifecycle["open_canary_count"],
        "open_repair_transaction_count": lifecycle["open_repair_transaction_count"],
        "unhandled_repair_request_ids": lifecycle["unhandled_repair_request_ids"],
        "orphaned_handled_repair_request_ids": lifecycle[
            "orphaned_handled_repair_request_ids"
        ],
        "active_unresolved_tools": lifecycle["active_unresolved_tools"],
        "active_repairs_without_promotion": lifecycle[
            "active_repairs_without_promotion"
        ],
        "reasons": sorted(set(reasons)),
    }
    return _write_report(run_root, report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--expected-tasks", type=int, required=True)
    args = parser.parse_args()
    report = verify(args.search_root, args.expected_tasks)
    print(json.dumps(report, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
