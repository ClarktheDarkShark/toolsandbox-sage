from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from validation.contract import verify_frozen_contract as verifier


ACTOR_PATH = "src/sage_ts/adapters/openai_toolsandbox_roles.py"
FROZEN_COMMIT = "a" * 40
CANDIDATE_COMMIT = "b" * 40


class ActorSourceEquivalenceReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary_root = Path(self.temporary.name).resolve()
        self.reference_root = temporary_root / "reference"
        self.candidate_root = temporary_root / "candidate"
        self.reference_actor = self.reference_root / ACTOR_PATH
        self.candidate_actor = self.candidate_root / ACTOR_PATH
        self.reference_actor.parent.mkdir(parents=True)
        self.candidate_actor.parent.mkdir(parents=True)
        self.reference_actor.write_text("reference actor\n", encoding="utf-8")
        self.candidate_actor.write_text("refactored actor\n", encoding="utf-8")
        self.reference_sha = hashlib.sha256(
            self.reference_actor.read_bytes()
        ).hexdigest()
        self.actor_source = {
            "role": verifier.ACTOR_POLICY_ROLE,
            "path": ACTOR_PATH,
            "sha256": self.reference_sha,
        }
        self.contract = {
            "reference_source": {"git_commit": FROZEN_COMMIT},
        }
        self.evidence_path = temporary_root / "replay-report.json"
        self.payload = {
            "schema_version": 1,
            "status": "equivalent",
            "reference_root": str(self.reference_root),
            "candidate_root": str(self.candidate_root),
            "reference_commit": FROZEN_COMMIT,
            "candidate_commit": CANDIDATE_COMMIT,
            "actor_source": {
                "path": ACTOR_PATH,
                "reference_sha256": self.reference_sha,
                "candidate_sha256": hashlib.sha256(
                    self.candidate_actor.read_bytes()
                ).hexdigest(),
            },
            "probes": verifier._expected_replay_probes(),
            "approved_normalizations": {"reference": [], "candidate": []},
            "difference_count": 0,
            "differences": [],
        }
        self._write_evidence()

    def _write_evidence(self) -> None:
        self.evidence_path.write_text(
            json.dumps(self.payload, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _git(self, root: Path, *arguments: str) -> str:
        resolved = root.resolve()
        if arguments == ("rev-parse", "HEAD"):
            if resolved == self.reference_root:
                return FROZEN_COMMIT
            if resolved == self.candidate_root:
                return CANDIDATE_COMMIT
        if arguments == ("status", "--porcelain", "--untracked-files=all"):
            if resolved in {self.reference_root, self.candidate_root}:
                return ""
        raise AssertionError(f"unexpected git call: {resolved}, {arguments}")

    def _verify(self) -> tuple[bool, verifier.VerificationReport]:
        report = verifier.VerificationReport()
        with mock.patch.object(verifier, "_git", side_effect=self._git):
            valid = verifier._verify_actor_source_equivalence_report(
                self.evidence_path,
                self.contract,
                self.candidate_root,
                self.actor_source,
                report,
            )
        return valid, report

    def test_accepts_complete_zero_difference_report_for_expected_roots(self) -> None:
        valid, report = self._verify()

        self.assertTrue(valid)
        self.assertEqual(report.errors, [])
        roots_check = next(
            check
            for check in report.checks
            if check["name"] == "actor_source_equivalence_report.roots_are_distinct"
        )
        self.assertEqual(roots_check["status"], "pass")

    def test_rejects_same_reference_and_candidate_root(self) -> None:
        self.payload["reference_root"] = str(self.candidate_root)
        self._write_evidence()

        valid, report = self._verify()

        self.assertFalse(valid)
        self.assertTrue(
            any(
                check["name"] == "actor_source_equivalence_report.roots_are_distinct"
                and check["status"] == "fail"
                for check in report.checks
            )
        )

    def test_rejects_report_created_before_current_actor_source(self) -> None:
        report_mtime = self.evidence_path.stat().st_mtime_ns
        os.utime(
            self.candidate_actor,
            ns=(report_mtime + 1_000_000, report_mtime + 1_000_000),
        )

        valid, report = self._verify()

        self.assertFalse(valid)
        self.assertTrue(
            any(
                check["name"] == "actor_source_equivalence_report.freshness"
                and check["status"] == "fail"
                for check in report.checks
            )
        )

    def test_rejects_actor_bytes_changed_after_report_even_with_older_mtime(
        self,
    ) -> None:
        self.candidate_actor.write_text("changed after replay\n", encoding="utf-8")
        report_mtime = self.evidence_path.stat().st_mtime_ns
        os.utime(
            self.candidate_actor,
            ns=(report_mtime - 1_000_000, report_mtime - 1_000_000),
        )

        valid, report = self._verify()

        self.assertFalse(valid)
        binding_check = next(
            check
            for check in report.checks
            if check["name"]
            == "actor_source_equivalence_report.actor_source.candidate_report_binding"
        )
        self.assertEqual(binding_check["status"], "fail")
        freshness_check = next(
            check
            for check in report.checks
            if check["name"] == "actor_source_equivalence_report.freshness"
        )
        self.assertEqual(freshness_check["status"], "pass")

    def test_rejects_a_dirty_reference_checkout(self) -> None:
        def dirty_reference_git(root: Path, *arguments: str) -> str:
            if root.resolve() == self.reference_root and arguments == (
                "status",
                "--porcelain",
                "--untracked-files=all",
            ):
                return "?? injected.py"
            return self._git(root, *arguments)

        report = verifier.VerificationReport()
        with mock.patch.object(verifier, "_git", side_effect=dirty_reference_git):
            valid = verifier._verify_actor_source_equivalence_report(
                self.evidence_path,
                self.contract,
                self.candidate_root,
                self.actor_source,
                report,
            )

        self.assertFalse(valid)
        self.assertTrue(
            any(
                check["name"]
                == "actor_source_equivalence_report.reference_root.worktree_status"
                and check["status"] == "fail"
                for check in report.checks
            )
        )

    def test_rejects_non_equivalent_partial_or_misbound_reports(self) -> None:
        invalid_mutations = {
            "non_equivalent_status": lambda payload: payload.update(status="different"),
            "nonzero_differences": lambda payload: payload.update(
                difference_count=1,
                differences=[{"path": "/actor", "kind": "value_changed"}],
            ),
            "partial_probe_suite": lambda payload: payload.update(
                probes=payload["probes"][:-1]
            ),
            "wrong_candidate_root": lambda payload: payload.update(
                candidate_root=str(self.reference_root)
            ),
            "wrong_reference_commit": lambda payload: payload.update(
                reference_commit="c" * 40
            ),
            "wrong_candidate_commit": lambda payload: payload.update(
                candidate_commit="d" * 40
            ),
            "wrong_actor_path": lambda payload: payload["actor_source"].update(
                path="src/sage_ts/wrong.py"
            ),
            "wrong_reference_actor_hash": lambda payload: payload[
                "actor_source"
            ].update(reference_sha256="e" * 64),
            "wrong_candidate_actor_hash": lambda payload: payload[
                "actor_source"
            ].update(candidate_sha256="f" * 64),
        }
        baseline = deepcopy(self.payload)
        for name, mutate in invalid_mutations.items():
            with self.subTest(name=name):
                self.payload = deepcopy(baseline)
                mutate(self.payload)
                self._write_evidence()

                valid, report = self._verify()

                self.assertFalse(valid)
                self.assertGreater(len(report.errors), 0)


class PolicySourceHashWaiverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo_root = Path(self.temporary.name).resolve()
        self.source_path = self.repo_root / "policy.py"
        self.source_path.write_text("refactored\n", encoding="utf-8")
        self.expected_sha = hashlib.sha256(b"reference\n").hexdigest()

    def _source(self, role: str) -> dict[str, str]:
        return {
            "role": role,
            "path": self.source_path.name,
            "sha256": self.expected_sha,
        }

    def test_default_actor_hash_check_remains_strict(self) -> None:
        report = verifier.VerificationReport()

        verifier._verify_policy_source_hash(
            self.repo_root,
            self._source(verifier.ACTOR_POLICY_ROLE),
            report,
            actor_source_equivalence_valid=False,
        )

        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.checks[-1]["status"], "fail")

    def test_valid_replay_waives_only_named_actor_hash_check(self) -> None:
        report = verifier.VerificationReport()

        verifier._verify_policy_source_hash(
            self.repo_root,
            self._source(verifier.ACTOR_POLICY_ROLE),
            report,
            actor_source_equivalence_valid=True,
        )

        self.assertEqual(report.errors, [])
        self.assertEqual(
            report.checks[-1],
            {
                "name": "policy_configuration.actor_policy.source_sha256",
                "status": "waived",
                "observed": hashlib.sha256(b"refactored\n").hexdigest(),
                "expected": self.expected_sha,
                "evidence": "actor_source_equivalence_report",
            },
        )

    def test_valid_actor_replay_cannot_waive_another_policy_source(self) -> None:
        report = verifier.VerificationReport()

        verifier._verify_policy_source_hash(
            self.repo_root,
            self._source("publication_protocol"),
            report,
            actor_source_equivalence_valid=True,
        )

        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.checks[-1]["status"], "fail")


if __name__ == "__main__":
    unittest.main()
