from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from validation.historical.verify_historical_pytest import (
    APPROVED_WARNING_MESSAGES,
    EXPECTED_PARTITION_SHA256,
    EXPECTED_TOTAL,
    INTENTIONAL_DESELECTIONS,
    SHARDS,
    GateError,
    _environment,
    _prepare_output_directory,
    _validate_frozen_contract,
    build_command,
    parse_test_summary,
    verify_partition,
)


class FrozenGateContractTest(unittest.TestCase):
    def test_exact_summaries_total_and_seven_waived_deselections(self) -> None:
        _validate_frozen_contract()

        self.assertEqual(
            [shard.expected_summary for shard in SHARDS],
            ["398 passed", "384 passed, 7 deselected", "385 passed"],
        )
        self.assertEqual(sum(shard.expected_passed for shard in SHARDS), EXPECTED_TOTAL)
        self.assertEqual(EXPECTED_TOTAL, 1_167)
        self.assertEqual(len(INTENTIONAL_DESELECTIONS), 7)
        self.assertEqual(SHARDS[0].deselections, ())
        self.assertEqual(SHARDS[1].deselections, INTENTIONAL_DESELECTIONS)
        self.assertEqual(SHARDS[2].deselections, ())
        self.assertEqual(
            EXPECTED_PARTITION_SHA256,
            "b7d6f521ed1aceed160a960a42f5a362d242b92e8b2953a65b7c19dcd421ae5b",
        )

        waiver_path = (
            Path(__file__).resolve().parents[1] / "contract/deletion_waivers_v1.json"
        )
        waiver = json.loads(waiver_path.read_text(encoding="utf-8"))
        self.assertEqual(
            tuple(waiver["waivers"][0]["allowed_failures"]),
            INTENTIONAL_DESELECTIONS,
        )

    def test_command_has_exact_isolation_flags_and_only_approved_deselections(
        self,
    ) -> None:
        command = build_command(
            SHARDS[1],
            python=Path("/publication/python"),
            basetemp=Path("/private/tmp/gate/shard2"),
            collect_only=True,
        )

        self.assertEqual(
            command[:8],
            [
                "/publication/python",
                "-m",
                "pytest",
                "--import-mode=importlib",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp=/private/tmp/gate/shard2",
            ],
        )
        self.assertEqual(command[8], "--collect-only")
        self.assertEqual(
            tuple(
                argument.removeprefix("--deselect=")
                for argument in command
                if argument.startswith("--deselect=")
            ),
            INTENTIONAL_DESELECTIONS,
        )

    def test_pythonpath_contains_only_candidate_source_and_root(self) -> None:
        candidate = Path("/candidate").resolve()

        environment = _environment(candidate)

        self.assertEqual(
            environment["PYTHONPATH"],
            f"{candidate / 'src'}:{candidate}",
        )


class SummaryTest(unittest.TestCase):
    def test_parses_exact_core_summary_without_warnings(self) -> None:
        parsed = parse_test_summary("dots\n384 passed, 7 deselected in 10.25s\n")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["summary"], "384 passed, 7 deselected")
        self.assertEqual(parsed["core_summary"], "384 passed, 7 deselected")
        self.assertEqual(parsed["passed"], 384)
        self.assertEqual(parsed["deselected"], 7)
        self.assertEqual(parsed["warnings"], 0)
        self.assertEqual(parsed["warning_families"], [])
        self.assertTrue(parsed["warnings_approved"])

    def test_accepts_and_records_exact_two_dependency_warnings(self) -> None:
        warning_text = "\n".join(APPROVED_WARNING_MESSAGES.values())
        parsed = parse_test_summary(
            f"{warning_text}\n"
            "384 passed, 7 deselected, 2 warnings in 556.00s (0:09:16)\n"
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["summary"], "384 passed, 7 deselected, 2 warnings")
        self.assertEqual(parsed["core_summary"], "384 passed, 7 deselected")
        self.assertEqual(parsed["warnings"], 2)
        self.assertEqual(parsed["warning_families"], sorted(APPROVED_WARNING_MESSAGES))
        self.assertTrue(parsed["warnings_approved"])

    def test_records_but_does_not_approve_unknown_or_partial_warnings(self) -> None:
        unknown = parse_test_summary(
            "UserWarning: something else\n398 passed, 2 warnings in 4.00s\n"
        )
        partial = parse_test_summary(
            f"{next(iter(APPROVED_WARNING_MESSAGES.values()))}\n"
            "398 passed, 2 warnings in 4.00s\n"
        )

        self.assertIsNotNone(unknown)
        self.assertIsNotNone(partial)
        assert unknown is not None and partial is not None
        self.assertEqual(unknown["warnings"], 2)
        self.assertFalse(unknown["warnings_approved"])
        self.assertFalse(partial["warnings_approved"])

    def test_rejects_summary_with_any_other_pytest_outcome(self) -> None:
        self.assertIsNone(
            parse_test_summary("397 passed, 1 warning, 1 skipped in 4.00s\n")
        )
        self.assertIsNone(parse_test_summary("397 passed, 1 failed in 4.00s\n"))
        self.assertIsNone(
            parse_test_summary(
                "351 passed, 7 deselected, 2 warnings, 33 errors in 537.36s\n"
            )
        )
        self.assertIsNone(
            parse_test_summary("398 passed in 4.00s\npost-summary plugin output\n")
        )


class PartitionTest(unittest.TestCase):
    def test_verifies_unique_sorted_union_without_trailing_newline(self) -> None:
        expected_digest = hashlib.sha256(b"a\nb\nc").hexdigest()

        result = verify_partition(
            {"shard1": ["c"], "shard2": ["a"], "shard3": ["b"]},
            expected_counts={"shard1": 1, "shard2": 1, "shard3": 1},
            expected_total=3,
            expected_sha256=expected_digest,
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["unique_nodeids"], 3)
        self.assertEqual(result["hash_encoding"], "no_trailing_newline")
        self.assertEqual(result["sha256"], expected_digest)

    def test_fails_on_cross_shard_overlap_even_when_union_hash_matches(self) -> None:
        expected_digest = hashlib.sha256(b"a\nb").hexdigest()

        result = verify_partition(
            {"shard1": ["a"], "shard2": ["a"], "shard3": ["b"]},
            expected_counts={"shard1": 1, "shard2": 1, "shard3": 1},
            expected_total=2,
            expected_sha256=expected_digest,
        )

        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any("duplicate an earlier shard" in item for item in result["failures"])
        )


class OutputDirectoryTest(unittest.TestCase):
    def test_refuses_to_reuse_a_nonempty_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gate-output"
            output.mkdir()
            (output / "old.log").write_text("keep\n", encoding="utf-8")

            with self.assertRaisesRegex(GateError, "not empty"):
                _prepare_output_directory(output)


if __name__ == "__main__":
    unittest.main()
