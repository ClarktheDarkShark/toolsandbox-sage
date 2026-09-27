from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from validation.replay import compare
from validation.replay.compare import ACTOR_SOURCE_PATH, _actor_source_identity
from validation.production_source_identity import (
    PRODUCTION_PYTHON_SOURCE_SCOPE,
    production_python_source_identity,
)


class ActorSourceIdentityTest(unittest.TestCase):
    def test_hashes_both_actor_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference_root = root / "reference"
            candidate_root = root / "candidate"
            reference_actor = reference_root / ACTOR_SOURCE_PATH
            candidate_actor = candidate_root / ACTOR_SOURCE_PATH
            reference_actor.parent.mkdir(parents=True)
            candidate_actor.parent.mkdir(parents=True)
            reference_actor.write_bytes(b"reference actor\n")
            candidate_actor.write_bytes(b"candidate actor\n")

            identity = _actor_source_identity(reference_root, candidate_root)

        self.assertEqual(
            identity,
            {
                "path": ACTOR_SOURCE_PATH.as_posix(),
                "reference_sha256": hashlib.sha256(b"reference actor\n").hexdigest(),
                "candidate_sha256": hashlib.sha256(b"candidate actor\n").hexdigest(),
            },
        )

    def test_missing_actor_source_fails_instead_of_emitting_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            with self.assertRaises(FileNotFoundError):
                _actor_source_identity(root / "reference", root / "candidate")


class ProductionPythonSourceIdentityTest(unittest.TestCase):
    def test_hashes_sorted_relative_paths_and_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "src/sage_ts/a.py"
            second = root / "src/sage_ts/nested/z.py"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"first\n")
            second.write_bytes(b"\x00second\r\n")
            (root / "src/sage_ts/ignored.txt").write_text("ignored", encoding="utf-8")

            identity = production_python_source_identity(root)

        digest = hashlib.sha256()
        for relative, content in (
            ("src/sage_ts/a.py", b"first\n"),
            ("src/sage_ts/nested/z.py", b"\x00second\r\n"),
        ):
            relative_bytes = relative.encode("utf-8")
            digest.update(len(relative_bytes).to_bytes(8, "big"))
            digest.update(relative_bytes)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        self.assertEqual(
            identity,
            {
                "scope": PRODUCTION_PYTHON_SOURCE_SCOPE,
                "file_count": 2,
                "sha256": digest.hexdigest(),
            },
        )

    def test_missing_or_empty_production_scope_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                production_python_source_identity(root)
            (root / "src/sage_ts").mkdir(parents=True)
            with self.assertRaises(ValueError):
                production_python_source_identity(root)

    def test_symlinked_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "src/sage_ts"
            external = root / "external"
            source.mkdir(parents=True)
            external.mkdir()
            (source / "present.py").write_text("present\n", encoding="utf-8")
            (external / "hidden.py").write_text("hidden\n", encoding="utf-8")
            (source / "linked").symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "contains symlinks"):
                production_python_source_identity(root)


class CompareSourceStabilityTest(unittest.TestCase):
    def test_source_change_during_replay_is_a_probe_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference_root = root / "reference"
            candidate_root = root / "candidate"
            for checkout in (reference_root, candidate_root):
                actor = checkout / ACTOR_SOURCE_PATH
                actor.parent.mkdir(parents=True)
                actor.write_text("actor\n", encoding="utf-8")
                helper = checkout / "src/sage_ts/runtime/helper.py"
                helper.parent.mkdir(parents=True)
                helper.write_text("helper\n", encoding="utf-8")
            output = root / "report.json"

            def run_snapshot(**kwargs: object) -> dict[str, object]:
                if Path(str(kwargs["root"])).resolve() == candidate_root.resolve():
                    (candidate_root / "src/sage_ts/runtime/helper.py").write_text(
                        "changed during replay\n", encoding="utf-8"
                    )
                return {"stable": True}

            argv = [
                "compare.py",
                "--reference-root",
                str(reference_root),
                "--candidate-root",
                str(candidate_root),
                "--python",
                sys.executable,
                "--output",
                str(output),
                "--probes",
                "imports",
            ]
            with (
                mock.patch.object(compare, "_run_snapshot", side_effect=run_snapshot),
                mock.patch.object(sys, "argv", argv),
            ):
                result = compare.main()

            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result, 2)
        self.assertEqual(payload["status"], "probe_error")
        self.assertIn("changed while replay probes were running", payload["error"])


if __name__ == "__main__":
    unittest.main()
