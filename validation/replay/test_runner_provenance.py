"""Contract and tamper checks for the external runner/provenance probe."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from validation.replay.compare import _diff  # noqa: E402
from validation.replay.runner_provenance import (  # noqa: E402
    RUNNER_SHA256,
    SHELL_ENTRYPOINT_SHA256,
    assert_frozen_source_hashes,
    run_probe,
)
from validation.replay.snapshot import (
    _capture_exact_call,
    _exact_json_snapshot,
)  # noqa: E402


class RunnerProvenanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = run_probe(
            ROOT,
            exact=_exact_json_snapshot,
            capture=_capture_exact_call,
        )

    def test_frozen_launcher_and_shell_hashes_are_exact(self) -> None:
        hashes = self.contract["frozen_source_hashes"]
        self.assertEqual(hashes["runner"]["sha256"], RUNNER_SHA256)
        self.assertEqual(hashes["shell_entrypoint"]["sha256"], SHELL_ENTRYPOINT_SHA256)
        assert_frozen_source_hashes(hashes)

    def test_manifest_preserves_writer_and_semantic_byte_contract(self) -> None:
        manifest = self.contract["run_manifest"]
        self.assertTrue(manifest["ends_with_newline"])
        self.assertEqual(
            manifest["top_level_key_order"][:3], ["agent", "user", "scenario_names"]
        )
        self.assertEqual(manifest["parsed_exact"]["python_type"], "dict")
        self.assertIn(
            '"actor_selection_mode":"policy"', manifest["parsed_exact"]["raw_json"]
        )

    def test_progress_transform_result_and_usage_order_are_frozen(self) -> None:
        timeline = self.contract["scenario_sequence"]["timeline"]["value"]
        progress = [row for row in timeline if row["call"] == "progress_hook"]
        self.assertEqual(
            [(row["status"], row["row_names"]) for row in progress],
            [
                ("running", []),
                ("running", ["alpha_task"]),
                ("running", ["alpha_task", "beta_task"]),
                ("complete", ["alpha_task", "beta_task"]),
            ],
        )
        run_calls = [row for row in timeline if row["call"] == "run_one_scenario"]
        self.assertEqual(
            [(row["name"], row["order_env"]) for row in run_calls],
            [("alpha_task", "0"), ("beta_task", "1")],
        )
        alpha = run_calls[0]
        self.assertEqual(alpha["scenario"]["stage"], "base")
        snapshots = [
            i
            for i, row in enumerate(timeline)
            if row["call"] == "snapshot_scenario_usage"
        ]
        clears = [
            i for i, row in enumerate(timeline) if row["call"] == "clear_scenario_usage"
        ]
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(len(clears), 2)
        self.assertTrue(
            all(snapshot < clear for snapshot, clear in zip(snapshots, clears))
        )

    def test_result_hook_fallback_identity_and_evaluator_reassertion_are_frozen(
        self,
    ) -> None:
        cases = self.contract["scenario_sequence_edges"]["value"]
        for name in ("none", "empty", "mutate_none"):
            with self.subTest(name=name):
                case = cases[name]
                self.assertTrue(
                    case["identity"]["summary_contains_run_result_by_identity"]
                )
                self.assertFalse(
                    case["identity"]["summary_contains_hook_return_by_identity"]
                )
                self.assertEqual(
                    case["result_summary"]["per_scenario_results"][0]["name"],
                    "edge_task",
                )
        self.assertEqual(
            cases["mutate_none"]["result_summary"]["per_scenario_results"][0][
                "in_place_hook_marker"
            ],
            "retained",
        )
        for name in ("fresh_spoof", "fresh_omitted"):
            with self.subTest(name=name):
                case = cases[name]
                row = case["result_summary"]["per_scenario_results"][0]
                self.assertFalse(
                    case["identity"]["summary_contains_run_result_by_identity"]
                )
                self.assertTrue(
                    case["identity"]["summary_contains_hook_return_by_identity"]
                )
                self.assertEqual(
                    row["outcome_evaluator_version"], "fixture-evaluator-v1"
                )
                self.assertEqual(
                    row["outcome_evaluator_contract_sha256"],
                    "fixture-evaluator-contract",
                )
                self.assertEqual(
                    row["outcome_evaluator_source_sha256"],
                    "fixture-evaluator-source",
                )
                self.assertNotIn("original_marker", row)

    def test_progress_callback_aliasing_and_mutation_timing_are_frozen(self) -> None:
        case = self.contract["scenario_sequence_edges"]["value"]["progress_mutation"]
        progress = [row for row in case["timeline"] if row["call"] == "progress_hook"]
        self.assertEqual(len(progress), 3)
        self.assertTrue(all(row["same_list_identity"] for row in progress))
        self.assertEqual(
            [
                row["scenario_order_index"]
                for row in case["timeline"]
                if row["call"] == "run_one_scenario"
            ],
            ["1"],
        )
        self.assertTrue(case["identity"]["summary_contains_run_result_by_identity"])
        artifact_rows = case["result_summary"]["per_scenario_results"]
        self.assertEqual(
            [row["name"] for row in artifact_rows],
            ["progress_injected_row", "edge_task"],
        )
        self.assertEqual(artifact_rows[1]["progress_row_mutation"], "per_task")
        self.assertEqual(
            case["closure_run_result_after_return"]["progress_row_mutation"],
            "post_final",
        )
        self.assertEqual(
            case["closure_row_names_after_return"][-1], "progress_post_final_row"
        )

    def test_result_and_progress_callback_failure_stages_are_frozen(self) -> None:
        cases = self.contract["scenario_sequence_edges"]["value"]
        expected = {
            "result_hook_exception": ("running", 0, False, False),
            "progress_initial_exception": ("running", 0, False, False),
            "progress_per_task_exception": ("running", 1, False, True),
            "progress_final_exception": ("complete", 1, True, True),
        }
        for name, (status, count, has_final, has_usage) in expected.items():
            with self.subTest(name=name):
                case = cases[name]
                self.assertEqual(case["invocation"]["status"], "raised")
                self.assertEqual(case["invocation"]["exception_type"], "RuntimeError")
                self.assertEqual(case["live_summary"]["status"], status)
                self.assertEqual(case["live_summary"]["completed_count"], count)
                self.assertEqual(case["result_summary"] is not None, has_final)
                self.assertEqual(case["usage_artifact_exists"], has_usage)
                self.assertFalse(case["currently_running_exists"])

    def test_retry_terminal_and_checkpoint_orders_are_frozen(self) -> None:
        retries = self.contract["scenario_retry_and_terminal_failure"]
        self.assertEqual(
            retries["first_attempt_success_result"]["value"]["transient_retry_count"],
            0,
        )
        self.assertEqual(retries["retry_result"]["value"]["transient_retry_count"], 2)
        self.assertEqual(
            [row["attempt_marker"] for row in retries["retry_archives"]["value"]],
            ["1", "2"],
        )
        self.assertEqual(
            retries["terminal_result"]["value"]["exception_type"],
            "DeterministicScenarioFailure",
        )
        for key in ("frozen_run_checkpoint_order", "online_run_checkpoint_order"):
            contract = self.contract[key]
            self.assertEqual(len(contract["checkpoint_contracts"]), 1)
            events = contract["sage_run_events"]["rows_exact"]["value"]
            names = [row["event"] for row in events]
            self.assertLess(
                names.index("registry_load"), names.index("registry_checkpoint_written")
            )
            self.assertLess(
                names.index("registry_checkpoint_written"), names.index("run_finished")
            )

    def test_sparse_checkpoint_and_io_failure_semantics_are_frozen(self) -> None:
        cases = self.contract["checkpoint_edges"]["value"]
        empty = cases["empty_registry"]
        self.assertEqual(empty["invocation"]["status"], "returned")
        self.assertIsNone(empty["invocation"]["result"]["value"])
        self.assertEqual(
            empty["output_inventory"][-1]["path"],
            "registry_checkpoints/after_0001_fixture_checkpoint_task",
        )
        one_file = cases["one_file_registry"]["output_inventory"]
        metadata = next(
            row for row in one_file if row["path"].endswith("checkpoint.json")
        )
        self.assertIn('"completed_count": 5', metadata["text"])
        self.assertIn('"registry_manifest.json"', metadata["text"])
        self.assertNotIn('"tool_lifecycle.json"', metadata["text"])
        for name in ("unset_order_index", "invalid_order_index"):
            with self.subTest(name=name):
                paths = [row["path"] for row in cases[name]["output_inventory"]]
                self.assertTrue(any("after_0000_" in path for path in paths))
        self.assertEqual(cases["copy_failure"]["invocation"]["status"], "raised")
        self.assertEqual(
            cases["metadata_write_failure"]["invocation"]["status"], "raised"
        )
        self.assertFalse(
            any(
                row["path"].endswith("checkpoint.json")
                for row in cases["metadata_write_failure"]["output_inventory"]
            )
        )

    def test_nonempty_generated_tool_sets_and_jsonl_failure_are_frozen(self) -> None:
        cases = self.contract["generated_selection_edges"]["value"]
        success = cases["nonempty_selection_sets"]
        self.assertEqual(success["invocation"]["status"], "returned")
        row = success["selection_rows"][0]
        self.assertEqual(len(row["generated_tools_visible"]), 4)
        self.assertEqual(row["generated_tools_called"], ["called_tool"])
        self.assertEqual(
            row["generated_tools_attempted"],
            ["attempted_only_tool", "failed_tool", "called_tool"],
        )
        self.assertEqual(row["generated_tools_failed"], ["failed_tool"])
        failure = cases["checkpoint_event_append_failure"]
        self.assertEqual(failure["invocation"]["status"], "raised")
        self.assertEqual(failure["invocation"]["exception_type"], "OSError")
        self.assertTrue(failure["checkpoint_inventory"])
        self.assertNotIn(
            "registry_checkpoint_written",
            [event["event"] for event in failure["sage_run_events"]],
        )

    def test_campaign_and_environment_outputs_are_complete(self) -> None:
        campaign = self.contract["campaign_artifacts"]
        for name in (
            "campaign_status",
            "task_plan",
            "dated_event_ledger",
            "latest_event_ledger",
            "run_index",
            "registry_snapshot",
        ):
            self.assertTrue(campaign[name]["ends_with_newline"], name)
        environment = self.contract["environment_verifier"]
        report = environment["pass_report"]["value"]
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["external_distribution_count"], 2)
        self.assertEqual(
            report["repository_import_provenance"]["mode"], "isolated_subprocess"
        )
        failures = environment["failure_contracts"]["value"]
        self.assertTrue(all(item["status"] == "raised" for item in failures.values()))
        relationships = environment["editable_path_relationships"]["value"]
        self.assertEqual(relationships["equal"]["status"], "returned")
        self.assertEqual(relationships["descendant"]["status"], "returned")
        self.assertEqual(relationships["sibling"]["status"], "raised")
        self.assertEqual(relationships["shared_prefix"]["status"], "raised")
        self.assertEqual(failures["import_provenance_sibling"]["status"], "raised")
        self.assertEqual(
            failures["import_provenance_shared_prefix"]["status"], "raised"
        )


class RunnerProvenanceTamperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = run_probe(
            ROOT,
            exact=_exact_json_snapshot,
            capture=_capture_exact_call,
        )

    def test_detects_progress_order_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        timeline = tampered["scenario_sequence"]["timeline"]["value"]
        progress = [row for row in timeline if row["call"] == "progress_hook"]
        progress[1]["row_names"] = ["beta_task"]
        paths = {item["path"] for item in _diff(self.reference, tampered)}
        self.assertTrue(any(path.endswith("/row_names/0") for path in paths))

    def test_detects_checkpoint_event_order_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        rows = tampered["online_run_checkpoint_order"]["sage_run_events"]["rows_exact"][
            "value"
        ]
        rows[0], rows[-1] = rows[-1], rows[0]
        differences = _diff(self.reference, tampered)
        self.assertTrue(differences)

    def test_rejects_source_hash_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference["frozen_source_hashes"])
        tampered["runner"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "runner"):
            assert_frozen_source_hashes(tampered)

    def test_detects_result_hook_and_callback_stage_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        edges = tampered["scenario_sequence_edges"]["value"]
        edges["fresh_spoof"]["result_summary"]["per_scenario_results"][0][
            "outcome_evaluator_version"
        ] = "spoof-version"
        edges["progress_final_exception"]["result_summary"] = None
        paths = {item["path"] for item in _diff(self.reference, tampered)}
        self.assertTrue(any("/fresh_spoof/result_summary" in path for path in paths))
        self.assertTrue(
            any("/progress_final_exception/result_summary" in path for path in paths)
        )

    def test_detects_checkpoint_and_generated_selection_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        checkpoint = tampered["checkpoint_edges"]["value"]["one_file_registry"]
        checkpoint["output_inventory"].pop()
        selection = tampered["generated_selection_edges"]["value"]
        selection["nonempty_selection_sets"]["selection_rows"][0][
            "generated_tools_failed"
        ] = []
        paths = {item["path"] for item in _diff(self.reference, tampered)}
        self.assertTrue(any("/checkpoint_edges/" in path for path in paths))
        self.assertTrue(any("/generated_selection_edges/" in path for path in paths))

    def test_detects_environment_path_relation_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        relationships = tampered["environment_verifier"]["editable_path_relationships"][
            "value"
        ]
        relationships["shared_prefix"] = copy.deepcopy(relationships["equal"])
        paths = {item["path"] for item in _diff(self.reference, tampered)}
        self.assertTrue(
            any(
                "/editable_path_relationships/value/shared_prefix" in path
                for path in paths
            )
        )


if __name__ == "__main__":
    unittest.main()
