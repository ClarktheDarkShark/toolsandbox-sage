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
from validation.replay.snapshot import _capture_exact_call, _exact_json_snapshot  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
