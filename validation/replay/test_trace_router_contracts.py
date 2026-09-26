"""Integrity and tamper checks for the trace-acquisition replay boundary."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from validation.replay.compare import _diff  # noqa: E402
from validation.replay.snapshot import (  # noqa: E402
    _accepted_entry,
    _capture_exact_call,
    _exact_json_snapshot,
    _tool_spec,
)
from validation.replay.trace_router_contracts import (  # noqa: E402
    _normalization_contracts,
    _routing_contracts,
    _trace_contracts,
)


class TraceAcquisitionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = _trace_contracts(
            capture=_capture_exact_call,
            exact=_exact_json_snapshot,
        )

    @classmethod
    def value(cls, name: str) -> dict[str, object]:
        return cls.contracts[name]["value"]

    def test_separate_readers_observe_separate_database_snapshots(self) -> None:
        observed = self.value("changing_snapshots")

        self.assertEqual(observed["context_acquisition_count"], 2)
        self.assertEqual(observed["database_acquisition_count"], 2)
        self.assertEqual(observed["call"]["result"]["value"], [101.25, 202.5])

    def test_datetime_enrichment_performs_two_independent_acquisitions(self) -> None:
        observed = self.value("datetime_enrichment_acquisitions")

        self.assertEqual(observed["context_acquisition_count"], 2)
        self.assertEqual(observed["database_acquisition_count"], 2)
        self.assertEqual(
            observed["call"]["result"]["value"],
            {
                "current_timestamp": 200.0,
                "current_datetime_info": {
                    "year": 2026,
                    "month": 9,
                    "day": 26,
                    "hour": 12,
                    "minute": 34,
                    "second": 56,
                },
            },
        )

    def test_every_history_reader_uses_the_exact_database_keywords(self) -> None:
        expected = {
            "positional_arguments": [],
            "keyword_arguments": {
                "namespace": {
                    "python_type": "DatabaseNamespace",
                    "name": "SANDBOX",
                    "value": "SANDBOX",
                    "is_sandbox_singleton": True,
                },
                "get_all_history_snapshots": {
                    "python_type": "bool",
                    "value": True,
                },
            },
        }
        observed = self.value("database_call_contracts")

        self.assertEqual(len(observed), 6)
        for reader, contract in observed.items():
            with self.subTest(reader=reader):
                self.assertEqual(contract["context_acquisition_count"], 1)
                self.assertEqual(contract["database_acquisition_count"], 1)
                self.assertEqual(contract["database_calls"], [expected])

    def test_empty_wanted_names_do_not_acquire_context_or_database(self) -> None:
        observed = self.value("empty_wanted_names")

        self.assertEqual(
            observed["call"]["result"]["value"],
            {
                "payload": None,
                "records": None,
            },
        )
        self.assertEqual(observed["context_acquisition_count"], 0)
        self.assertEqual(observed["database_acquisition_count"], 0)
        self.assertEqual(observed["database_calls"], [])

    def test_to_dicts_failure_propagates_from_every_history_reader(self) -> None:
        observed = self.value("rows_failure_propagation")

        self.assertEqual(len(observed), 6)
        for reader, contract in observed.items():
            with self.subTest(reader=reader):
                self.assertEqual(
                    contract["call"],
                    {
                        "status": "raised",
                        "exception_type": "TraceRowsFailure",
                        "message": "sentinel sandbox.to_dicts failure",
                    },
                )

    def test_newest_match_short_circuits_before_older_list_conversion(self) -> None:
        observed = self.value("lazy_short_circuit")

        self.assertEqual(observed["call"]["status"], "returned")
        self.assertEqual(
            observed["call"]["result"]["value"],
            [{"person_id": "newest", "name": "Last in row"}],
        )
        self.assertEqual(observed["unreached_conversion_attempt_count"], 0)


class TraceAcquisitionTamperTests(unittest.TestCase):
    def setUp(self) -> None:
        contracts = _trace_contracts(
            capture=_capture_exact_call,
            exact=_exact_json_snapshot,
        )
        self.reference = {
            name: contracts[name]
            for name in (
                "changing_snapshots",
                "datetime_enrichment_acquisitions",
                "database_call_contracts",
                "empty_wanted_names",
                "rows_failure_propagation",
                "lazy_short_circuit",
            )
        }

    def test_detects_acquisition_count_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        tampered["changing_snapshots"]["value"]["database_acquisition_count"] = 1

        paths = {difference["path"] for difference in _diff(self.reference, tampered)}
        self.assertIn(
            "/changing_snapshots/value/database_acquisition_count",
            paths,
        )

    def test_detects_database_keyword_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        calls = tampered["database_call_contracts"]["value"]
        del calls["named_records"]["database_calls"][0]["keyword_arguments"][
            "get_all_history_snapshots"
        ]

        paths = {difference["path"] for difference in _diff(self.reference, tampered)}
        self.assertIn(
            "/database_call_contracts/value/named_records/database_calls/0/"
            "keyword_arguments/get_all_history_snapshots",
            paths,
        )

    def test_detects_lazy_short_circuit_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        tampered["lazy_short_circuit"]["value"][
            "unreached_conversion_attempt_count"
        ] = 1

        paths = {difference["path"] for difference in _diff(self.reference, tampered)}
        self.assertIn(
            "/lazy_short_circuit/value/unreached_conversion_attempt_count",
            paths,
        )


class RouterCollisionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = _routing_contracts(
            tool_spec=_tool_spec,
            accepted_entry=_accepted_entry,
            exact=_exact_json_snapshot,
        )

    @classmethod
    def case(cls, section: str, name: str) -> dict[str, object]:
        return cls.contracts[section]["value"][name]["value"]

    def test_tools_field_cannot_supply_a_trigger_but_signals_still_can(self) -> None:
        stripped = self.case(
            "context_boundaries",
            "tools_field_false_positive_is_stripped",
        )
        retained = self.case(
            "context_boundaries",
            "tools_field_is_stripped_but_signal_field_is_retained",
        )

        self.assertEqual(stripped["selected_order"], [])
        decision = retained["decisions"]["tool_list_and_signal_helper"]
        self.assertEqual(retained["selected_order"], ["tool_list_and_signal_helper"])
        self.assertEqual(
            decision["matched_positive_triggers"],
            ["real_visible_signal"],
        )

    def test_family_only_metadata_match_and_missing_context_equivalence(self) -> None:
        family = self.case(
            "context_boundaries",
            "task_family_metadata_match_without_trigger",
        )["decisions"]["family_metadata_only_helper"]
        none_context = self.case("context_boundaries", "none_context")
        empty_context = self.case("context_boundaries", "empty_context")

        self.assertTrue(family["visible"])
        self.assertEqual(family["matched_positive_triggers"], [])
        self.assertEqual(family["matched_task_families"], ["metadata_only_family"])
        self.assertEqual(none_context, empty_context)

    def test_overlapping_message_rules_keep_both_specific_selectors(self) -> None:
        observed = self.case(
            "message_rule_collisions",
            "content_rule_precedes_counterparty_rule_for_generic_selector",
        )

        self.assertEqual(
            observed["selected_order"],
            [
                "select_message_content_by_recency",
                "select_message_counterparty_for_contact_update",
            ],
        )
        self.assertEqual(
            observed["decisions"]["select_record_by_timestamp_extreme"]["reason"],
            "message_content_selector_preferred_over_generic_timestamp_selector",
        )
        self.assertEqual(
            observed["decisions"]["resolve_search_window_or_bounds"]["reason"],
            "message_recency_uses_content_selector_not_search_window",
        )

    def test_negative_and_exact_scenario_blocks_win_lifecycle_collisions(self) -> None:
        negative = self.case(
            "lifecycle_thresholds",
            "negative_trigger_hard_block_beats_clean_lifecycle_family_override",
        )["decisions"]["prepare_specific_location_search_args"]
        exact_harm = self.case(
            "lifecycle_thresholds",
            "exact_harmful_scenario_beats_visible_signal",
        )["decisions"]["prepare_specific_location_search_args"]

        self.assertEqual(negative["reason"], "blocked_by_negative_trigger")
        self.assertEqual(negative["matched_negative_triggers"], ["poison_context"])
        self.assertEqual(
            exact_harm["reason"],
            "lifecycle_suppressed_exact_harmful_called_scenario",
        )

    def test_guardrail_and_native_alternative_precedence(self) -> None:
        guard = self.case(
            "downstream_contracts",
            "guardrail_precedes_insufficiency_downstream_bypass",
        )["decisions"]["prepare_safe_action_or_abstain"]
        action_only = self.case(
            "downstream_contracts",
            "native_alternative_rule_precedes_generic_any_action_only",
        )["decisions"]["native_alternative_over_any_helper"]
        producer_and_action = self.case(
            "downstream_contracts",
            "native_alternative_rule_accepts_producer_plus_one_action",
        )["decisions"]["native_alternative_over_any_helper"]

        self.assertEqual(
            guard["reason"],
            "abstention_guard_suppressed_for_no_tool_guardrail",
        )
        self.assertEqual(
            action_only["reason"],
            "blocked_by_missing_downstream_original_tool",
        )
        self.assertTrue(producer_and_action["visible"])

    def test_composite_retains_evidence_while_budget_suppression_clears_it(
        self,
    ) -> None:
        composite = self.case(
            "evidence_retention",
            "composite_suppression_preserves_prior_match_evidence",
        )["decisions"]["lower_shared_helper"]
        budget = self.case(
            "evidence_retention",
            "budget_suppression_clears_prior_match_evidence",
        )["decisions"]["zeta_budget"]

        self.assertEqual(composite["matched_positive_triggers"], ["shared_signal"])
        self.assertEqual(budget["matched_positive_triggers"], [])
        self.assertEqual(budget["reason"], "blocked_by_context_budget")


class NormalizationBoundaryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = _normalization_contracts(
            tool_spec=_tool_spec,
            exact=_exact_json_snapshot,
        )

    @classmethod
    def result(cls, section: str, name: str) -> dict[str, object]:
        return cls.contracts[section]["value"][name]["value"]["result"]

    def test_device_state_collisions_use_fixed_rule_order(self) -> None:
        same_service = self.result(
            "device_state",
            "same_service_on_off_collision_uses_rule_table_order",
        )
        cross_service = self.result(
            "device_state",
            "cross_service_collision_uses_rule_table_order",
        )

        self.assertEqual(same_service["tool_name"], "set_wifi_status")
        self.assertEqual(same_service["arguments"], {"on": True})
        self.assertEqual(cross_service["tool_name"], "set_cellular_service_status")
        self.assertEqual(cross_service["arguments"], {"on": True})

    def test_coordinate_zero_and_positive_subnormal_boundary(self) -> None:
        zero = self.result(
            "reminder",
            "zero_latitude_is_not_a_concrete_coordinate",
        )
        positive = self.result(
            "reminder",
            "smallest_positive_latitude_is_concrete",
        )

        self.assertFalse(zero["should_call_add_reminder"])
        self.assertEqual(zero["abstain_reason"], "required_location_unresolved")
        self.assertTrue(positive["should_call_add_reminder"])
        self.assertEqual(positive["add_reminder_kwargs"]["latitude"], 5e-324)

    def test_timestamp_and_relative_clock_boundaries(self) -> None:
        zero = self.result(
            "reminder",
            "zero_prepared_and_resolved_timestamp_is_invalid",
        )
        positive = self.result(
            "reminder",
            "smallest_positive_prepared_timestamp_is_valid",
        )
        latest_valid = self.result("reminder", "relative_time_2359_is_valid")
        invalid_hour = self.result("reminder", "relative_hour_24_is_invalid")
        invalid_minute = self.result("reminder", "relative_minute_60_is_invalid")

        self.assertFalse(zero["should_call_add_reminder"])
        self.assertTrue(positive["should_call_add_reminder"])
        self.assertTrue(latest_valid["should_call_add_reminder"])
        self.assertFalse(invalid_hour["should_call_add_reminder"])
        self.assertFalse(invalid_minute["should_call_add_reminder"])


class RouterAndNormalizerTamperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.routing = _routing_contracts(
            tool_spec=_tool_spec,
            accepted_entry=_accepted_entry,
            exact=_exact_json_snapshot,
        )
        cls.normalization = _normalization_contracts(
            tool_spec=_tool_spec,
            exact=_exact_json_snapshot,
        )

    def test_detects_routing_precedence_tamper(self) -> None:
        reference = self.routing["evidence_retention"]
        tampered = copy.deepcopy(reference)
        decision = tampered["value"]["budget_suppression_clears_prior_match_evidence"][
            "value"
        ]["decisions"]["zeta_budget"]
        decision["matched_positive_triggers"] = ["budget_signal"]

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/budget_suppression_clears_prior_match_evidence/value/"
            "decisions/zeta_budget/matched_positive_triggers/0",
            paths,
        )

    def test_detects_coordinate_boundary_tamper(self) -> None:
        reference = self.normalization["reminder"]
        tampered = copy.deepcopy(reference)
        result = tampered["value"]["zero_latitude_is_not_a_concrete_coordinate"][
            "value"
        ]["result"]
        result["should_call_add_reminder"] = True

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/zero_latitude_is_not_a_concrete_coordinate/value/result/"
            "should_call_add_reminder",
            paths,
        )


if __name__ == "__main__":
    unittest.main()
