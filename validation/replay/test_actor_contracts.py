from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from validation.replay.actor_contracts import verify_actor_fixture_bytes
from validation.replay.actor_fixture import actor_cases
from validation.replay.compare import _diff


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "actor_fixture.py"
MANIFEST = HERE / "actor_fixture.manifest.json"


class ActorFixtureIntegrityTest(unittest.TestCase):
    def test_manifest_accepts_exact_fixture_and_rejects_one_byte_tamper(self) -> None:
        payload = FIXTURE.read_bytes()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        verify_actor_fixture_bytes(payload, manifest)
        tampered = bytearray(payload)
        tampered[len(tampered) // 2] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA-256 changed"):
            verify_actor_fixture_bytes(bytes(tampered), manifest)

    def test_fixture_declares_complete_builder_receipt_set(self) -> None:
        cases = actor_cases()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        receipts = {name for case in cases for name in case.get("direct_positive", ())}

        self.assertEqual(len(cases), manifest["case_count"])
        self.assertEqual(len(receipts), 49)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertFalse(
            any(case["provenance"] == "trajectory_derived" for case in cases)
        )


class ActorSnapshotTamperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = {
            "messages": [
                {"role": "system", "content": "policy"},
                {"role": "user", "content": "request"},
            ],
            "tools": [
                {"type": "function", "function": {"name": "generated_first"}},
                {"type": "function", "function": {"name": "native_second"}},
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "generated_first"},
            },
        }

    def test_detects_prompt_text_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        tampered["messages"][0]["content"] = "changed policy"

        self.assertEqual(
            _diff(self.reference, tampered)[0]["path"], "/messages/0/content"
        )

    def test_detects_schema_order_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        tampered["tools"].reverse()

        paths = {difference["path"] for difference in _diff(self.reference, tampered)}
        self.assertIn("/tools/0/function/name", paths)
        self.assertIn("/tools/1/function/name", paths)

    def test_detects_named_choice_tamper(self) -> None:
        tampered = copy.deepcopy(self.reference)
        tampered["tool_choice"]["function"]["name"] = "native_second"

        self.assertEqual(
            _diff(self.reference, tampered)[0]["path"],
            "/tool_choice/function/name",
        )


if __name__ == "__main__":
    unittest.main()
