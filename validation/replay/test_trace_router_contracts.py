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
    _capture_exact_call,
    _exact_json_snapshot,
)
from validation.replay.trace_router_contracts import _trace_contracts  # noqa: E402


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

        self.assertEqual(observed["call"]["result"]["value"], {
            "payload": None,
            "records": None,
        })
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


if __name__ == "__main__":
    unittest.main()
