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

    def test_marker_shape_controls_exact_tools_field_stripping_boundary(self) -> None:
        no_signals = self.case(
            "context_boundaries",
            "tools_field_without_signals_marker_is_not_stripped",
        )
        repeated = self.case(
            "context_boundaries",
            "multiple_marker_pairs_strip_only_the_first_tools_segment",
        )
        reversed_markers = self.case(
            "context_boundaries",
            "reversed_signals_then_tools_markers_retain_the_tools_suffix",
        )

        self.assertEqual(no_signals["selected_order"], ["unstripped_tools_helper"])
        self.assertEqual(
            no_signals["decisions"]["unstripped_tools_helper"][
                "matched_positive_triggers"
            ],
            ["unstripped_tool_token"],
        )
        self.assertEqual(
            repeated["selected_order"],
            [
                "first_signal_helper",
                "second_signal_helper",
                "second_tools_helper",
            ],
        )
        self.assertEqual(
            repeated["decisions"]["first_tools_helper"]["reason"],
            "visible_context_no_match",
        )
        self.assertEqual(
            reversed_markers["selected_order"],
            ["reversed_signal_helper", "reversed_tools_helper"],
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

    def test_task_family_key_is_appended_to_both_metadata_match_channels(self) -> None:
        observed = self.case(
            "context_boundaries",
            "task_family_augmentation_matches_both_metadata_channels",
        )
        decision = observed["decisions"]["augmented_family_helper"]

        self.assertEqual(observed["selected_order"], ["augmented_family_helper"])
        self.assertEqual(decision["reason"], "visible_context_metadata_match")
        self.assertEqual(decision["matched_positive_triggers"], ["augmented_family"])
        self.assertEqual(decision["matched_task_families"], ["augmented_family"])

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

    def test_raw_tools_message_recency_activates_post_route_suppression(self) -> None:
        observed = self.case(
            "message_rule_collisions",
            "raw_tools_message_recency_activates_post_route_suppression",
        )
        decision = observed["decisions"]["resolve_search_window_or_bounds"]

        self.assertEqual(observed["selected_order"], [])
        self.assertEqual(
            decision["reason"],
            "message_recency_uses_content_selector_not_search_window",
        )
        self.assertEqual(decision["matched_positive_triggers"], ["recency_search"])
        self.assertEqual(decision["matched_task_families"], ["recency_search"])

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

    def test_lifecycle_uses_task_family_key_and_short_circuits_without_it(
        self,
    ) -> None:
        park = self.case("lifecycle_thresholds", "park_is_hidden")
        parked = self.case("lifecycle_thresholds", "parked_is_hidden")
        no_family = self.case(
            "lifecycle_thresholds",
            "absent_task_family_short_circuits_even_a_parked_row",
        )
        positional = self.case(
            "lifecycle_thresholds",
            "positional_scenario_name_does_not_drive_lifecycle_matching",
        )
        family_key = self.case(
            "lifecycle_thresholds",
            "task_family_key_drives_exact_lifecycle_matching",
        )

        for observed in (park, parked):
            self.assertEqual(observed["selected_order"], [])
            self.assertEqual(
                observed["decisions"]["prepare_specific_location_search_args"][
                    "reason"
                ],
                "lifecycle_suppressed_parked_tool",
            )
        self.assertEqual(
            no_family["selected_order"],
            ["prepare_specific_location_search_args"],
        )
        self.assertEqual(
            positional["selected_order"],
            ["prepare_specific_location_search_args"],
        )
        self.assertEqual(family_key["selected_order"], [])

    def test_lifecycle_fallbacks_count_duplicates_and_exact_harm_wins_ties(
        self,
    ) -> None:
        exact_tie = self.case(
            "lifecycle_thresholds",
            "exact_harm_beats_an_equal_helpful_family_count",
        )
        malformed_count = self.case(
            "lifecycle_thresholds",
            "malformed_harmful_count_falls_back_to_scenario_list_length",
        )
        duplicate_harm = self.case(
            "lifecycle_thresholds",
            "harmful_family_fallback_counts_duplicate_scenarios",
        )
        duplicate_tie = self.case(
            "lifecycle_thresholds",
            "helpful_family_fallback_counts_duplicates_and_ties_harm",
        )

        self.assertEqual(exact_tie["selected_order"], [])
        self.assertEqual(malformed_count["selected_order"], [])
        self.assertEqual(duplicate_harm["selected_order"], [])
        self.assertEqual(
            duplicate_tie["selected_order"],
            ["prepare_specific_location_search_args"],
        )

    def test_count_coercion_quirks_differ_between_abstention_and_override(
        self,
    ) -> None:
        malformed_abstention = self.case(
            "lifecycle_thresholds",
            "malformed_abstention_counts_are_treated_as_operationally_clean",
        )
        negative_abstention = self.case(
            "lifecycle_thresholds",
            "negative_abstention_counts_are_not_operationally_clean",
        )
        malformed_failed = self.case(
            "lifecycle_thresholds",
            "malformed_failed_count_blocks_visible_signal_override",
        )
        malformed_incident = self.case(
            "lifecycle_thresholds",
            "malformed_incident_count_blocks_visible_signal_override",
        )
        negative_override = self.case(
            "lifecycle_thresholds",
            "negative_failure_and_incident_counts_allow_visible_signal_override",
        )

        self.assertEqual(
            malformed_abstention["selected_order"],
            ["prepare_safe_action_or_abstain"],
        )
        self.assertEqual(negative_abstention["selected_order"], [])
        self.assertEqual(malformed_failed["selected_order"], [])
        self.assertEqual(malformed_incident["selected_order"], [])
        self.assertEqual(
            negative_override["selected_order"],
            ["prepare_specific_location_search_args"],
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

    def test_downstream_schema_precedence_and_family_specific_any_rules(self) -> None:
        enum_loses = self.case(
            "downstream_contracts",
            "downstream_tool_name_overrides_an_earlier_tool_name_enum",
        )
        preserved_action = self.case(
            "downstream_contracts",
            "downstream_tool_name_uses_preserved_action_after_enum_override",
        )
        derived_one = self.case(
            "downstream_contracts",
            "derived_multi_producer_requires_any_one",
        )
        derived_none = self.case(
            "downstream_contracts",
            "derived_multi_producer_is_hidden_when_none_are_available",
        )

        self.assertEqual(enum_loses["selected_order"], [])
        self.assertEqual(
            preserved_action["selected_order"],
            ["enum_then_downstream_name_helper"],
        )
        self.assertEqual(
            derived_one["selected_order"],
            ["derived_any_producer_helper"],
        )
        self.assertEqual(derived_none["selected_order"], [])

    def test_preserved_fallback_search_narrowing_and_available_none_boundary(
        self,
    ) -> None:
        preserved_missing = self.case(
            "downstream_contracts",
            "empty_required_calls_fall_back_to_preserved_tools",
        )
        preserved_present = self.case(
            "downstream_contracts",
            "preserved_fallback_is_satisfied_when_preserved_tool_is_available",
        )
        search_union = self.case(
            "downstream_contracts",
            "search_helper_narrows_required_and_preserved_union_to_producers",
        )
        action_only = self.case(
            "downstream_contracts",
            "search_helper_rejects_an_action_without_any_producer",
        )
        none_base = self.case(
            "downstream_contracts",
            "none_available_base_tools_bypasses_downstream_validation",
        )
        empty_base = self.case(
            "downstream_contracts",
            "empty_available_base_tools_enforces_downstream_validation",
        )

        self.assertEqual(preserved_missing["selected_order"], [])
        self.assertEqual(
            preserved_present["selected_order"],
            ["preserved_fallback_helper"],
        )
        self.assertEqual(
            search_union["selected_order"],
            ["select_search_union_helper"],
        )
        self.assertEqual(action_only["selected_order"], [])
        self.assertEqual(none_base["selected_order"], ["all_required_helper"])
        self.assertEqual(empty_base["selected_order"], [])

    def test_single_native_action_and_insufficiency_bypass_boundaries(self) -> None:
        single_missing = self.case(
            "downstream_contracts",
            "one_native_action_still_requires_every_dependency",
        )
        single_complete = self.case(
            "downstream_contracts",
            "one_native_action_and_its_producer_are_sufficient",
        )
        multiple_complete = self.case(
            "downstream_contracts",
            "native_alternative_rule_accepts_producer_plus_one_action",
        )
        bypass = self.case(
            "downstream_contracts",
            "insufficiency_guard_bypasses_missing_downstream_when_no_guard_matches",
        )
        no_tool_guard = self.case(
            "downstream_contracts",
            "guardrail_precedes_insufficiency_downstream_bypass",
        )

        self.assertEqual(single_missing["selected_order"], [])
        self.assertEqual(
            single_complete["selected_order"],
            ["single_native_action_helper"],
        )
        self.assertEqual(
            multiple_complete["selected_order"],
            ["native_alternative_over_any_helper"],
        )
        self.assertEqual(
            bypass["selected_order"],
            ["prepare_safe_action_or_abstain"],
        )
        self.assertEqual(no_tool_guard["selected_order"], [])

    def test_bundle_cap_composite_fill_and_registry_alias_order(self) -> None:
        default_cap = self.case(
            "ordering_and_budget",
            "default_signature_value_five_is_clamped_to_four",
        )
        explicit_cap = self.case(
            "ordering_and_budget",
            "explicit_bundle_size_above_four_is_clamped_to_four",
        )
        composite_fill = self.case(
            "subsumption_collisions",
            "composite_suppression_happens_before_budget_fill",
        )
        alias_order = self.case(
            "registry_identity_mismatches",
            "registry_alias_controls_lexical_tie_break_not_spec_name",
        )

        expected_cap = [
            "alpha_clamp",
            "bravo_clamp",
            "charlie_clamp",
            "delta_clamp",
        ]
        self.assertEqual(default_cap["selected_order"], expected_cap)
        self.assertEqual(explicit_cap["selected_order"], expected_cap)
        self.assertEqual(
            composite_fill["selected_order"],
            [
                "alpha_composite_helper",
                "bravo_fill",
                "charlie_fill",
                "delta_fill",
            ],
        )
        self.assertEqual(
            composite_fill["decisions"]["lower_shared_helper"]["status"],
            "deprioritized",
        )
        self.assertEqual(
            composite_fill["decisions"]["echo_fill"]["reason"],
            "blocked_by_context_budget",
        )
        self.assertEqual(
            alias_order["input_entry_order"],
            ["zeta_registry_alias", "alpha_registry_alias"],
        )
        self.assertEqual(
            alias_order["decision_order"],
            ["alpha_registry_alias", "zeta_registry_alias"],
        )
        self.assertEqual(
            alias_order["selected_order"],
            ["zeta_spec_name_selected_by_alpha_alias"],
        )

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

    def test_full_decision_evidence_is_preserved_only_for_composite_suppression(
        self,
    ) -> None:
        composite = self.case(
            "evidence_retention",
            "composite_suppression_preserves_the_full_prior_decision_payload",
        )["decisions"]["rich_lower_helper"]
        budget = self.case(
            "evidence_retention",
            "budget_suppression_clears_the_full_prior_decision_payload",
        )["decisions"]["zeta_rich_budget"]

        self.assertEqual(
            composite,
            {
                "tool_name": "rich_lower_helper",
                "visible": False,
                "status": "deprioritized",
                "reason": (
                    "more_specific_generated_tool_preferred_over_redundant_"
                    "lower_level_tool:rich_composite_helper"
                ),
                "score": 8,
                "matched_positive_triggers": ["rich_signal"],
                "matched_negative_triggers": [],
                "matched_task_families": ["rich_family"],
                "fair_chance_candidate": False,
                "fair_chance_reason": "",
            },
        )
        self.assertEqual(
            budget,
            {
                "tool_name": "zeta_rich_budget",
                "visible": False,
                "status": "deprioritized",
                "reason": "blocked_by_context_budget",
                "score": 8,
                "matched_positive_triggers": [],
                "matched_negative_triggers": [],
                "matched_task_families": [],
                "fair_chance_candidate": False,
                "fair_chance_reason": "",
            },
        )

    def test_suppression_evidence_payloads_copy_or_drop_signals_exactly(self) -> None:
        copied = self.case(
            "evidence_retention",
            "service_scalar_suppression_copies_matched_signal_as_family_evidence",
        )["decisions"]["extract_temperature_result"]
        dropped = self.case(
            "evidence_retention",
            "recency_action_context_suppression_does_not_copy_signal_evidence",
        )["decisions"]["select_action_target_by_recency"]

        self.assertEqual(
            copied,
            {
                "tool_name": "extract_temperature_result",
                "visible": False,
                "status": "hidden",
                "reason": "service_scalar_extractor_requires_matching_visible_request",
                "score": -25,
                "matched_positive_triggers": [],
                "matched_negative_triggers": [],
                "matched_task_families": ["service_answer_extraction"],
                "fair_chance_candidate": False,
                "fair_chance_reason": "",
            },
        )
        self.assertEqual(
            dropped,
            {
                "tool_name": "select_action_target_by_recency",
                "visible": False,
                "status": "hidden",
                "reason": "recency_action_selector_requires_reminder_action_context",
                "score": -25,
                "matched_positive_triggers": [],
                "matched_negative_triggers": [],
                "matched_task_families": [],
                "fair_chance_candidate": False,
                "fair_chance_reason": "",
            },
        )

    def test_registry_key_controls_routing_identity_when_spec_name_differs(
        self,
    ) -> None:
        visible = self.case(
            "registry_identity_mismatches",
            "registry_key_controls_decision_identity_but_spec_name_is_selected",
        )
        spec_lifecycle = self.case(
            "registry_identity_mismatches",
            "lifecycle_row_keyed_by_spec_name_does_not_match_registry_alias",
        )
        registry_lifecycle = self.case(
            "registry_identity_mismatches",
            "lifecycle_row_keyed_by_registry_alias_suppresses_mismatched_spec",
        )

        self.assertEqual(visible["input_entry_order"], ["registry_alias"])
        self.assertEqual(visible["decision_order"], ["registry_alias"])
        self.assertEqual(visible["selected_order"], ["spec_identity_helper"])
        self.assertEqual(
            visible["decisions"]["registry_alias"]["tool_name"],
            "registry_alias",
        )
        self.assertEqual(spec_lifecycle["selected_order"], ["spec_identity_helper"])
        self.assertEqual(registry_lifecycle["selected_order"], [])
        self.assertEqual(
            registry_lifecycle["decisions"]["registry_alias"]["reason"],
            "lifecycle_suppressed_parked_tool",
        )

    def test_public_router_signature_module_and_adapter_import_identity(self) -> None:
        observed = self.contracts["public_compatibility"]["value"]

        self.assertEqual(
            observed["runtime_module"],
            "sage_ts.runtime.toolsandbox_integration",
        )
        self.assertEqual(observed["runtime_qualname"], "route_registry_entries")
        self.assertEqual(observed["runtime_default_max_bundle_size"], 5)
        self.assertEqual(
            observed["runtime_parameter_order"],
            [
                "entries",
                "scenario_name",
                "max_bundle_size",
                "available_base_tools",
                "lifecycle_state",
                "task_context_text",
                "task_family_key",
            ],
        )
        self.assertTrue(observed["adapter_import_is_runtime_object"])
        self.assertTrue(observed["adapter_signature_matches_runtime"])
        self.assertTrue(observed["module_attribute_is_imported_object"])


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

    def test_detects_marker_boundary_tamper(self) -> None:
        reference = self.routing["context_boundaries"]
        tampered = copy.deepcopy(reference)
        case = tampered["value"][
            "multiple_marker_pairs_strip_only_the_first_tools_segment"
        ]["value"]
        case["selected_order"].append("first_tools_helper")

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/multiple_marker_pairs_strip_only_the_first_tools_segment/"
            "value/selected_order/3",
            paths,
        )

    def test_detects_raw_post_route_activation_tamper(self) -> None:
        reference = self.routing["message_rule_collisions"]
        tampered = copy.deepcopy(reference)
        decision = tampered["value"][
            "raw_tools_message_recency_activates_post_route_suppression"
        ]["value"]["decisions"]["resolve_search_window_or_bounds"]
        decision["visible"] = True

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/raw_tools_message_recency_activates_post_route_suppression/"
            "value/decisions/resolve_search_window_or_bounds/visible",
            paths,
        )

    def test_detects_suppression_evidence_tamper(self) -> None:
        reference = self.routing["evidence_retention"]
        tampered = copy.deepcopy(reference)
        decision = tampered["value"][
            "service_scalar_suppression_copies_matched_signal_as_family_evidence"
        ]["value"]["decisions"]["extract_temperature_result"]
        decision["matched_task_families"] = []

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/"
            "service_scalar_suppression_copies_matched_signal_as_family_evidence/"
            "value/decisions/extract_temperature_result/matched_task_families/0",
            paths,
        )

    def test_detects_registry_and_spec_identity_tamper(self) -> None:
        reference = self.routing["registry_identity_mismatches"]
        tampered = copy.deepcopy(reference)
        case = tampered["value"][
            "registry_key_controls_decision_identity_but_spec_name_is_selected"
        ]["value"]
        case["decisions"]["registry_alias"]["tool_name"] = "spec_identity_helper"

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/registry_key_controls_decision_identity_but_spec_name_is_selected/"
            "value/decisions/registry_alias/tool_name",
            paths,
        )

    def test_detects_lifecycle_count_coercion_tamper(self) -> None:
        reference = self.routing["lifecycle_thresholds"]
        tampered = copy.deepcopy(reference)
        case = tampered["value"][
            "malformed_abstention_counts_are_treated_as_operationally_clean"
        ]["value"]
        case["selected_order"] = []
        case["decisions"]["prepare_safe_action_or_abstain"]["visible"] = False

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/malformed_abstention_counts_are_treated_as_operationally_clean/"
            "value/selected_order/0",
            paths,
        )
        self.assertIn(
            "/value/malformed_abstention_counts_are_treated_as_operationally_clean/"
            "value/decisions/prepare_safe_action_or_abstain/visible",
            paths,
        )

    def test_detects_downstream_precedence_tamper(self) -> None:
        reference = self.routing["downstream_contracts"]
        tampered = copy.deepcopy(reference)
        decision = tampered["value"][
            "downstream_tool_name_overrides_an_earlier_tool_name_enum"
        ]["value"]["decisions"]["enum_then_downstream_name_helper"]
        decision["reason"] = "visible_context_metadata_match"

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/downstream_tool_name_overrides_an_earlier_tool_name_enum/"
            "value/decisions/enum_then_downstream_name_helper/reason",
            paths,
        )

    def test_detects_composite_before_cap_tamper(self) -> None:
        reference = self.routing["subsumption_collisions"]
        tampered = copy.deepcopy(reference)
        case = tampered["value"]["composite_suppression_happens_before_budget_fill"][
            "value"
        ]
        case["selected_order"].remove("delta_fill")

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn(
            "/value/composite_suppression_happens_before_budget_fill/"
            "value/selected_order/3",
            paths,
        )

    def test_detects_public_compatibility_tamper(self) -> None:
        reference = self.routing["public_compatibility"]
        tampered = copy.deepcopy(reference)
        tampered["value"]["runtime_default_max_bundle_size"] = 4
        tampered["value"]["adapter_import_is_runtime_object"] = False

        paths = {difference["path"] for difference in _diff(reference, tampered)}
        self.assertIn("/value/runtime_default_max_bundle_size", paths)
        self.assertIn("/value/adapter_import_is_runtime_object", paths)

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
