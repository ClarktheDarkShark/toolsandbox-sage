"""Integrity and tamper checks for the readable generator/validator corpus."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from validation.replay.generator_validator_corpus import (
    GENERIC_PROFILE_NAME,
    PROFILE_NAMES,
    VALIDATOR_ERROR_KINDS,
    _assert_profile_coverage,
    _assert_validator_error_coverage,
)


class GeneratorProfileIntegrityTests(unittest.TestCase):
    def test_exact_34_profile_fixture_is_complete(self) -> None:
        self.assertEqual(len(PROFILE_NAMES), 34)
        self.assertEqual(len(PROFILE_NAMES), len(set(PROFILE_NAMES)))
        self.assertNotIn(GENERIC_PROFILE_NAME, PROFILE_NAMES)
        _assert_profile_coverage(PROFILE_NAMES)

    def test_missing_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing=.*extract_stock_symbol"):
            _assert_profile_coverage(
                tuple(name for name in PROFILE_NAMES if name != "extract_stock_symbol")
            )

    def test_reordered_profile_is_rejected(self) -> None:
        tampered = (PROFILE_NAMES[1], PROFILE_NAMES[0], *PROFILE_NAMES[2:])
        with self.assertRaisesRegex(RuntimeError, "order_matches=True"):
            _assert_profile_coverage(tampered)

    def test_duplicate_profile_is_rejected(self) -> None:
        tampered = (*PROFILE_NAMES[:-1], PROFILE_NAMES[0])
        with self.assertRaisesRegex(RuntimeError, "duplicates="):
            _assert_profile_coverage(tampered)


class ValidatorBranchIntegrityTests(unittest.TestCase):
    def test_declared_error_kinds_are_unique(self) -> None:
        self.assertEqual(len(VALIDATOR_ERROR_KINDS), len(set(VALIDATOR_ERROR_KINDS)))

    def test_complete_synthetic_coverage_is_accepted(self) -> None:
        errors = tuple(f"source_0_{kind}:detail" for kind in VALIDATOR_ERROR_KINDS)
        _assert_validator_error_coverage(errors)

    def test_removed_branch_is_rejected(self) -> None:
        errors = tuple(
            f"held_out_2_{kind}:detail"
            for kind in VALIDATOR_ERROR_KINDS
            if kind != "native_action_arguments_invalid"
        )
        with self.assertRaisesRegex(RuntimeError, "native_action_arguments_invalid"):
            _assert_validator_error_coverage(errors)


class DeletionWaiverIntegrityTests(unittest.TestCase):
    def test_legacy_prompt_waiver_is_exact_and_allows_no_replay_difference(
        self,
    ) -> None:
        path = Path(__file__).parents[1] / "contract" / "deletion_waivers_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["waivers"]), 1)
        waiver = payload["waivers"][0]
        self.assertEqual(waiver["removed_physical_lines"], 252)
        self.assertEqual(waiver["permitted_replay_differences"], [])
        self.assertEqual(
            waiver["allowed_failures"],
            [
                "tests/unit/test_tool_generator.py::test_generation_request_includes_reusable_name_hint",
                "tests/unit/test_tool_generator.py::test_generation_request_preserves_negative_applicability_metadata",
                "tests/unit/test_tool_generator.py::test_generation_request_includes_family_contract_guidance",
                "tests/unit/test_tool_generator.py::test_generation_request_includes_exact_contact_phone_normalization",
                "tests/unit/test_tool_generator.py::test_generation_request_requires_contract_fields",
                "tests/unit/test_tool_generator.py::test_generation_request_includes_medium_grain_guidance",
                "tests/unit/test_tool_generator.py::test_generation_request_includes_failure_memory_and_cluster_context",
            ],
        )


if __name__ == "__main__":
    unittest.main()
